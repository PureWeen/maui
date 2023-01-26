using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.Maui;
using Microsoft.Maui.Controls;
using Microsoft.Maui.Controls.Hosting;
using Microsoft.Maui.Controls.Hosting.WPF;
using Microsoft.Maui.Controls.Internals;
using Microsoft.Maui.Hosting;

namespace Maui.Controls.Sample.WPF
{
	public static class MauiProgram
	{
		public static MauiApp CreateMauiApp() =>
			MauiApp
				.CreateBuilder()
				.UseMauiAppWPF<App>()
				.Build();
	}

	class App : Application
	{
		protected override Window CreateWindow(IActivationState? activationState)
		{
			return new Window(new ContentPage() { Content = new Label() { Text = "What is this" } });
		}
	}


	class WPFWindow : Window
	{
		public WPFWindow()
		{

		}

		public class WPFNavProxy : NavigationProxy
		{
			public WPFNavProxy()
			{
			}
		}

		class NavigationImpl : NavigationProxy
		{
			readonly Window _owner;

			public NavigationImpl(Window owner)
			{
				_owner = owner;
				_owner.NavigationProxy.Inner = this;
			}

			protected override IReadOnlyList<Page> GetModalStack()
			{
				throw new NotImplementedException();
			}

			protected override Task<Page?> OnPopModal(bool animated)
			{
				throw new NotImplementedException();
			}

			protected override Task OnPushModal(Page modal, bool animated)
			{
				throw new NotImplementedException();
			}
		}
	}

	class CustomContentPage : ContentPage
	{

		protected override void OnAppearing()
		{
			base.OnAppearing();
		}
	}
}