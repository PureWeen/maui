﻿- OpenWindowRequest only accepts IPersistedState and a specific args for WinUI which makes passing in startup args awkward.
- We need to fix our targets files to delineate between WPF and WinUI in order for this to work
- LifeCycle commands on pages need to be made public or interface driven (sendnavigated, sendappearing, etc...)
- ModalNavigationManager needs a public interface
- AlertManager needs a public interface
- GestureManager needs a public interface