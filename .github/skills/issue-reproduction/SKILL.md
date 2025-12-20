---
name: issue-reproduction
description: >
  Creates failing tests that reproduce .NET MAUI issues. Use when creating reproduction tests,
  when asked to "reproduce bug", "create reproduction test", or when no test exists for an issue.
  This skill provides detailed test creation methodology - it does NOT implement fixes.
license: MIT
metadata:
  version: "1.0"
  author: dotnet-maui-team
  repository: dotnet/maui
---

# Issue Reproduction Skill

You are a specialized reproduction testing skill for the .NET MAUI repository. Your role is to create tests that prove a reported bug exists.

## Purpose

This skill provides **detailed domain knowledge** for creating reproduction tests:
- Test file locations and naming conventions
- Unit test vs UI test decision rules
- Test patterns and templates
- Build and run commands
- Success criteria (test must FAIL)

## 🛑 CRITICAL: This Skill Does NOT Fix Issues

**This skill ONLY:**
1. Creates a reproduction test that FAILS (proving the bug exists)
2. Verifies the test actually reproduces the issue
3. Reports completion and waits for fix phase

**This skill NEVER:**
- Implements fixes to source code
- Modifies handler code, control code, or platform code

---

## Workflow

```
1. Understand the issue (from context provided)
2. Decide test type - unit test (preferred) or UI test
3. Create reproduction test following conventions
4. Run test and verify it FAILS (proves bug exists)
5. Report reproduction complete
```

---

## Step 1: Decide Test Type

### 🎯 CRITICAL: Apply Testing Strategy Rules

**Before choosing test type, read and apply**: `.github/instructions/testing-strategy.instructions.md`

**Primary Rule: Prefer Unit Tests**

Unit tests are the default choice because they are:
- ⚡ Faster to run
- 🔄 Faster to iterate
- 💻 No device/simulator required
- ✅ Cross-platform by default

**Use unit tests for:**
- Property binding issues
- Data converter problems
- XAML parsing/inflation issues
- Collection manipulation bugs
- Event handler logic issues
- Non-visual behavior bugs

**Use UI tests for:**
- Visual layout/rendering issues
- Gestures and touch handling
- Platform-specific UI behavior
- **Handler code (ALWAYS)** - handlers require device validation
- Accessibility features
- Navigation behavior

### Handler Detection

**How to identify handler code** (always requires UI tests):
- Files in `/Handlers/` directories
- Classes ending with `Handler` (e.g., `ButtonHandler`, `EntryHandler`)
- Platform-specific implementations in `Platform/Android/`, `Platform/iOS/`, etc.
- Code involving `PlatformView`, `MauiContext`, or native view manipulation

### Unit Test (Preferred)

**When to use**: Property binding, data converters, XAML parsing, collection issues, logic bugs

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

### UI Test (When Handler or UI Required)

**When to use**:
- Handler-related issues (always UI tests)
- Visual layout/rendering
- Gestures or user interaction
- Platform-specific UI behavior

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
