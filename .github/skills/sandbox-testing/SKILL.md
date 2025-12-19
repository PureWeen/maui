---
name: sandbox-testing
description: Specialized skill for working with the .NET MAUI Sandbox app for testing, validation, and experimentation. Use this skill when the user asks to "test this PR", "validate PR #XXXXX in Sandbox", "reproduce issue #XXXXX", or "try out in Sandbox".
license: MIT
metadata:
  version: "1.0"
  author: dotnet-maui-team
  repository: dotnet/maui
---

# Sandbox Testing Skill

You are a specialized testing skill for the .NET MAUI Sandbox app. Your job is to validate PRs and reproduce issues through hands-on testing with the Sandbox sample application.

## When to Invoke

Invoke this skill when user:
- Asks to "test this PR" or "validate PR #XXXXX"
- Asks to "reproduce issue #XXXXX" in Sandbox
- Asks to "test" or "verify" something using Sandbox
- Wants to deploy to iOS/Android for manual testing
- Mentions Sandbox app by name in testing context

## What This Skill Does

- ✅ Reads and follows comprehensive sandbox testing instructions
- ✅ Creates test scenarios in Sandbox MainPage.xaml[.cs]
- ✅ Runs BuildAndRunSandbox.ps1 for automated build/deploy/test
- ✅ Analyzes device logs and Appium output
- ✅ Provides detailed testing summaries with verdicts

## Workflow

When invoked, you will:

1. **Checkout the PR branch** (if testing a PR)
2. **Understand the issue and PR changes**
3. **Create appropriate test scenario in Sandbox MainPage**
4. **Run BuildAndRunSandbox.ps1 script**
5. **Analyze results from logs and test execution**
6. **Provide comprehensive testing summary**

---

## 🚨 CRITICAL VALIDATION RULES

**YOU MUST FOLLOW THESE RULES WHEN RUNNING SANDBOX TESTS:**

### What You NEVER Do

- ❌ **NEVER** assume test completion without validation
- ❌ **NEVER** claim success based on HTTP 200 responses alone
- ❌ **NEVER** skip the mandatory validation checklist
- ❌ **NEVER** proceed without verifying device logs show expected behavior
- ❌ **NEVER** switch branches during reproduction - stay on current branch

### What You ALWAYS Do

- ✅ **ALWAYS** save full output to file for analysis
- ✅ **ALWAYS** check for errors/exceptions FIRST before claiming success
- ✅ **ALWAYS** verify "Test completed" marker appears in output
- ✅ **ALWAYS** verify expected test actions in logs
- ✅ **ALWAYS** check device logs for Console.WriteLine markers

---

## Core Workflow

### Step 1: Understand Issue

```bash
# ONLY if user explicitly asks to test a PR:
gh pr checkout <PR_NUMBER>
```

**Understand the issue thoroughly:**
- Read issue report or PR description
- Identify what bug needs to be reproduced
- Note affected platforms
- Look for reproduction steps in the issue

### Step 2: Create Test Scenario in Sandbox

**Choose test scenario source (in priority order):**

1. **From Issue Reproduction** (Preferred) - Use exact scenario user reported
2. **From PR's UI Tests** (Alternative) - Adapt test page code to Sandbox
3. **Create Your Own** (Last Resort) - Design based on PR changes

**Files to modify**:
- `src/Controls/samples/Controls.Sample.Sandbox/MainPage.xaml[.cs]`
- `CustomAgentLogsTmp/Sandbox/RunWithAppiumTest.cs` (MANDATORY)

**Setting up the Appium test file:**

```bash
mkdir -p CustomAgentLogsTmp/Sandbox
cp .github/scripts/templates/RunWithAppiumTest.template.cs CustomAgentLogsTmp/Sandbox/RunWithAppiumTest.cs
```

Then update `RunWithAppiumTest.cs` to match your MainPage AutomationIds.

### Step 3: Run Test

```powershell
# Android
pwsh .github/scripts/BuildAndRunSandbox.ps1 -Platform Android

# iOS
pwsh .github/scripts/BuildAndRunSandbox.ps1 -Platform iOS

# iOS with specific device
pwsh .github/scripts/BuildAndRunSandbox.ps1 -Platform iOS -DeviceUdid "YOUR-DEVICE-UDID"
```

### Step 4: Validate Results

After script completes, run validation checklist:

```bash
# Step 1: Check for errors/exceptions FIRST
grep -iE "error|exception|failed" CustomAgentLogsTmp/Sandbox/build-run-output.log | head -20

# Step 2: Verify expected test actions
grep -E "Tapping|Screenshot saved|Found.*element" CustomAgentLogsTmp/Sandbox/build-run-output.log

# Step 3: Verify test completion marker
grep "Test completed" CustomAgentLogsTmp/Sandbox/build-run-output.log

# Step 4: Verify device logs show expected behavior
grep "SANDBOX" CustomAgentLogsTmp/Sandbox/android-device.log  # or ios-device.log
```

**If ANY check fails, investigate and fix before proceeding.**

---

## Platform Selection

Follow this priority:
1. **PR title has platform tag** → Test that platform ONLY
2. **All files in platform-specific paths** → Test that platform ONLY
3. **Issue mentions specific platform** → Test that platform
4. **High-risk cross-platform code** → Test Android + iOS
5. **Default** → Test Android ONLY (faster)

---

## Output Format

```markdown
## PR Testing Summary

**PR**: #XXXXX - [Title]
**Platform Tested**: Android/iOS
**Issue**: [Brief description]

---

### Test Scenario Setup

**Source**: [From issue reproduction / From PR UITest / Custom scenario]
**What was tested**: [Specific actions taken]

---

### Test Results WITH PR Fix

**Observed Behavior**: [What happened]
**Validation Checklist**: [Results of all checks]

---

### Verdict

✅ **FIX VALIDATED** / ⚠️ **PARTIAL** / ❌ **ISSUES FOUND** / 🚫 **CANNOT TEST**
```

---

## Scope

This skill handles the complete Sandbox testing workflow. For automated UI test creation (not Sandbox testing), use the `uitest-coding` skill instead.

---

## External References

For complete sandbox testing documentation, see:
- [sandbox.instructions.md](../../instructions/sandbox.instructions.md) - Full testing guide
