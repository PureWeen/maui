using System;
using Microsoft.Maui.Controls;
using Microsoft.Maui.Controls.Xaml;

namespace Maui.Controls.Sample.Issues
{
	[XamlCompilation(XamlCompilationOptions.Compile)]
	[Issue(IssueTracker.Github, 6995, "[iOS] Modal Formsheet on iOS is currently not cancellable on Shell", PlatformAffected.iOS)]
	public partial class Issue6995 : ContentPage
	{
		private int _dismissAttemptCount = 0;

		public Issue6995()
		{
			InitializeComponent();
		}

		private async void OnShowModalClicked(object sender, EventArgs e)
		{
			var modalPage = new FormSheetModalPage();
			
			// Subscribe to the ModalDismissAttempted event
			modalPage.ModalDismissAttempted += (s, args) =>
			{
				_dismissAttemptCount++;
				DismissAttemptLabel.Text = $"Dismiss attempts: {_dismissAttemptCount}";
				
				// For testing, we'll allow dismissal after 2 attempts
				if (_dismissAttemptCount < 2)
				{
					args.Cancel = true;
				}
			};

#if IOS || MACCATALYST
			// Set the modal presentation style to FormSheet
			modalPage.On<Microsoft.Maui.Controls.PlatformConfiguration.iOS>()
				.SetModalPresentationStyle(Microsoft.Maui.Controls.PlatformConfiguration.iOSSpecific.UIModalPresentationStyle.FormSheet);
#endif

			await Navigation.PushModalAsync(modalPage);
		}
	}

	public class FormSheetModalPage : ContentPage
	{
		public FormSheetModalPage()
		{
			Title = "FormSheet Modal";
			
			var layout = new StackLayout
			{
				Padding = 20,
				Spacing = 10
			};

			layout.Children.Add(new Label
			{
				Text = "Try to dismiss this modal by swiping down",
				AutomationId = "ModalInstructionLabel"
			});

			layout.Children.Add(new Label
			{
				Text = "First attempt will be cancelled",
				AutomationId = "ModalHintLabel"
			});

			layout.Children.Add(new Button
			{
				Text = "Close Modal",
				AutomationId = "CloseModalButton",
				Command = new Command(async () => await Navigation.PopModalAsync())
			});

			Content = layout;
		}
	}
}
