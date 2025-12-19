using NUnit.Framework;
using UITest.Appium;
using UITest.Core;

namespace Microsoft.Maui.TestCases.Tests.Issues;

public class Issue6995 : _IssuesUITest
{
	public Issue6995(TestDevice device) : base(device)
	{
	}

	public override string Issue => "[iOS] Modal FormSheet on iOS is currently not cancellable on Shell";

	[Test]
	[Category(UITestCategories.Shell)]
	public void ModalFormsheetDismissAttemptShouldBeDetectable()
	{
		// This test validates the bug: when a FormSheet modal is presented on iOS
		// with isModalInPresentation=true (preventing swipe-to-dismiss), 
		// attempting to swipe down should trigger a dismiss attempt event.
		// Currently, this event is NOT wired up in MAUI, so the test should FAIL.

		// Wait for the main page to load
		App.WaitForElement("OpenModalButton");

		// Open the FormSheet modal
		App.Tap("OpenModalButton");

		// Wait for the modal to appear
		App.WaitForElement("DismissAttemptLabel");

		// Verify initial state - no dismiss attempts yet
		var initialText = App.FindElement("DismissAttemptCountLabel").GetText();
		Assert.That(initialText, Does.Contain("Dismiss attempts: 0"), "Initial dismiss attempt count should be 0");

		// Now we need to simulate a swipe-down gesture to attempt to dismiss the modal
		// On iOS, when isModalInPresentation=true, the modal won't dismiss but the
		// presentationControllerDidAttemptToDismiss delegate method should be called
		
		// Get the modal's dismiss attempt label to swipe on it
		var dismissAttemptLabel = App.WaitForElement("DismissAttemptLabel");
		
		// Perform a swipe down gesture to attempt to dismiss the modal
		// This simulates a user trying to swipe down to dismiss the FormSheet
		App.ScrollDown("DismissAttemptLabel");

		// Wait a moment for the gesture to be processed
		Thread.Sleep(500);

		// Check if the dismiss attempt was detected
		// BUG: Currently this will still show "Dismiss attempts: 0" because
		// presentationControllerDidAttemptToDismiss is not wired up
		var afterSwipeText = App.FindElement("DismissAttemptCountLabel").GetText();
		
		// This assertion should PASS when the bug is fixed, but currently FAILS
		// because the dismiss attempt event is not being detected
		Assert.That(afterSwipeText, Does.Contain("Dismiss attempts: 1"), 
			"After swiping down on a non-dismissible FormSheet modal, the dismiss attempt should be detected. " +
			"This is failing because presentationControllerDidAttemptToDismiss is not wired up in MAUI.");

		// Clean up - close the modal
		App.Tap("CloseModalButton");

		// Wait for main page
		App.WaitForElement("OpenModalButton");
	}
}
