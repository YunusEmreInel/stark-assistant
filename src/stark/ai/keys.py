"""İnternetteki modellerin API anahtarları: ~/.stark/anahtarlar.bin, Windows DPAPI ile şifreli.

DPAPI anahtarı Windows kullanıcı hesabına bağlar: dosya başka bir hesaba ya da bilgisayara kopyalansa da çözülemez.
Anahtarlar düz metin olarak diske, ayar dosyasına ya da kayıtlara yazılmaz.
"""
import ctypes
import json
from ctypes import wintypes

from ..config import APP_DIR

KEYS_FILE = APP_DIR / "anahtarlar.bin"
PROVIDERS = ("groq", "gemini", "openrouter")


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt(data: bytes, protect: bool) -> bytes:
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))  # çağrı bitene kadar bellekte kalmalı
    blob_in = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(out))  # UI_FORBIDDEN
    if not ok:
        raise OSError("Windows şifreleme (DPAPI) başarısız")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def load() -> dict[str, str]:
    try:
        data = json.loads(_crypt(KEYS_FILE.read_bytes(), protect=False).decode("utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if k in PROVIDERS and isinstance(v, str) and v.strip()}


def save(keys: dict[str, str]) -> None:
    clean = {k: v.strip() for k, v in keys.items() if k in PROVIDERS and v and v.strip()}
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not clean:
        KEYS_FILE.unlink(missing_ok=True)
        return
    KEYS_FILE.write_bytes(_crypt(json.dumps(clean).encode("utf-8"), protect=True))
