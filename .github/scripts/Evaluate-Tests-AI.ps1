#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Evaluates PR tests using GitHub Models API.

.DESCRIPTION
    Builds a prompt from pre-gathered context (test files, fix files, PR metadata,
    automated analysis from Gather-TestContext.ps1) and calls GitHub Models API
    for a single-shot AI evaluation of test quality.

    This is the standard GitHub Actions equivalent of what gh-aw's interactive
    Copilot agent does. The key tradeoff is:
      - gh-aw agent: Can interactively read files, use tools, iterate
      - This script: Pre-gathers all context, single API call

    For complex PRs with many files, the gh-aw agent may produce better results
    because it can selectively read relevant code paths. This script compensates
    by including all test/fix file contents in the prompt (up to token limits).

.PARAMETER PrNumber
    The PR number being evaluated.

.PARAMETER OutputPath
    Path to write the evaluation markdown output.

.PARAMETER Model
    GitHub Models model to use. Default: gpt-4o (good balance of quality/speed/cost).
    Other options: gpt-4.1, claude-sonnet-4.5 (if available on GitHub Models).

.EXAMPLE
    ./Evaluate-Tests-AI.ps1 -PrNumber 12345 -OutputPath evaluation.md
#>

param(
    [Parameter(Mandatory = $true)]
    [int]$PrNumber,

    [Parameter(Mandatory = $false)]
    [string]$OutputPath = "CustomAgentLogsTmp/TestEvaluation/evaluation.md",

    [Parameter(Mandatory = $false)]
    [string]$Model = "gpt-4o"
)

$ErrorActionPreference = "Stop"
$contextDir = "CustomAgentLogsTmp/TestEvaluation"

# ── Verify context files exist ──────────────────────────────────────────────
$requiredFiles = @(
    "context.md"       # From Gather-TestContext.ps1
    "test-files.txt"   # List of test files
    "fix-files.txt"    # List of fix files
)

foreach ($f in $requiredFiles) {
    $path = Join-Path $contextDir $f
    if (-not (Test-Path $path)) {
        Write-Warning "Missing context file: $path"
    }
}

# ── Load context ────────────────────────────────────────────────────────────
function SafeRead($filePath, $maxChars = 50000) {
    if (Test-Path $filePath) {
        $content = Get-Content $filePath -Raw -ErrorAction SilentlyContinue
        if ($content -and $content.Length -gt $maxChars) {
            return $content.Substring(0, $maxChars) + "`n`n⚠️ [Truncated at $maxChars chars]"
        }
        return $content
    }
    return "(not available)"
}

$automatedContext = SafeRead (Join-Path $contextDir "context.md") 30000
$testFiles        = SafeRead (Join-Path $contextDir "test-files.txt") 5000
$fixFiles         = SafeRead (Join-Path $contextDir "fix-files.txt") 5000
$testContents     = SafeRead (Join-Path $contextDir "test-contents.txt") 150000
$fixContents      = SafeRead (Join-Path $contextDir "fix-contents.txt") 80000

# Load PR metadata
$prMeta = "(not available)"
$prMetaPath = Join-Path $contextDir "pr-metadata.json"
if (Test-Path $prMetaPath) {
    try {
        $prJson = Get-Content $prMetaPath -Raw | ConvertFrom-Json
        $prMeta = @"
**Title:** $($prJson.title)
**Base branch:** $($prJson.baseRefName)
**Labels:** $($prJson.labels.name -join ', ')

**Description:**
$($prJson.body)
"@
    } catch {
        $prMeta = SafeRead $prMetaPath 10000
    }
}

# ── Build the system prompt ─────────────────────────────────────────────────
# This embeds the SKILL.md evaluation criteria directly. In gh-aw, the agent
# reads SKILL.md from disk. Here we inline the criteria to avoid needing
# the agent to browse files.
$systemPrompt = @"
You are a test evaluation expert for the .NET MAUI repository. You evaluate
the quality, coverage, and appropriateness of tests added in pull requests.

## Evaluation Criteria

Evaluate the PR tests against ALL of these criteria. For each criterion,
provide a verdict (✅ Pass, ⚠️ Concern, ❌ Fail) with explanation.

### 1. Fix Coverage
Does the test exercise the actual code paths changed by the fix? Would it
fail if the fix were reverted? Red flags: test only checks page loads,
asserts on wrong property, doesn't trigger buggy code path.

### 2. Edge Cases & Gaps
Does the test cover boundary conditions (null/empty, min/max, repeated
actions, platform-specific, async/timing, state transitions, error paths)?
For each branch in the fix code, is there a test?

### 3. Test Type Appropriateness
Is this the lightest test type that can verify the fix?
Priority: Unit Test > XAML Test > Device Test > UI Test.
Flag if a UI test could be a unit test, etc.

### 4. Convention Compliance
Check naming (IssueXXXXX), attributes ([Issue], [Category], [Test]),
base classes (_IssuesUITest), WaitForElement before interactions, no
Task.Delay/Thread.Sleep, no inline #if directives, no obsolete APIs.

### 5. Flakiness Risk
Risk factors: arbitrary delays, missing waits, screenshot without
retryTimeout, cursor blink in screenshot, external URLs, animation timing.

### 6. Duplicate Coverage
Does a similar test already exist? Is the new test redundant or covering
a different scenario?

