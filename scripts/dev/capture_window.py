"""Yalnızca Stark penceresinin görüntüsünü (başlık çubuğu dahil) kaydeder: PrintWindow, üstteki başka
pencereleri yakalamaz. Kullanım: python scripts/capture_window.py çıktı.png"""
import ctypes
import sys
from ctypes import wintypes

from PySide6.QtGui import QImage

user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
user32.SetProcessDPIAware()
found = []


@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def _each(h, _):
    title = ctypes.create_unicode_buffer(64)
    user32.GetWindowTextW(h, title, 64)
    r = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    if title.value == "Stark" and user32.IsWindowVisible(h) and r.right - r.left > 300:
        found.append(h)
    return True


if len(sys.argv) > 2:  # pencere tanıtıcısı doğrudan verilebilir (PowerShell: MainWindowHandle)
    found = [int(sys.argv[2])]
else:
    user32.EnumWindows(_each, 0)  # aynı başlıklı küçük yardımcı pencereler değil, görünür ana pencere
if not found:
    sys.exit("Stark penceresi bulunamadı")
hwnd = found[0]
rect = wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
w, h = rect.right - rect.left, rect.bottom - rect.top
src = user32.GetWindowDC(hwnd)
dc = gdi32.CreateCompatibleDC(src)
bmp = gdi32.CreateCompatibleBitmap(src, w, h)
gdi32.SelectObject(dc, bmp)
user32.PrintWindow(hwnd, dc, 2)  # PW_RENDERFULLCONTENT


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


info = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
buf = ctypes.create_string_buffer(w * h * 4)
gdi32.GetDIBits(dc, bmp, 0, h, buf, ctypes.byref(info), 0)
QImage(buf.raw, w, h, QImage.Format.Format_RGB32).copy().save(sys.argv[1])
gdi32.DeleteObject(bmp)
gdi32.DeleteDC(dc)
user32.ReleaseDC(hwnd, src)
print("kaydedildi", w, "x", h)
