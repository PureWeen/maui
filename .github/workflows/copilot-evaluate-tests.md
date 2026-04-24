---
description: Evaluates test quality, coverage, and appropriateness on PRs that add or modify tests
on:
  pull_request_target:
    types: [opened, synchronize, reopened]
    paths:
      - 'src/**/tests/**'
      - 'src/**/test/**'
  slash_command:
    name: evaluate-tests
    events: [pull_request_comment]
  workflow_dispatch:
    inputs:
      pr_number:
        description: 'PR number to evaluate'
        required: true
        type: number
      suppress_output:
        description: 'Dry-run — evaluate but do not post output on the PR'
        required: false
        type: boolean
        default: false
  bots:
    - "copilot-swe-agent[bot]"

labels: ["pr-review", "testing"]

# Trigger filtering: pull_request_target auto-triggers on test file changes,
# slash_command compiles to issue_comment (platform handles command matching),
# workflow_dispatch is always allowed.
if: >-
  (github.event_name == 'pull_request_target' && github.event.pull_request.draft == false) ||
  github.event_name == 'issue_comment' ||
  github.event_name == 'workflow_dispatch'

permissions:
  contents: read
  issues: read
  pull-requests: read

engine:
  id: copilot
  model: claude-sonnet-4.6

safe-outputs:
  add-comment:
    max: 1
    target: "*"
    hide-older-comments: true
  noop:
    report-as-issue: false
  messages:
    footer: "> 🧪 *Test evaluation by [{workflow_name}]({run_url})*"
    run-started: "🔬 Evaluating tests on this PR… [{workflow_name}]({run_url})"
    run-success: "✅ Test evaluation complete! [{workflow_name}]({run_url})"
    run-failure: "❌ Test evaluation failed. [{workflow_name}]({run_url}) {status}"

tools:
  github:
    toolsets: [default]
  bash: ["dotnet", "pwsh", "gh", "env", "ls", "cat", "head", "tail", "grep", "echo", "find", "curl", "sed", "awk", "mkdir", "cp", "wc", "sort", "date", "pwd", "uniq", "yq"]

network:
  allowed:
    - defaults
    - dotnet
    - java
    - "services.gradle.org"
    - "downloads.gradle.org"
    - "releaseassets.githubusercontent.com"

concurrency:
  group: "evaluate-pr-tests-${{ github.event.pull_request.number || github.event.issue.number || inputs.pr_number || github.run_id }}"
  cancel-in-progress: true

timeout-minutes: 20

