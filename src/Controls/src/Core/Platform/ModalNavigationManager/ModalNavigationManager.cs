using System;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using Microsoft.Maui.Controls.Internals;

namespace Microsoft.Maui.Controls.Platform
{
	internal partial class ModalNavigationManager
	{
		Window _window;
		public IReadOnlyList<Page> ModalStack => _navModel.Modals;
		IMauiContext WindowMauiContext => _window.MauiContext;
		NavigationModel _navModel = new NavigationModel();
		NavigationModel? _previousNavModel = null;
		Page? _previousPage;

		public ModalNavigationManager(Window window)
		{
			_window = window;
		}

		public Task<Page?> PopModalAsync()
		{
			return PopModalAsync(true);
		}

		public Task PushModalAsync(Page modal)
		{
			return PushModalAsync(modal, true);
		}

		public async Task<Page?> PopModalAsync(bool animated)
		{
			Page modal = _window.ModalNavigationManager.ModalStack[_window.ModalNavigationManager.ModalStack.Count - 1];
			if (_window.OnModalPopping(modal))
			{
				_window.OnPopCanceled();
				return null;
			}

			Page? nextPage;
			if (modal.NavigationProxy.ModalStack.Count == 1)
			{
				nextPage = _window.Page;
			}
			else
			{
				nextPage = ModalStack[ModalStack.Count - 2];
			}

			_navModel.LastRoot.SendDisappearing();
			Page result = await PopModalPlatformAsync(animated);
			result.Parent = null;
			_window.OnModalPopped(result);

			modal.SendNavigatedFrom(new NavigatedFromEventArgs(nextPage));
			nextPage?.SendNavigatedTo(new NavigatedToEventArgs(modal));

			return result;
		}

		public async Task PushModalAsync(Page modal, bool animated)
		{
			_window.OnModalPushing(modal);

			modal.Parent = _window;

			if (ModalStack.Count == 0)
			{
				_window.Page?.SendDisappearing();
				modal.SendAppearing();
				modal.NavigationProxy.Inner = _window.Navigation;
				await PushModalPlatformAsync(modal, animated);
				_window.Page?.SendNavigatedFrom(new NavigatedFromEventArgs(modal));
				modal.SendNavigatedTo(new NavigatedToEventArgs(_window.Page));
			}
			else
			{
				var previousModalPage = modal.NavigationProxy.ModalStack[modal.NavigationProxy.ModalStack.Count - 1];
				previousModalPage.SendDisappearing();
				modal.SendAppearing();
				await PushModalPlatformAsync(modal, animated);
				modal.NavigationProxy.Inner = _window.Navigation;
				previousModalPage.SendNavigatedFrom(new NavigatedFromEventArgs(modal));
				modal.SendNavigatedTo(new NavigatedToEventArgs(previousModalPage));
			}

			_window.OnModalPushed(modal);
		}

		internal void SettingNewPage()
		{
			if (_previousPage != null)
			{
				// if _previousNavModel has been set than _navModel has already been reinitialized
				if (_previousNavModel != null)
				{
					_previousNavModel = null;
					if (_navModel == null)
						_navModel = new NavigationModel();
				}
				else
					_navModel = new NavigationModel();
			}

			if (_window.Page == null)
			{
				_previousPage = null;

				return;
			}

			_navModel.Push(_window.Page, null);
			_previousPage = _window.Page;
		}

		partial void OnPageAttachedHandler();

		public void PageAttachedHandler() => OnPageAttachedHandler();
	}
}