---
description: "Test strategy rules for .NET MAUI - when to use unit tests vs UI tests"
applyTo: "src/Controls/tests/**,src/Core/tests/**,src/Essentials/test/**"
---

# .NET MAUI Testing Strategy

This document defines the rules for choosing between unit tests and UI tests when working with the .NET MAUI repository.

## 🎯 Primary Rule: Prefer Unit Tests

**Unit tests are the default choice** because they are:
- ⚡ Faster to run
- 🔄 Faster to iterate
- 💻 No device/simulator required
- ✅ Cross-platform by default

**Fall back to UI tests only when necessary.**

---

## When to Use Unit Tests

**Use unit tests for:**
- Property binding issues
- Data converter problems
- XAML parsing/inflation issues
- Collection manipulation bugs
- Event handler logic issues
- Non-visual behavior bugs
- State management issues
- Method/function logic validation

**Unit test locations:**
- `src/Controls/tests/Core.UnitTests/` - Core controls logic
- `src/Controls/tests/Xaml.UnitTests/` - XAML parsing
- `src/Essentials/test/UnitTests/` - Essentials APIs
- `src/Core/tests/UnitTests/` - Core framework

**Run command:**
```bash
pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests
```

---

## When to Use UI Tests

**Use UI tests for:**
- Visual layout/rendering issues
- Gestures and touch handling
- Platform-specific UI behavior
- **Handler code** (handlers ALWAYS require UI tests)
- Accessibility features
- Navigation behavior
- Animations and transitions
- Focus/keyboard handling

**🚨 Handler Rule:**
> Handlers are platform-specific implementations that bridge .NET controls to native views. 
> They ALWAYS require UI tests because they need actual device/simulator execution.
> Never use unit tests for handler validation.

**UI test locations:**
- `src/Controls/tests/TestCases.HostApp/Issues/` - Test page (XAML + code-behind)
- `src/Controls/tests/TestCases.Shared.Tests/Tests/Issues/` - NUnit test

**Run command:**
```bash
pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform [android|ios|maccatalyst] -TestFilter "IssueXXXXX"
```

---

## Decision Flowchart

```
Is this testing a Handler?
├── YES → UI Test (always)
└── NO
    ├── Does it require visual rendering?
    │   ├── YES → UI Test
    │   └── NO
    │       ├── Does it require gestures/touch?
    │       │   ├── YES → UI Test
    │       │   └── NO
    │       │       ├── Does it require platform-specific UI?
    │       │       │   ├── YES → UI Test
    │       │       │   └── NO → Unit Test ✓
```

---

## Handler Detection

**How to identify handler code:**
- Files in `/Handlers/` directories
- Classes ending with `Handler` (e.g., `ButtonHandler`, `EntryHandler`)
- Platform-specific implementations in `Platform/Android/`, `Platform/iOS/`, etc.
- Code involving `PlatformView`, `MauiContext`, or native view manipulation

**Examples of handler-related issues:**
- "Button click event not firing on Android" → UI Test (handler behavior)
- "Entry placeholder color wrong on iOS" → UI Test (handler styling)
- "CollectionView scrolling issue" → UI Test (handler scroll behavior)

---

## Unit Test Structure

```csharp
// Location: src/Controls/tests/Core.UnitTests/IssueXXXXXTests.cs
namespace Microsoft.Maui.Controls.Core.UnitTests;

[TestFixture]
public class IssueXXXXXTests : BaseTestFixture
{
    [Test]
    public void IssueXXXXX_ReproducesBug()
    {
        // Arrange: Set up the scenario
        var control = new MyControl { Property = InitialValue };

        // Act: Perform the action
        control.Property = NewValue;

        // Assert: Verify expected behavior
        Assert.That(control.ActualBehavior, Is.EqualTo(ExpectedBehavior));
    }
}
```

---

## UI Test Structure

**HostApp Page** (`TestCases.HostApp/Issues/IssueXXXXX.xaml.cs`):
```csharp
namespace Maui.Controls.Sample.Issues;

[Issue(IssueTracker.Github, XXXXX, "Brief description", PlatformAffected.All)]
public partial class IssueXXXXX : ContentPage
{
    public IssueXXXXX() { InitializeComponent(); }
}
```

**NUnit Test** (`TestCases.Shared.Tests/Tests/Issues/IssueXXXXX.cs`):
```csharp
namespace Microsoft.Maui.TestCases.Tests.Issues;

public class IssueXXXXX : _IssuesUITest
{
    public override string Issue => "Brief description";
    
    public IssueXXXXX(TestDevice device) : base(device) { }

    [Test]
    [Category(UITestCategories.Button)]  // Use appropriate category
    public void ValidateBugIsFixed()
    {
        App.WaitForElement("AutomationId");
        App.Tap("TriggerButton");
        var result = App.FindElement("ResultLabel").GetText();
        Assert.That(result, Is.EqualTo("Expected"));
    }
}
```

---

## Common Mistakes to Avoid

| ❌ Don't | ✅ Do |
|---------|------|
| Use UI test for property binding logic | Use unit test |
| Use unit test for handler code | Use UI test |
| Create tests that pass immediately | Create tests that fail (reproducing bug) |
| Use Sandbox app for test validation | Use TestCases.HostApp |
| Forget AutomationId on elements | Add AutomationId to all interactive elements |
| Forget `[Issue]` attribute | Include tracker, number, and description |

---

## Platform Limitations

| Platform | Unit Tests | UI Tests |
|----------|-----------|----------|
| Linux | ✅ All platforms | ⚠️ Android only |
| macOS | ✅ All platforms | ✅ All platforms |
| Windows | ✅ All platforms | ✅ Windows + Android |

**If testing iOS on Linux:** Note the limitation and focus on Android. UI test code will still compile and be ready for iOS testing by others.

---

## Quick Reference

| Test Type | Location | Run Command |
|-----------|----------|-------------|
| Unit test | `Core.UnitTests/`, `Xaml.UnitTests/` | `pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests` |
| UI test (HostApp) | `TestCases.HostApp/Issues/` | N/A (pages only) |
| UI test (NUnit) | `TestCases.Shared.Tests/Tests/Issues/` | `pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform [platform] -TestFilter "..."` |
