"""Windows genel klavye kısayolları (RegisterHotKey). Stark arka plandayken de çalışır."""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
user32 = ctypes.windll.user32


class GlobalHotkeys(QAbstractNativeEventFilter):
    def __init__(self):
        super().__init__()
        self._actions: dict[int, callable] = {}
        self.failed: list[str] = []

    def register(self, label: str, key: str, action) -> None:
        """key: tek harf, Ctrl+Alt ile birlikte."""
        hid = len(self._actions) + 1
        if user32.RegisterHotKey(None, hid, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord(key.upper())):
            self._actions[hid] = action
        else:
            self.failed.append(label)  # başka bir uygulama kullanıyor

    def unregister_all(self) -> None:
        for hid in self._actions:
            user32.UnregisterHotKey(None, hid)
        self._actions.clear()

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in self._actions:
                self._actions[msg.wParam]()
                return True, 0
        return False, 0
