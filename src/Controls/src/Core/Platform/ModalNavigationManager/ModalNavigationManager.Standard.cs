using System;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using Microsoft.Maui.Controls.Internals;

namespace Microsoft.Maui.Controls.Platform
{
	internal partial class ModalNavigationManager
	{
		Task<Page> PopModalPlatformAsync(bool animated)
		{
			if (ModalStack.Count == 0)
				throw new InvalidOperationException();

			return Task.FromResult(_navModel.PopModal());
		}

		Task PushModalPlatformAsync(Page modal, bool animated)
		{
			_navModel.PushModal(modal);
			return Task.CompletedTask;
		}
	}
}