steps:
  - name: Gate — skip if no test source files in diff
    if: github.event_name == 'pull_request_target' || github.event_name == 'issue_comment'
    env:
      GH_TOKEN: ${{ github.token }}
      PR_NUMBER: ${{ github.event.pull_request.number || github.event.issue.number || inputs.pr_number }}
    run: |
      # Verify this is an open PR
      if ! STATE=$(gh pr view "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --json state --jq .state 2>&1); then
        echo "❌ Failed to fetch PR #$PR_NUMBER state: $STATE"
        exit 1
      fi
      if [ "$STATE" != "OPEN" ]; then
        echo "⏭️ PR #$PR_NUMBER is $STATE — skipping evaluation."
        exit 1
      fi
      # Try gh pr diff first; fall back to REST API only on command failure
      if DIFF_OUTPUT=$(gh pr diff "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --name-only 2>/dev/null); then
        TEST_FILES=$(echo "$DIFF_OUTPUT" \
          | grep -E '\.(cs|xaml)$' \
          | grep -iE '(tests?/|TestCases|UnitTests|DeviceTests)' \
          || true)
      else
        # gh pr diff fails with HTTP 406 for PRs with 300+ files; use paginated files API
        if ! API_FILES=$(gh api "repos/$GITHUB_REPOSITORY/pulls/$PR_NUMBER/files" --paginate --jq '.[].filename' 2>&1); then
          echo "❌ gh pr diff failed and REST API fallback also failed: $API_FILES"
          exit 1
        fi
        TEST_FILES=$(echo "$API_FILES" \
          | grep -E '\.(cs|xaml)$' \
          | grep -iE '(tests?/|TestCases|UnitTests|DeviceTests)' \
          || true)
      fi
      if [ -z "$TEST_FILES" ]; then
        echo "⏭️ No test source files (.cs/.xaml) found in PR diff. Nothing to evaluate."
        exit 1
      fi
      echo "✅ Found test files to evaluate:"
      echo "$TEST_FILES" | head -20

  # For slash_command triggers, the gh-aw platform's checkout_pr_branch.cjs runs
  # AFTER all user steps and overlays the PR branch onto the workspace. This means
  # fork PRs can supply their own .github/skills/ and .github/instructions/.
  # We cannot restore trusted infra here because the platform checkout runs later.
  # Mitigation: agent is sandboxed (no credentials), max 1 comment via safe-outputs,
  # and the agent prompt includes a pre-flight check that catches missing SKILL.md.
  # See: .github/instructions/gh-aw-workflows.instructions.md "The issue_comment + Fork Problem"

  # For workflow_dispatch, the platform skips checkout entirely — this step is the
  # only thing that gets the PR code onto disk and restores trusted infra from main.
  - name: Checkout PR and restore agent infrastructure
    if: github.event_name == 'workflow_dispatch'
    env:
      GH_TOKEN: ${{ github.token }}
      PR_NUMBER: ${{ inputs.pr_number }}
    run: pwsh .github/scripts/Checkout-GhAwPr.ps1

  # ── Provision .NET SDK + MAUI workloads (TRUSTED — no repo code executed) ──
  # Security: This step runs on the runner with GITHUB_TOKEN. It downloads
  # tools ONLY from Microsoft CDN and Gradle CDN — no repo scripts are executed.
  # The only thing read from the repo is global.json's version string (passive data).
  # The workspace .dotnet/ and .gradle-home/ are mounted into the agent container.
  - name: Provision .NET SDK, MAUI workloads, and Gradle
    run: |
      set -euo pipefail

      # ── 1. Install .NET SDK from Microsoft CDN ──
      SDK_VERSION=$(jq -r '.tools.dotnet' global.json)
      echo "⏳ Installing .NET SDK ${SDK_VERSION} into .dotnet/ ..."
      curl -sSL https://builds.dotnet.microsoft.com/dotnet/scripts/v1/dotnet-install.sh \
        | bash -s -- --install-dir .dotnet --version "$SDK_VERSION"
      echo "✅ .NET SDK installed: $(.dotnet/dotnet --version)"

      # ── 2. Install MAUI workloads ──
      echo "⏳ Installing MAUI Android workload..."
      .dotnet/dotnet workload install maui-android --skip-sign-check
      echo "✅ Workloads installed:"
      .dotnet/dotnet workload list

      # ── 3. Pre-cache Gradle distribution ──
      # The AWF squid proxy blocks Gradle's HTTPS CONNECT tunneling even when
      # services.gradle.org is allowlisted. Download it here (no proxy) and
      # place it in the Gradle wrapper cache structure.
      GRADLE_VER=8.13
      GRADLE_URL="https://services.gradle.org/distributions/gradle-${GRADLE_VER}-all.zip"
      # Gradle's wrapper uses base36(MD5(url)) as the cache directory name
      GRADLE_HASH=$(echo -n "$GRADLE_URL" | md5sum | cut -d' ' -f1 \
        | python3 -c "import sys; h=int(sys.stdin.readline().strip(),16); c='0123456789abcdefghijklmnopqrstuvwxyz'; r=''; exec('while h>0:\n r=c[h%36]+r\n h//=36'); print(r)")
      DIST_DIR=".gradle-home/wrapper/dists/gradle-${GRADLE_VER}-all/${GRADLE_HASH}"
      mkdir -p "$DIST_DIR"
      echo "⏳ Downloading Gradle ${GRADLE_VER} (hash dir: ${GRADLE_HASH})..."
      curl -sL "$GRADLE_URL" -o "$DIST_DIR/gradle-${GRADLE_VER}-all.zip"
      echo "⏳ Extracting..."
      unzip -q "$DIST_DIR/gradle-${GRADLE_VER}-all.zip" -d "$DIST_DIR/"
      touch "$DIST_DIR/gradle-${GRADLE_VER}-all.zip.ok"
      echo "✅ Gradle ${GRADLE_VER} cached at .gradle-home/"
      ls "$DIST_DIR/"
---

# Evaluate PR Tests

Invoke the **evaluate-pr-tests** skill: read and follow `.github/skills/evaluate-pr-tests/SKILL.md`.

## Context

- **Repository**: ${{ github.repository }}
- **PR Number**: ${{ github.event.pull_request.number || github.event.issue.number || inputs.pr_number }}

The PR branch has been checked out for you. All files from the PR are available locally.

## Pre-flight check

Before starting, verify the skill file exists:

```bash
test -f .github/skills/evaluate-pr-tests/SKILL.md
```

If the file is **missing**, the fork PR branch is likely not rebased on the latest `main`. Post a comment using `add_comment`:

```markdown
## 🧪 PR Test Evaluation

❌ **Cannot evaluate**: this PR's branch does not include the evaluate-pr-tests skill (`.github/skills/evaluate-pr-tests/SKILL.md` is missing).

**Fix**: rebase your fork on the latest `main` branch and push again. The evaluation will trigger automatically once the skill file is available.
```

Then stop — do not proceed with the evaluation.

## Dry-run mode

When triggered via `workflow_dispatch`, the `suppress_output` input controls behavior.
- If `${{ inputs.suppress_output }}` == **true**, perform the full evaluation but **do not** post output on the PR. Write the evaluation to the workflow log only. This is useful for testing the skill without spamming the PR.
- If **false** (default), post the output as normal.

## When no action is needed

If there is nothing to evaluate (PR has no test files, PR is a docs-only change, etc.), you **must** call the `noop` tool with a message explaining why:

```json
{"noop": {"message": "No action needed: [brief explanation, e.g. 'PR contains no test files']"}}
```

Do not post a comment and do not silently exit — always use `noop` so the workflow run shows a clear reason.

## EXPERIMENT: Build MAUI inside gh-aw sandbox (run this FIRST)

The .NET SDK, MAUI workloads, and Gradle are **pre-provisioned** by the runner (trusted `steps:` block — no repo code executed). The agent just needs to set environment variables and build.

Run each step in order and report ALL output.

### Step 1: Verify pre-provisioned SDK

```bash
export DOTNET_ROOT=$(pwd)/.dotnet
export GRADLE_USER_HOME=$(pwd)/.gradle-home

echo "=== 1a: SDK version ==="
dotnet --version 2>&1

echo "=== 1b: Installed packs ==="
ls .dotnet/packs/ 2>&1 | head -20

echo "=== 1c: Gradle cache ==="
ls -la .gradle-home/wrapper/dists/ 2>&1
```

### Step 2: Build MAUI MSBuild tasks

```bash
export DOTNET_ROOT=$(pwd)/.dotnet
export GRADLE_USER_HOME=$(pwd)/.gradle-home

echo "=== 2: Build MSBuild tasks ==="
dotnet build Microsoft.Maui.BuildTasks.slnf -c Release 2>&1 | tail -30
```

### Step 3: Build HostApp for Android

```bash
export DOTNET_ROOT=$(pwd)/.dotnet
export GRADLE_USER_HOME=$(pwd)/.gradle-home

echo "=== 3a: Find HostApp ==="
HOSTAPP=$(find . -name "Controls.TestCases.HostApp.csproj" -type f 2>/dev/null | head -1)
echo "Found: $HOSTAPP"

echo "=== 3b: Restore HostApp ==="
dotnet restore "$HOSTAPP" 2>&1 | tail -20

echo "=== 3c: Build HostApp for Android ==="
dotnet build "$HOSTAPP" -f net10.0-android -c Debug --no-restore 2>&1 | tail -40
```

After running ALL steps, post the full results using `add_comment` with `item_number` set to the PR number. Include ALL output from every step. Then call `noop` with message "Build experiment complete" and STOP — do not proceed with the regular evaluation below.

## Running the skill (SKIP FOR THIS EXPERIMENT)

1. Use `gh pr view <number>` to fetch PR metadata (title, body, labels, base branch). If `gh` CLI is unavailable, use the GitHub MCP tools instead.
2. Run `pwsh .github/skills/evaluate-pr-tests/scripts/Gather-TestContext.ps1 -PrNumber <number>` to gather automated context (use the PR number from the Context section above)
3. Read the context report and the actual changed files, then evaluate per SKILL.md criteria
4. Post results using `add_comment` with `item_number` set to the PR number

## Posting Results

If dry-run mode is active (`suppress_output` is true), log the evaluation report to stdout and stop — do **not** call `add_comment`.

Otherwise, call `add_comment` with `item_number` set to the PR number. Wrap the report in a collapsible `<details>` block:

```markdown
## 🧪 PR Test Evaluation

**Overall Verdict:** [✅ Tests are adequate | ⚠️ Tests need improvement | ❌ Tests are insufficient]

[1-2 sentence summary]

> 👍 / 👎 — Was this evaluation helpful? React to let us know!

<details>
<summary>📊 Expand Full Evaluation</summary>

[Full report from SKILL.md]

</details>
```
