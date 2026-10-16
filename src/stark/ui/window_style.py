"""Windows 11 başlık çubuğunu uygulamanın siyah temasına uydurur (DWM öznitelikleri).

Çerçevesiz pencere yerine yerel başlık çubuğu korunur: sürükleme, kenara yaslama (Snap), büyütme çalışmaya
devam eder. Windows 10'da renk öznitelikleri desteklenmez; yalnızca koyu mod uygulanır, hata verilmez.
"""
import ctypes

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def _colorref(r: int, g: int, b: int) -> ctypes.c_int:
    return ctypes.c_int(r | (g << 8) | (b << 16))


def dark_title_bar(widget) -> None:
    try:
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        for attr, value in ((DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.c_int(1)),
                            (DWMWA_CAPTION_COLOR, _colorref(14, 14, 16)),     # uygulama başlığıyla aynı ton
                            (DWMWA_TEXT_COLOR, _colorref(230, 230, 232)),
                            (DWMWA_BORDER_COLOR, _colorref(31, 31, 35))):
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
    except (AttributeError, OSError):
        pass  # Windows dışı / eski sürüm: varsayılan başlık çubuğu kalır
