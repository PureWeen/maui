---
name: uitest-coding
description: Specialized skill for writing new UI tests for .NET MAUI with proper syntax, style, and conventions. Use this skill when the user asks to "write UI test for #XXXXX", "create UI tests", or "add test coverage".
license: MIT
metadata:
  version: "1.0"
  author: dotnet-maui-team
  repository: dotnet/maui
---

# UI Test Coding Skill

You are a specialized skill for writing high-quality UI tests for the .NET MAUI repository following established conventions and best practices.

## Purpose

Write new UI tests that:
- Follow .NET MAUI UI test conventions
- Are maintainable and clear
- Run reliably across platforms
- Actually test the stated behavior

## Quick Decision: Should You Use This Skill?

**YES, use this skill if:**
- User says "write a UI test for issue #XXXXX"
- User says "add test coverage for..."
- User says "create automated test for..."
- Need to write NEW test files

**NO, use different skill if:**
- "Test this PR" → use `sandbox-testing`
- "Review this PR" → use `pr-reviewer`
- "Investigate issue #XXXXX" → use `issue-resolver`
- Only need manual verification → use `sandbox-testing`

---

## 🚨 CRITICAL: Always Use BuildAndRunHostApp.ps1 Script

```bash
pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform [android|ios|maccatalyst] -TestFilter "IssueXXXXX"
```

---

## Two-Project Requirement

**CRITICAL**: Every UI test requires code in TWO projects:

1. **HostApp UI Test Page** (`src/Controls/tests/TestCases.HostApp/Issues/`)
   - XAML: `IssueXXXXX.xaml`
   - Code-behind: `IssueXXXXX.xaml.cs`
   - Contains actual UI that demonstrates/reproduces the issue

2. **NUnit Test** (`src/Controls/tests/TestCases.Shared.Tests/Tests/Issues/`)
   - Test file: `IssueXXXXX.cs`
   - Contains Appium-based automated test

---

## File Templates

This skill includes templates at `.github/skills/uitest-coding/templates/`:
- `IssueTemplate.xaml.template` - XAML page boilerplate
- `IssueTemplate.xaml.cs.template` - Code-behind boilerplate
- `IssueNUnitTest.cs.template` - NUnit test boilerplate

### HostApp XAML (`IssueXXXXX.xaml`)

```xml
<?xml version="1.0" encoding="utf-8" ?>
<ContentPage xmlns="http://schemas.microsoft.com/dotnet/2021/maui"
             xmlns:x="http://schemas.microsoft.com/winfx/2009/xaml"
             x:Class="Maui.Controls.Sample.Issues.IssueXXXXX"
             Title="Issue XXXXX - [Brief Description]">

    <StackLayout>
        <!-- Elements must have AutomationId for test automation -->
        <Button x:Name="TestButton"
                AutomationId="TestButton"
                Text="Trigger Action"
                Clicked="OnButtonClicked"/>
        
        <Label x:Name="ResultLabel"
               AutomationId="ResultLabel"
               Text="Initial State"/>
    </StackLayout>
</ContentPage>
```

### HostApp Code-Behind (`IssueXXXXX.xaml.cs`)

```csharp
using Microsoft.Maui.Controls;

namespace Maui.Controls.Sample.Issues;

// CRITICAL: Must have Issue attribute with ALL parameters
[Issue(IssueTracker.Github, XXXXX, "Brief description of the issue", PlatformAffected.All)]
public partial class IssueXXXXX : ContentPage
{
    public IssueXXXXX()
    {
        InitializeComponent();
    }

    private void OnButtonClicked(object sender, EventArgs e)
    {
        // Implement behavior that demonstrates the issue/fix
        ResultLabel.Text = "Action Completed";
    }
}
```

### NUnit Test (`IssueXXXXX.cs`)

```csharp
using NUnit.Framework;
using UITest.Appium;
using UITest.Core;

namespace Microsoft.Maui.TestCases.Tests.Issues
{
    public class IssueXXXXX : _IssuesUITest
    {
        public override string Issue => "Brief description of the issue";

        public IssueXXXXX(TestDevice device) : base(device) { }

        [Test]
        [Category(UITestCategories.Button)] // Use ONE category - the most specific
        public void DescriptiveTestMethodName()
        {
            // Wait for element to be ready
            App.WaitForElement("TestButton");

            // Interact with UI
            App.Tap("TestButton");

            // Verify expected behavior
            var result = App.FindElement("ResultLabel").GetText();
            Assert.That(result, Is.EqualTo("Action Completed"));
        }
    }
}
```

---

## Test Category Selection

**CRITICAL**: Use ONLY ONE `[Category]` attribute per test.

**Always check**: `src/Controls/tests/TestCases.Shared.Tests/UITestCategories.cs` for the authoritative list.

**Selection rule**: Choose the MOST SPECIFIC category that applies.

**Common categories** (examples):
- `UITestCategories.Button` - Button-specific tests
- `UITestCategories.Entry` - Entry-specific tests
- `UITestCategories.CollectionView` - CollectionView tests
- `UITestCategories.Layout` - Layout-related tests
- `UITestCategories.Navigation` - Navigation tests
- `UITestCategories.SafeAreaEdges` - SafeArea tests

---

## Platform Coverage Rules

