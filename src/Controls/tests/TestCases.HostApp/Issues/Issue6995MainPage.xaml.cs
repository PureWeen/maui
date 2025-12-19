using Microsoft.Maui.Controls.PlatformConfiguration;
using Microsoft.Maui.Controls.PlatformConfiguration.iOSSpecific;

namespace Maui.Controls.Sample.Issues;

public partial class Issue6995MainPage : ContentPage
{
	public Issue6995MainPage()
	{
		InitializeComponent();
	}

	async void OnOpenModalClicked(object sender, EventArgs e)
	{
		ResultLabel.Text = "Opening modal...";
		
		var modalPage = new Issue6995Modal();
		
		// Set FormSheet presentation style on iOS
		modalPage.On<iOS>().SetModalPresentationStyle(UIModalPresentationStyle.FormSheet);
		
		await Navigation.PushModalAsync(modalPage);
		
		ResultLabel.Text = "Modal was closed";
	}
}
