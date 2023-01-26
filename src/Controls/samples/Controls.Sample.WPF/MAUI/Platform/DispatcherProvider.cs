using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Threading;
using Microsoft.Maui.Dispatching;

namespace Microsoft.Maui.Platform.WPF
{
	public partial class WPFDispatcherProvider : IDispatcherProvider
	{
		[ThreadStatic]
		static IDispatcher? s_dispatcherInstance;

		/// <inheritdoc/>
		public IDispatcher? GetForCurrentThread() =>
			s_dispatcherInstance ??= new WPFDispatcher(System.Windows.Threading.Dispatcher.CurrentDispatcher);
	}

	public partial class WPFDispatcher : IDispatcher
	{
		readonly System.Windows.Threading.Dispatcher _dispatcherQueue;
		public System.Windows.Threading.Dispatcher Dispatcher => _dispatcherQueue;

		internal WPFDispatcher(System.Windows.Threading.Dispatcher dispatcherQueue)
		{
			_dispatcherQueue = dispatcherQueue ?? throw new ArgumentNullException(nameof(dispatcherQueue));
		}

		public bool IsDispatchRequired => throw new NotImplementedException();

		public bool Dispatch(Action action)
		{
			_dispatcherQueue.BeginInvoke(action, null);
			return true;
		}

		public bool DispatchDelayed(TimeSpan delay, Action action)
		{
			throw new NotImplementedException();
		}

		public IDispatcherTimer CreateTimer()
		{
			return new WPFDispatchTimer(this);
		}
	}

	public class WPFDispatchTimer : IDispatcherTimer
	{
		DispatcherTimer _dispatchTimer;

		public WPFDispatchTimer(WPFDispatcher wPFDispatcher)
		{
			_dispatchTimer = new DispatcherTimer(DispatcherPriority.Normal, wPFDispatcher.Dispatcher);
			_dispatchTimer.Tick += OnTick;
		}

		void OnTick(object? sender, EventArgs e)
		{
			Tick?.Invoke(this, EventArgs.Empty);
		}

		public TimeSpan Interval
		{
			get => _dispatchTimer.Interval;
			set => _dispatchTimer.Interval = value;
		}
		public bool IsRepeating
		{
			get;
			set;
		}

		public bool IsRunning => throw new NotImplementedException();

		public event EventHandler? Tick;

		public void Start()
		{
			_dispatchTimer.Start();
		}

		public void Stop()
		{
			_dispatchTimer.Stop();
		}
	}
}
