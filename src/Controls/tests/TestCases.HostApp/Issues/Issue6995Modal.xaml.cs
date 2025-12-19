namespace Maui.Controls.Sample.Issues;

public partial class Issue6995Modal : ContentPage
{
	int _dismissAttemptCount = 0;

	public Issue6995Modal()
	{
		InitializeComponent();
	}

#if IOS || MACCATALYST
	protected override void OnHandlerChanged()
	{
		base.OnHandlerChanged();

		if (Handler?.PlatformView is UIKit.UIView view)
		{
			// Get the parent view controller
			var viewController = view.FindViewController();
			if (viewController != null)
			{
				// Set isModalInPresentation to true to prevent swipe-to-dismiss
				// This means swiping down will NOT dismiss the modal, but will trigger
				// presentationControllerDidAttemptToDismiss (which is the bug - this event isn't wired up)
				viewController.ModalInPresentation = true;
			}
		}
	}
#endif

	/// <summary>
	/// This method should be called when a dismiss attempt is detected.
	/// Currently, this is NOT being called because the presentationControllerDidAttemptToDismiss
	/// delegate method is not wired up in MAUI's ControlsModalWrapper.
	/// </summary>
	public void OnDismissAttempted()
	{
		_dismissAttemptCount++;
		DismissAttemptLabel.Text = "Dismiss attempt DETECTED!";
		DismissAttemptLabel.TextColor = Colors.Green;
		DismissAttemptCountLabel.Text = $"Dismiss attempts: {_dismissAttemptCount}";
	}

	async void OnCloseModalClicked(object sender, EventArgs e)
	{
		await Navigation.PopModalAsync();
	}
}

#if IOS || MACCATALYST
file static class Issue6995ViewExtensions
{
	public static UIKit.UIViewController? FindViewController(this UIKit.UIView view)
	{
		var responder = view.NextResponder;
		while (responder != null)
		{
			if (responder is UIKit.UIViewController vc)
				return vc;
			responder = responder.NextResponder;
		}
		return null;
	}
}
#endif
