---
name: issue-fix
description: >
  Implement fixes for .NET MAUI issues after reproduction is confirmed. 
  Use this skill when asked to "proceed with fix", "implement fix for #XXXXX", 
  or "fix the issue" after reproduction testing is complete.
  This skill assumes a reproduction test already exists and FAILS.
license: MIT
metadata:
  version: "1.0"
  author: dotnet-maui-team
  repository: dotnet/maui
---

# Issue Fix Skill

You are a specialized fix implementation skill for the .NET MAUI repository. Your role is to implement fixes for issues that have confirmed reproduction tests.

## When to Use This Skill

- ✅ "Proceed with fix for issue #XXXXX"
- ✅ "Implement the fix"
- ✅ "Fix the issue" (after reproduction is confirmed)
- ✅ "Continue with implementation"

## When NOT to Use This Skill

- ❌ "Fix issue #XXXXX" (fresh start) → Use `issue-reproduction` skill first
- ❌ "Investigate issue" → Use `issue-reproduction` skill first
- ❌ No reproduction test exists → Use `issue-reproduction` skill first

---

## 🛑 PREREQUISITE: Reproduction Must Exist

**Before using this skill, ensure:**
1. A reproduction test exists that FAILS (proving the bug)
2. The user has confirmed the reproduction is correct
3. The issue-reproduction skill has completed

**If no reproduction exists, stop and tell the user:**
> "No reproduction test found. Please run the issue-reproduction skill first."

---

## Workflow

```
1. Verify reproduction test exists and fails
2. Investigate root cause
3. Design fix approach
4. Implement fix
5. Verify reproduction test now PASSES
6. Test edge cases
7. Submit PR
```

---

## Step 1: Verify Reproduction Exists

Check for existing reproduction test:
- Unit test: `src/Controls/tests/Core.UnitTests/IssueXXXXXTests.cs`
- UI test: `src/Controls/tests/TestCases.HostApp/Issues/IssueXXXXX.xaml[.cs]`

**Run the test to confirm it FAILS:**
```bash
# For unit tests
pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests

# For UI tests
pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform [android|ios] -TestFilter "IssueXXXXX"
```

If test passes (no reproduction), stop and inform user.

---

## Step 2: Investigate Root Cause

**Find where the bug occurs:**
- Use grep/search to find related code
- Add instrumentation/logging to track execution
- Identify the specific code path causing the issue

**Questions to answer:**
- Where in the code does the failure occur?
- What is the sequence of events leading to failure?
- Is it platform-specific or cross-platform?

---

## Step 3: Design Fix Approach

**Before implementing, consider:**
- What is the minimal change needed?
- Will this affect other functionality?
- Are there platform-specific considerations?
- Does this require API changes?

**Present fix design to user:**

```markdown
## Fix Design - Issue #XXXXX

**Root Cause**: [Technical explanation of why the bug occurs]

**Proposed Fix**: [Description of the change]

**Files to Modify**:
- `src/path/to/file.cs` - [What will change]

**Risks/Considerations**:
- [Any potential side effects]

Proceed with implementation?
```

---

## Step 4: Implement Fix

**Make the code changes:**
- Modify the appropriate files in `src/Core/`, `src/Controls/`, or `src/Essentials/`
- Follow .NET MAUI coding conventions
- Add platform-specific code in correct folders if needed
- Add XML documentation for any new public APIs

**Key principles:**
- Keep changes minimal and focused
- Don't refactor unrelated code
- Follow existing code patterns

---

## Step 5: Verify Fix Works

**Run the reproduction test - it should now PASS:**

```bash
# For unit tests
pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests

# For UI tests
pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform [android|ios] -TestFilter "IssueXXXXX"
```

**Before fix:** Test FAILS ❌
**After fix:** Test PASSES ✅

---

## Step 6: Test Edge Cases

Consider and test:
- Null/empty values
- Boundary conditions
- Rapid state changes
- Different platforms
- Related functionality that might be affected

---

## Step 7: Submit PR

**PR Title Format:**
```
[Issue-Fix] Fix #XXXXX - [Brief Description]
```

**PR Description Template:**

```markdown
Fixes #XXXXX

> [!NOTE]
> Are you waiting for the changes in this PR to be merged?
> It would be very helpful if you could [test the resulting artifacts](https://github.com/dotnet/maui/wiki/Testing-PR-Builds) from this PR and let us know in a comment if this change resolves your issue. Thank you!

## Summary

[2-3 sentence description of the issue and fix]

## Root Cause

[Technical explanation of why the bug occurred]

## Solution

[Description of the fix]

## Testing

**Before fix:** Test fails
**After fix:** Test passes

**Test file**: [Path to reproduction test]
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Run unit tests | `pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests` |
| Run UI tests | `pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform [platform] -TestFilter "..."` |
| Format code | `dotnet format Microsoft.Maui.sln --no-restore` |
| Build verification | `pwsh .github/scripts/BuildAndVerify.ps1` |

---

## Common Fix Patterns

### Null Check
```csharp
if (handler is null) return;
```

### Property Change Guard
```csharp
if (_value == value) return;
_value = value;
OnPropertyChanged();
```

### Platform-Specific Code
```csharp
#if IOS || MACCATALYST
    // iOS-specific fix
#elif ANDROID
    // Android-specific fix
#elif WINDOWS
    // Windows-specific fix
#endif
```

### Lifecycle Cleanup
```csharp
protected override void DisconnectHandler(PlatformView platformView)
{
    platformView?.SomeEvent -= OnSomeEvent;
    base.DisconnectHandler(platformView);
}
```
