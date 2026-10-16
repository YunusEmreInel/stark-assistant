"""Görev çubuğu kimliği: pencere pythonw.exe'ye değil Stark'a ait görünsün (Python simgesi yerine Stark simgesi).

Pencereye AppUserModel özellikleri yazılır; görev çubuğuna sabitlenirse yeniden açma komutu Stark.exe olur.
"""
import ctypes
import uuid
from ctypes import POINTER, Structure, byref, c_ubyte, c_ulong, c_ushort, c_void_p, c_wchar_p
from ctypes import wintypes
from pathlib import Path


class _GUID(Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort), ("Data4", c_ubyte * 8)]

    @classmethod
    def of(cls, text: str) -> "_GUID":
        u = uuid.UUID(text)
        g = cls(u.fields[0], u.fields[1], u.fields[2])
        g.Data4[:] = list(u.bytes[8:])
        return g


class _PROPERTYKEY(Structure):
    _fields_ = [("fmtid", _GUID), ("pid", wintypes.DWORD)]


class _PROPVARIANT(Structure):  # yalnızca VT_LPWSTR kullanılır
    _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort),
                ("pwszVal", c_wchar_p), ("pad", c_void_p)]


_APPUSERMODEL = "9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"
_IID_IPROPERTYSTORE = "886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"
_VT_LPWSTR = 31


def set_identity(hwnd: int, app_id: str, display_name: str = "Stark") -> bool:
    """AppUserModel.ID + yeniden açma komutu/simgesi (Stark.exe) pencereye yazılır. Başarısızsa False."""
    try:
        exe = Path(__file__).resolve().parents[3] / "launcher" / "Stark.exe"
        values = {5: app_id, 4: display_name}  # 5 = ID, 4 = RelaunchDisplayNameResource
        if exe.exists():
            values[2] = f'"{exe}"'          # RelaunchCommand
            values[3] = f"{exe},0"          # RelaunchIconResource
        store = c_void_p()
        iid = _GUID.of(_IID_IPROPERTYSTORE)
        if ctypes.windll.shell32.SHGetPropertyStoreForWindow(wintypes.HWND(hwnd), byref(iid), byref(store)) != 0:
            return False
        vtable = ctypes.cast(ctypes.cast(store, POINTER(c_void_p))[0], POINTER(c_void_p))
        set_value = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, POINTER(_PROPERTYKEY), POINTER(_PROPVARIANT))(vtable[6])
        commit = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p)(vtable[7])
        release = ctypes.WINFUNCTYPE(c_ulong, c_void_p)(vtable[2])
        # Windows kuralı: ID en son yazılır (yeniden açma özellikleri ondan önce)
        for pid in sorted(values, key=lambda p: p == 5):
            key = _PROPERTYKEY(_GUID.of(_APPUSERMODEL), pid)
            var = _PROPVARIANT(_VT_LPWSTR, 0, 0, 0, values[pid], None)
            set_value(store, byref(key), byref(var))
        commit(store)
        release(store)
        return True
    except (AttributeError, OSError):
        return False