### 7. Platform Scope
Does test coverage match platforms affected by the fix? Cross-platform
fix needs cross-platform tests.

### 8. Assertion Quality
Are assertions specific enough? Flag: Assert.That(true), Is.Not.Null
when should be Is.EqualTo, magic numbers.

### 9. Fix-Test Alignment
Do the test and fix target the same code paths/controls/features?

## Output Format

Produce your evaluation in this exact markdown format:

```
## 🧪 PR Test Evaluation

**Overall Verdict:** [✅ Tests are adequate | ⚠️ Tests need improvement | ❌ Tests are insufficient]

[1-2 sentence summary of the most important finding]

> 👍 / 👎 — Was this evaluation helpful? React to let us know!

<details>
<summary>📊 Expand Full Evaluation</summary>

### 1. Fix Coverage — [✅/⚠️/❌]
[analysis]

### 2. Edge Cases & Gaps — [✅/⚠️/❌]
**Covered:** [list]
**Missing:** [list with explanations]

### 3. Test Type Appropriateness — [✅/⚠️/❌]
**Current:** [type]
**Recommendation:** [same or lighter alternative]

### 4. Convention Compliance — [✅/⚠️/❌]
[issues found]

### 5. Flakiness Risk — [✅ Low / ⚠️ Medium / ❌ High]
[risk factors]

### 6. Duplicate Coverage — [✅/⚠️]
[analysis]

### 7. Platform Scope — [✅/⚠️/❌]
[analysis]

### 8. Assertion Quality — [✅/⚠️/❌]
[analysis]

### 9. Fix-Test Alignment — [✅/⚠️/❌]
[analysis]

### Recommendations
1. [most important]
2. [second]
3. [...]

</details>
```

Do NOT include the triple-backtick fences in your actual output — output raw markdown.
"@

# ── Build the user prompt ───────────────────────────────────────────────────
$userPrompt = @"
Evaluate the tests in PR #$PrNumber.

## PR Metadata
$prMeta

## Changed Files

### Test files:
$testFiles

### Fix files:
$fixFiles

## Automated Analysis (from Gather-TestContext.ps1)
$automatedContext

## Test File Contents
$testContents

## Fix File Contents
$fixContents

---

Now evaluate these tests against all 9 criteria and produce the structured report.
"@

# ── Call GitHub Models API ──────────────────────────────────────────────────
# GitHub Models API is accessible with GITHUB_TOKEN when models:read permission
# is granted. Endpoint: https://models.inference.ai.azure.com/chat/completions
#
# If GitHub Models is not available, falls back to a structured analysis
# without AI (just the automated context report).

$token = $env:GITHUB_TOKEN
if (-not $token) {
    Write-Error "GITHUB_TOKEN not set. Cannot call GitHub Models API."
    exit 1
}

$apiUrl = "https://models.inference.ai.azure.com/chat/completions"

$body = @{
    model    = $Model
    messages = @(
        @{ role = "system"; content = $systemPrompt }
        @{ role = "user";   content = $userPrompt }
    )
    max_tokens  = 4000
    temperature = 0.3
} | ConvertTo-Json -Depth 10

Write-Host "🤖 Calling GitHub Models API (model: $Model)..."
Write-Host "   Prompt size: system=$($systemPrompt.Length) chars, user=$($userPrompt.Length) chars"

$maxRetries = 2
$evaluation = $null

for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
    try {
        $response = Invoke-RestMethod -Uri $apiUrl `
            -Method Post `
            -Headers @{
                "Authorization" = "Bearer $token"
                "Content-Type"  = "application/json"
            } `
            -Body $body `
            -TimeoutSec 120

        $evaluation = $response.choices[0].message.content
        Write-Host "✅ AI evaluation received ($($evaluation.Length) chars)"
        break
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Warning "Attempt $attempt failed (HTTP $statusCode): $($_.Exception.Message)"

        if ($attempt -eq $maxRetries) {
            Write-Warning "GitHub Models API unavailable after $maxRetries attempts."
            Write-Warning "Falling back to automated-only analysis."
        }
        else {
            Start-Sleep -Seconds 5
        }
    }
}

# ── Fallback: structured report without AI ──────────────────────────────────
# If the Models API is unavailable, produce a useful report from the
# automated context alone. This is worse than the AI evaluation but still
# provides value.
if (-not $evaluation) {
    $evaluation = @"
## 🧪 PR Test Evaluation

**Overall Verdict:** ⚠️ Automated analysis only (AI evaluation unavailable)

The GitHub Models API was not reachable. Below is the automated analysis from
the context-gathering script. A human reviewer should evaluate the criteria
that require judgment (fix coverage, edge cases, test type appropriateness).

> ℹ️ To get AI-powered evaluation, ensure the workflow has `models: read`
> permission and GitHub Models is enabled for this repository.

<details>
<summary>📊 Automated Context Report</summary>

$automatedContext

</details>

### Test Files Changed
``````
$testFiles
``````

### Fix Files Changed
``````
$fixFiles
``````
"@
}

# ── Write output ────────────────────────────────────────────────────────────
$outputDir = Split-Path $OutputPath -Parent
if ($outputDir -and -not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}

Set-Content -Path $OutputPath -Value $evaluation -Encoding UTF8
Write-Host "📝 Evaluation written to: $OutputPath"