**Default**: Tests should run on ALL platforms unless there's a technical reason.

**DO NOT use platform directives unless**:
- Platform-specific API is being tested
- Known limitation prevents test on a platform
- Platforms are expected to behave differently

```csharp
// ✅ Good: Runs everywhere
[Test]
[Category(UITestCategories.Button)]
public void ButtonClickWorks()
{
    App.WaitForElement("TestButton");
    App.Tap("TestButton");
}

// ❌ Bad: Unnecessarily limited
#if ANDROID
[Test]
[Category(UITestCategories.Button)]
public void ButtonClickWorks() { }
#endif
```

---

## AutomationId Requirements

**CRITICAL**: Every interactive element MUST have an `AutomationId`.

```xml
<!-- ✅ Good -->
<Button AutomationId="SaveButton" Text="Save"/>
<Entry AutomationId="UsernameEntry"/>
<Label AutomationId="StatusLabel"/>

<!-- ❌ Bad: Missing AutomationId -->
<Button Text="Save"/>
<Entry/>
<Label/>
```

---

## Common Test Patterns

### Basic Interaction Test
```csharp
[Test]
[Category(UITestCategories.Button)]
public void ButtonClickUpdatesLabel()
{
    App.WaitForElement("TestButton");
    App.Tap("TestButton");
    
    var labelText = App.FindElement("ResultLabel").GetText();
    Assert.That(labelText, Is.EqualTo("Clicked"));
}
```

### Navigation Test
```csharp
[Test]
[Category(UITestCategories.Navigation)]
public void NavigationDoesNotCrash()
{
    App.WaitForElement("NavigateButton");
    App.Tap("NavigateButton");
    
    // Wait for new page
    App.WaitForElement("BackButton");
    
    Assert.Pass("Navigation completed without crash");
}
```

### Layout Measurement Test
```csharp
[Test]
[Category(UITestCategories.Layout)]
public void ElementHasCorrectSize()
{
    App.WaitForElement("TestElement");
    
    var rect = App.FindElement("TestElement").GetRect();
    
    Assert.That(rect.Width, Is.GreaterThan(0));
    Assert.That(rect.Height, Is.GreaterThan(0));
}
```

---

## Best Practices

### 1. Always Wait Before Interacting
```csharp
// ✅ Good
App.WaitForElement("TestButton");
App.Tap("TestButton");

// ❌ Bad: May fail if element not ready
App.Tap("TestButton");
```

### 2. Use Descriptive Names
```csharp
// ✅ Good
public void ButtonClickUpdatesLabelText() { }

// ❌ Bad
public void Test1() { }
```

### 3. Add Meaningful Assertions
```csharp
// ✅ Good: Verifies behavior
Assert.That(result, Is.EqualTo("Expected"));

// ❌ Bad: Empty test
App.Tap("TestButton");
// No verification
```

---

## Checklist Before Committing

- [ ] Two files created (XAML + NUnit test)
- [ ] File names match: `IssueXXXXX`
- [ ] `[Issue()]` attribute present with all parameters
- [ ] Inherits from `_IssuesUITest`
- [ ] ONE `[Category]` attribute from UITestCategories
- [ ] All interactive elements have `AutomationId`
- [ ] Test uses `App.WaitForElement()` before interactions
- [ ] Test has meaningful assertions
- [ ] Test method name is descriptive
- [ ] No unnecessary platform directives
- [ ] Compiled both HostApp and test projects
- [ ] Ran test locally and verified it passes

---

## Running Tests

```bash
# Default: Android
pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform android -TestFilter "IssueXXXXX"

# Or iOS
pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform ios -TestFilter "IssueXXXXX"

# Run by category
pwsh .github/scripts/BuildAndRunHostApp.ps1 -Platform android -Category "Button"
```

---

## Verification on Linux Without Device Access

If you cannot run BuildAndRunHostApp due to OS limitations:

```bash
# Verify test code compiles and run unit tests
pwsh .github/scripts/BuildAndVerify.ps1 -RunUnitTests
```

**Report to user:**
```markdown
⚠️ **Test Created - Compilation Verified**

**Files created:**
- `TestCases.HostApp/Issues/IssueXXXXX.xaml[.cs]`
- `TestCases.Shared.Tests/Tests/Issues/IssueXXXXX.cs`

**Verification status:**
- ✅ Test code compiles successfully
- ❌ UI test NOT executed (requires device/simulator)

**Recommended**: UI test execution on platform with device access.
```

---

## Troubleshooting

**Test Won't Compile**:
- Check namespace: `Microsoft.Maui.TestCases.Tests.Issues`
- Verify base class: `_IssuesUITest`
- Ensure constructor: `public IssueXXXXX(TestDevice device) : base(device) { }`

**Element Not Found**:
🚨 **Check device logs first - app may have crashed!**
1. Check logs for crashes
2. Verify AutomationId exists in XAML
3. Ensure [Issue] attribute is present

**Test Flaky**:
- Add appropriate waits with `App.WaitForElement()`
- Don't rely on fixed sleeps

---

## External References

- [uitests.instructions.md](../../instructions/uitests.instructions.md) - Full UI test documentation
- [UITestCategories.cs](../../../src/Controls/tests/TestCases.Shared.Tests/UITestCategories.cs) - All available categories
