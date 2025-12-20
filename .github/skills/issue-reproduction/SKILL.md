---
name: issue-reproduction
description: >
  Create reproduction tests for .NET MAUI issues. Use this skill when asked to 
  "fix issue #XXXXX", "investigate issue", "reproduce bug", or "work on issue #XXXXX".
  This skill creates tests that prove the bug exists - it does NOT implement fixes.
  After reproduction is confirmed, invoke the issue-fix skill to implement the solution.
license: MIT
metadata:
  version: "1.0"
  author: dotnet-maui-team
  repository: dotnet/maui
---

# Issue Reproduction Skill

You are a specialized reproduction testing skill for the .NET MAUI repository. Your role is to create tests that prove a reported bug exists.

## When to Use This Skill

- ✅ "Fix issue #12345" - Start here, create reproduction first
- ✅ "Investigate issue #XXXXX"
- ✅ "Reproduce bug #XXXXX"
- ✅ "Work on issue #XXXXX"

## When NOT to Use This Skill

- ❌ "Proceed with fix" or "implement the fix" → Use `issue-fix` skill
- ❌ "Test this PR" → Use `pr-reviewer` skill
- ❌ "Write UI tests" (not for a bug) → Use `uitest-coding` skill

---

## 🛑 CRITICAL: This Skill Does NOT Fix Issues

**This skill ONLY:**
1. Reads and understands the issue
2. Creates a reproduction test that FAILS (proving the bug exists)
3. Verifies the test actually reproduces the issue
4. Stops and waits for user to invoke `issue-fix` skill

**This skill NEVER:**
- Implements fixes to source code
- Modifies handler code, control code, or platform code
- Creates PRs with fixes

---

## Workflow

```
1. Fetch issue - read description and ALL comments
2. Create initial assessment - show user before starting
3. Create reproduction test - unit test (preferred) or UI test
4. Run test and verify it FAILS (proves bug exists)
5. 🛑 STOP - Report reproduction complete, wait for user to invoke issue-fix skill
```

---

## Step 1: Fetch Issue

```bash
# Fetch GitHub issue
ISSUE_NUM=XXXXX  # Replace with actual number
echo "Fetching: https://github.com/dotnet/maui/issues/$ISSUE_NUM"
```

**Read thoroughly:**
- Issue description
- ALL comments (additional details, workarounds, platform info)
- Screenshots/code samples
- Affected platforms (iOS, Android, Windows, Mac, All)

---

## Step 2: Create Initial Assessment

**Before starting any work, show user this assessment:**

```markdown
## Issue Reproduction Assessment - Issue #XXXXX

**Issue Summary**: [Brief description of reported problem]

**Affected Platforms**: [iOS/Android/Windows/Mac/All]

**Reproduction Strategy**:
- **Type**: [Unit test (preferred) | UI test (if UI interaction required)]
- **Location**: [Test project and file path]
- **Scenario**: [What the test will verify]

**Expected Outcome**: Test should FAIL, proving the bug exists.

Any concerns about this approach?
```

---

## Step 3: Create Reproduction Test

### Prefer Unit Tests (Faster)

**Location**: `src/Controls/tests/Core.UnitTests/` or similar

```csharp
// Example: src/Controls/tests/Core.UnitTests/IssueXXXXXTests.cs
namespace Microsoft.Maui.Controls.Core.UnitTests;

[TestFixture]
public class IssueXXXXXTests : BaseTestFixture
{
    [Test]
    public void IssueXXXXX_ReproducesBug()
    {
        // Arrange: Set up the scenario from the issue
        var control = new MyControl { Property = InitialValue };

        // Act: Perform action that triggers the bug
        control.Property = NewValue;

        // Assert: Verify the buggy behavior occurs
        // This assertion should FAIL without the fix
        Assert.That(control.ActualBehavior, Is.EqualTo(ExpectedBehavior));
    }
}
```

### Fall Back to UI Tests (When Needed)

Use UI tests only when:
- Issue requires visual layout verification
- Issue involves gestures or user interaction
- Issue is handler-specific (handlers always need UI tests)

**Locations:**
- Test page: `src/Controls/tests/TestCases.HostApp/Issues/IssueXXXXX.xaml[.cs]`
- NUnit test: `src/Controls/tests/TestCases.Shared.Tests/Tests/Issues/IssueXXXXX.cs`

---

## Step 4: Run Test and Verify Reproduction

**For unit tests:**
```bash
pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests
```

**For UI tests:**
```bash
pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform [android|ios] -TestFilter "IssueXXXXX"
```

**Expected result:** Test should **FAIL**, proving the bug exists.

If test passes, the reproduction is incorrect - revise and try again.

---

## Step 5: 🛑 STOP - Report Completion

**After confirming reproduction, present this summary:**

```markdown
## ✅ Reproduction Complete - Issue #XXXXX

**Test Created**: [File path]

**Test Validates**: [What behavior the test checks]

**Reproduction Confirmed**: ✅ Test FAILS, proving the bug exists

**Test Output**:
```
[Show failing test output]
```

---

**Next Step**: To proceed with implementing the fix, invoke the `issue-fix` skill:
> "Proceed with fix for issue #XXXXX"

**IMPORTANT**: This skill does NOT implement fixes. The reproduction is complete.
```

**DO NOT proceed to implementing the fix.** Wait for user to invoke `issue-fix` skill.

---

## Quick Reference

| Task | Command |
|------|---------|
| Run unit tests | `pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests` |
| Run UI tests | `pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform [platform] -TestFilter "..."` |
| Unit test location | `src/Controls/tests/Core.UnitTests/` |
| UI test HostApp | `src/Controls/tests/TestCases.HostApp/Issues/` |
| UI test NUnit | `src/Controls/tests/TestCases.Shared.Tests/Tests/Issues/` |
