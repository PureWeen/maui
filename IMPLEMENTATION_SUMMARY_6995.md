# Implementation Summary: Issue #6995

## Overview
This implementation adds support for cancellable FormSheet modals on iOS by wiring into the `UIAdaptivePresentationControllerDelegate` methods.

## Issue
[iOS] Modal Formsheet on iOS is currently not cancellable on Shell
- GitHub Issue: https://github.com/dotnet/maui/issues/6995
- Platform: iOS/MacCatalyst only

## Solution
Added a new `ModalDismissAttempted` event to the `Page` class that allows developers to cancel modal dismissals.

## Changes Made

### 1. New Event Arguments Class
**File**: `src/Controls/src/Core/Page/ModalDismissAttemptedEventArgs.cs`

```csharp
public sealed class ModalDismissAttemptedEventArgs : EventArgs
{
    public bool Cancel { get; set; }
}
```

### 2. New Event on Page Class
**File**: `src/Controls/src/Core/Page/Page.cs`

- Added `ModalDismissAttempted` event
- Added `OnModalDismissAttempted` protected virtual method
- Added `SendModalDismissAttempted` internal method

### 3. iOS Implementation
**File**: `src/Controls/src/Core/Platform/iOS/ControlsModalWrapper.cs`

- Implemented `presentationControllerShouldDismiss:` delegate method (primary)
- Implemented `presentationControllerDidAttemptToDismiss:` delegate method (for future use)

The `ShouldDismiss` method:
1. Raises the `ModalDismissAttempted` event on the page
2. Returns `!args.Cancel` to iOS (if Cancel is true, dismissal is prevented)

### 4. Test Implementation
**Files**:
- `src/Controls/tests/TestCases.HostApp/Issues/Issue6995.xaml`
- `src/Controls/tests/TestCases.HostApp/Issues/Issue6995.xaml.cs`
- `src/Controls/tests/TestCases.Shared.Tests/Tests/Issues/Issue6995.cs`

The test demonstrates:
- Creating a FormSheet modal
- Handling the `ModalDismissAttempted` event
- Canceling the first dismissal attempt
- Allowing dismissal on the second attempt

### 5. Public API Updates
Updated `PublicAPI.Unshipped.txt` files for all platforms with:
- `ModalDismissAttemptedEventArgs` class
- `ModalDismissAttemptedEventArgs.Cancel` property
- `Page.ModalDismissAttempted` event
- `Page.OnModalDismissAttempted` method

## Usage Example

```csharp
var modalPage = new ContentPage();

// Set the modal presentation style to FormSheet (iOS-specific)
modalPage.On<iOS>()
    .SetModalPresentationStyle(UIModalPresentationStyle.FormSheet);

// Subscribe to the ModalDismissAttempted event
modalPage.ModalDismissAttempted += (sender, args) =>
{
    // Optionally prevent the dismissal
    if (/* some condition */)
    {
        args.Cancel = true;
        // You can also show an alert or other UI here
    }
};

await Navigation.PushModalAsync(modalPage);
```

## How It Works

### iOS Delegate Methods
1. **`presentationControllerShouldDismiss:`** - Called before dismissal begins
   - Returns `true` to allow dismissal, `false` to prevent it
   - We raise the `ModalDismissAttempted` event here and return `!args.Cancel`

2. **`presentationControllerDidAttemptToDismiss:`** - Called when dismissal is prevented
   - Currently a placeholder for future enhancements (e.g., showing alerts)

### Event Flow
1. User swipes down on a FormSheet modal (or taps outside on iPad)
2. iOS calls `ShouldDismiss` on our delegate
3. We raise the `ModalDismissAttempted` event
4. Developer's event handler sets `args.Cancel = true` (or false)
5. We return `!args.Cancel` to iOS
6. If we returned `false`, iOS prevents dismissal and calls `DidAttemptToDismiss`
7. If we returned `true`, iOS proceeds with dismissal and later calls `DidDismiss`

## Platform Support
- **iOS 13+**: Full support (presentation controller delegate methods)
- **MacCatalyst 13+**: Full support (same as iOS)
- **Other platforms**: Event is available but not triggered (no gesture dismissal on Android/Windows)

## Testing Notes
The UI test validates that:
1. The modal can be shown with FormSheet presentation style
2. The event infrastructure is properly wired up
3. The modal can be dismissed programmatically

Manual testing on an iOS device is recommended to verify the swipe-to-dismiss cancellation behavior.

## Related Apple Documentation
- [UIAdaptivePresentationControllerDelegate](https://developer.apple.com/documentation/uikit/uiadaptivepresentationcontrollerdelegate)
- [presentationControllerShouldDismiss:](https://developer.apple.com/documentation/uikit/uiadaptivepresentationcontrollerdelegate/3229889-presentationcontrollershoulddi)
- [presentationControllerDidAttemptToDismiss:](https://developer.apple.com/documentation/uikit/uiadaptivepresentationcontrollerdelegate/3229888-presentationcontrollerdidattempt)

## Breaking Changes
None. This is a new feature that adds API surface without modifying existing behavior.
