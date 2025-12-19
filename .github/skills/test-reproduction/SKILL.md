---
name: test-reproduction
description: Specialized skill for creating reproduction tests for .NET MAUI issues. Use this skill when the user asks to "create a reproduction test for issue #XXXXX" or "write a test that reproduces #XXXXX". This skill does NOT fix issues - it only creates tests that prove bugs exist.
license: MIT
metadata:
  version: "1.0"
  author: dotnet-maui-team
  repository: dotnet/maui
---

# .NET MAUI Test Reproduction Skill

You are a specialized test creation skill for the .NET MAUI repository. Your **ONLY** role is to create tests that reproduce reported issues. You do NOT fix issues.

## When to Use This Skill

- ✅ "Create a reproduction test for issue #12345"
- ✅ "Write a test that reproduces #67890"
- ✅ "Create a repro for the bug reported in #XXXXX"

## When NOT to Use This Skill

- ❌ "Fix issue #12345" → Use `issue-resolver` skill
- ❌ "Test this PR" or "validate PR #XXXXX" → Use `pr-reviewer` or `sandbox-testing`
- ❌ "Write UI tests" for a feature (not a bug) → Use `uitest-coding`
- ❌ Discussing or analyzing issue without creating test → Analyze directly, no skill needed

**Critical**: This skill creates reproduction tests ONLY. It does NOT implement fixes or solutions.

---

## Core Workflow

```
1. Fetch issue - read description and ALL comments
2. Create assessment - show strategy before starting
3. Create reproduction test - prioritize unit tests, fallback to UI tests
4. Validate test reproduces bug - confirm test FAILS without fix
5. Report results - show test code, confirm reproduction, exit
```

**This skill stops after creating the reproduction test.** It does NOT proceed to fixing the issue.

---

## Step 1: Fetch Issue

The developer MUST provide the issue number in their prompt.

**Read thoroughly**:
- Issue description
- ALL comments (additional details, workarounds, platform info)
- Screenshots/code samples
- Reproduction steps provided by reporter

**Extract key details**:
- Affected platforms (iOS, Android, Windows, Mac, All)
- Minimum reproduction steps
- Expected vs actual behavior
- Code samples or scenarios from issue

---

## Step 2: Create Assessment

**Before starting any work, show user this assessment:**

```markdown
## Test Reproduction Assessment - Issue #XXXXX

**Issue Summary**: [Brief description of reported problem]

**Affected Platforms**: [iOS/Android/Windows/Mac/All]

**Reproduction Strategy**:
- **Type**: [Unit test (preferred) | UI test (if UI interaction required)]
- **Reason**: [Why this test type]
- **Location**: [Specify test project and file path]
- **Scenario**: [What the test will do to reproduce the bug]

**Expected Outcome**: Test should FAIL, demonstrating the bug exists.

Any concerns about this approach?
```

**Wait for user response before continuing.**

---

## Step 3: Create Reproduction Test

### Test Strategy - Prioritize Unit Tests

**🎯 Prefer unit tests when possible** (faster to run and iterate):
- **Location**: `src/Controls/tests/Core.UnitTests/`, `src/Controls/tests/Xaml.UnitTests/`
- **Use when**: Testing logic, property changes, XAML parsing, non-UI behavior
- **Handlers always require UI tests** (not unit tests)
- **Run with**: `pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests`

**Fall back to UI tests when needed** (requires UI interaction):
- **Location**: `src/Controls/tests/TestCases.HostApp/Issues/` + `src/Controls/tests/TestCases.Shared.Tests/Tests/Issues/`
- **Use when**: Testing visual layout, gestures, platform-specific UI rendering, handler behavior

### Unit Test Template

```csharp
// Location: src/Controls/tests/Core.UnitTests/IssueXXXXXTests.cs
namespace Microsoft.Maui.Controls.Core.UnitTests;

[TestFixture]
public class IssueXXXXXTests : BaseTestFixture
{
    [Test]
    public void IssueXXXXX_ReproducesBug()
    {
        // Arrange: Set up the scenario that triggers the issue
        var control = new MyControl { Property = InitialValue };

        // Act: Perform the action that causes the bug
        control.Property = NewValue;

        // Assert: Verify the bug occurs (test should FAIL without fix)
        Assert.That(control.ActualBehavior, Is.EqualTo(BuggyBehavior));
    }
}
```

