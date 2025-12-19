using System;

namespace Microsoft.Maui.Controls
{
	/// <summary>
	/// Event arguments for the ModalDismissAttempted event, which is raised when a user attempts to dismiss a modal page.
	/// </summary>
	public sealed class ModalDismissAttemptedEventArgs : EventArgs
	{
		/// <summary>
		/// Initializes a new instance of the <see cref="ModalDismissAttemptedEventArgs"/> class.
		/// </summary>
		public ModalDismissAttemptedEventArgs()
		{
			Cancel = false;
		}

		/// <summary>
		/// Gets or sets a value indicating whether the modal dismissal should be cancelled.
		/// </summary>
		/// <value>
		/// <c>true</c> to cancel the dismissal; otherwise, <c>false</c>. The default is <c>false</c>.
		/// </value>
		public bool Cancel { get; set; }
	}
}