### UI Test Template

**HostApp Page** (`src/Controls/tests/TestCases.HostApp/Issues/IssueXXXXX.xaml.cs`):
```csharp
namespace Maui.Controls.Sample.Issues;

[Issue(IssueTracker.Github, XXXXX, "Brief description", PlatformAffected.All)]
public partial class IssueXXXXX : ContentPage
{
    public IssueXXXXX()
    {
        InitializeComponent();
    }
    
    private void OnTriggerBug(object sender, EventArgs e)
    {
        // Code that reproduces the issue
        ResultLabel.Text = "Bug reproduced";
    }
}
```

**NUnit Test** (`src/Controls/tests/TestCases.Shared.Tests/Tests/Issues/IssueXXXXX.cs`):
```csharp
namespace Microsoft.Maui.TestCases.Tests.Issues;

public class IssueXXXXX : _IssuesUITest
{
    public override string Issue => "Brief description of the bug";

    public IssueXXXXX(TestDevice device) : base(device) { }

    [Test]
    [Category(UITestCategories.YourCategory)]
    public void IssueXXXXX_ReproducesBug()
    {
        App.WaitForElement("TriggerButton");
        App.Tap("TriggerButton");
        
        var result = App.FindElement("ResultLabel").GetText();
        Assert.That(result, Is.EqualTo("Expected behavior but bug shows different"));
    }
}
```

---

## Step 4: Validate Test Reproduces Bug

**Run the test and confirm it FAILS** (proving the bug exists):

```bash
# For unit tests
pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests

# For UI tests
pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform android -TestFilter "IssueXXXXX"
```

**Expected result**: Test should FAIL with output showing the bug behavior.

**If test passes**: The test doesn't reproduce the issue correctly. Revise and retest.

---

## Step 5: Report Results

After creating and validating the reproduction test, provide this summary:

```markdown
## Reproduction Test Created - Issue #XXXXX

**Test Type**: [Unit test | UI test]

**Location**:
- [File path(s) to test code]

**Test Validates**: [Brief description of what test checks]

**Reproduction Confirmed**: ✅ Test FAILS, demonstrating the bug exists

**Test Execution**:
```bash
[Command used to run the test]
```

**Next Steps**: 
- Test is ready for use in issue resolution
- To fix this issue, use the `issue-resolver` skill with this test as the reproduction baseline

**IMPORTANT**: This skill does NOT implement fixes. The reproduction test is complete and validated.
```

**DO NOT proceed to fixing the issue.** Stop here.

---

## What This Skill Does NOT Do

- ❌ Design or implement bug fixes
- ❌ Investigate root causes beyond what's needed for reproduction
- ❌ Create PRs or commit fixes
- ❌ Modify production code (only creates test code)
- ❌ Run extensive debugging sessions

**This skill's sole purpose**: Create a test that proves the bug exists. That's it.

---

## Common Mistakes to Avoid

1. ❌ **Implementing a fix** - This skill only creates reproduction tests
2. ❌ **Creating tests that pass immediately** - Reproduction tests should FAIL
3. ❌ **Using Sandbox app** - Always use TestCases.HostApp for UI tests
4. ❌ **Creating UI test when unit test would work** - Prefer unit tests
5. ❌ **Not validating test actually reproduces bug** - Always run and confirm it fails
6. ❌ **Creating tests without `AutomationId`** - UI tests need AutomationIds
7. ❌ **Forgetting `[Issue]` attribute** - HostApp pages need Issue attribute

---

## Quick Reference

| Task | Command |
|------|---------|
| **Run unit test** | `pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests` |
| **Run UI test (Android)** | `pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform android -TestFilter "IssueXXXXX"` |
| **Run UI test (iOS)** | `pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform ios -TestFilter "IssueXXXXX"` |
