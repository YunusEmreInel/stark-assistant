"""Bilgisayar kontrolü: yalnızca izin verilen dar komutlar (kodla tanınır, dil modeli komut çalıştıramaz).

Uygulama açma, tarayıcıda/YouTube'da arama, YouTube'da video açma, ekran görüntüsü, masaüstünde dosya/klasör
oluşturma (asla üzerine yazmaz), ses ve medya tuşları, ekran kilitleme. Silme, kapatma, rastgele komut yok.
"""
import ctypes
import os
import re
import time
import winreg
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import httpx

_R = re.compile
_I = re.I

# ---- izin verilen uygulamalar: (eşleşme, App Paths adı ya da doğrudan hedef, okunur ad) ----
APPS = [
    (r"chrome|google\s+chrome|krom", "chrome.exe", "Chrome"),
    (r"edge|microsoft\s+edge", "msedge.exe", "Edge"),
    (r"word", "WINWORD.EXE", "Word"),
    (r"excel", "EXCEL.EXE", "Excel"),
    (r"power\s*point", "POWERPNT.EXE", "PowerPoint"),
    (r"vs\s*code|visual\s+studio\s+code|kod\s+editörü", "Code.exe", "VS Code"),
    (r"not\s+defteri|notepad", "notepad.exe", "Not Defteri"),
    (r"hesap\s+makinesi|calculator", "calc.exe", "Hesap Makinesi"),
    (r"dosya\s+gezgini|dosyalar|file\s+explorer", "explorer.exe", "Dosya Gezgini"),
    (r"paint", "mspaint.exe", "Paint"),
    (r"görev\s+yöneticisi|task\s+manager", "taskmgr.exe", "Görev Yöneticisi"),
    (r"ayarlar|settings", "ms-settings:", "Ayarlar"),
    (r"youtube", "https://www.youtube.com", "YouTube"),
]

# ekler: Chrome'u, YouTube'da, Word'ü, Excel'i ...
_SUF = r"(?:['’]?(?:u|ü|ı|i|yu|yü|yı|yi|nu|nü|nı|ni|da|de|ta|te|dan|den|tan|ten|a|e|ya|ye))?"
_APP = "|".join(f"(?:{rx})" for rx, _, _ in APPS)
_MORE = r"(?:(?:biraz|bir\s+tık|az|daha|çok)\s+)*"  # "sesi biraz daha kıs"

PATTERNS = [
    # YouTube'da video aç/oynat: "YouTube'da Tarkan Kuzu Kuzu'yu aç", "... videosunu oynat"
    ("youtube_play", _R(rf"^(?:youtube{_SUF}\s+)(?P<q>.+?)\s+(?:videosunu|videoyu|şarkısını|klibini|kanalını)?\s*"
                        rf"(?:aç|oynat|çal|başlat|izle)\w*\W*$", _I)),
    ("youtube_play", _R(rf"^(?P<q>.+?)\s+(?:videosunu|şarkısını|klibini)\s+(?:youtube{_SUF}\s+)?"
                        rf"(?:aç|oynat|çal|başlat)\w*\W*$", _I)),
    # YouTube'da arama
    ("youtube_search", _R(rf"^(?:youtube{_SUF}\s+)(?:aç\s+(?:ve\s+)?)?(?P<q>.+?)\s+(?:diye\s+)?ara\w*\W*$", _I)),
    ("youtube_search", _R(r"^search\s+youtube\s+for\s+(?P<q>.+)$", _I)),
    # Tarayıcıda/Google'da arama (Stark'ın kendi aramasından farklı: sayfayı açar)
    ("web_search", _R(rf"^(?:(?:chrome|google|tarayıcı|edge){_SUF}\s+)(?:aç\s+(?:ve\s+)?)?(?P<q>.+?)\s+(?:diye\s+)?"
                      rf"ara\w*\W*$", _I)),
    ("web_search", _R(r"^google\s+(?P<q>.+)$", _I)),
    # Ekran görüntüsü
    ("screenshot", _R(r"ekran\s+görüntüsü\s+(?:al|çek)|ekran[ıi]n?\s+(?:fotoğrafını|resmini)\s+(?:al|çek)|"
                      r"take\s+a\s+screenshot|screenshot", _I)),
    # Masaüstünde dosya/klasör: "Masaüstünde alışveriş adında bir dosya oluştur, içine süt ekmek yaz"
    ("create", _R(r"masaüstün(?:de|e)\s+(?P<name>.+?)\s+(?:adında|isminde|adlı|isimli|diye)\s+(?:bir\s+)?"
                  r"(?P<kind>klasör|dosya|metin\s+dosyası|not\s+dosyası|belge)\s*(?:oluştur|aç|yap)\w*"
                  r"(?:\s*[,.]?\s*(?:ve\s+)?içine\s+(?P<content>.+?)\s+yaz\w*)?\W*$", _I)),
    # Ses ve medya
    ("volume_up", _R(rf"\bsesi\s+{_MORE}(?:aç|yükselt|artır|arttır)\w*|volume\s+up", _I)),
    ("volume_down", _R(rf"\bsesi\s+{_MORE}(?:kıs|azalt|düşür)\w*|volume\s+down", _I)),
    ("mute", _R(r"\bsesi\s+(?:tamamen\s+)?kapat\w*|sessize\s+al\w*|\bmute\b", _I)),
    ("media_pause", _R(r"(?:müziği|şarkıyı|videoyu|medyayı)\s+(?:durdur|duraklat)\w*|pause\s+(?:the\s+)?music", _I)),
    ("media_play", _R(r"(?:müziğe|şarkıya|videoya)\s+devam\s+et\w*|müziği\s+(?:devam\s+ettir|oynat|başlat)\w*|"
                      r"resume\s+(?:the\s+)?music", _I)),
    ("media_next", _R(r"(?:sonraki|sıradaki)\s+(?:şarkı|parça|video)\w*|next\s+(?:song|track)", _I)),
    ("media_prev", _R(r"önceki\s+(?:şarkı|parça|video)\w*|previous\s+(?:song|track)", _I)),
    ("lock", _R(r"(?:ekranı|bilgisayarı)\s+kilitle\w*|lock\s+(?:the\s+)?(?:screen|computer)", _I)),
    # Uygulama açma: "Chrome'u aç", "Word'ü başlat", "open notepad"
    ("open_app", _R(rf"^(?:lütfen\s+)?(?P<app>{_APP}){_SUF}\s+(?:aç|başlat|çalıştır)\w*\W*$", _I)),
    ("open_app", _R(rf"^(?:open|launch|start)\s+(?P<app>{_APP})\W*$", _I)),
]


@dataclass(frozen=True)
class DesktopCommand:
    action: str
    arg: str = ""
    kind: str = ""
    content: str = ""


def _clean(q: str) -> str:
    q = re.sub(r"['’](?:yu|yü|yı|yi|u|ü|ı|i|nu|nü)$", "", q.strip(" \"'.,"))  # "Kuzu Kuzu'yu" → "Kuzu Kuzu"
    return q.strip(" \"'.,")


def parse(text: str) -> DesktopCommand | None:
    t = text.strip()
    for action, rx in PATTERNS:
        m = rx.search(t) if action not in ("youtube_play", "youtube_search", "web_search", "open_app", "create") \
            else rx.match(t)
        if not m:
            continue
        groups = m.groupdict()
        if action in ("youtube_play", "youtube_search", "web_search"):
            q = _clean(groups.get("q") or "")
            if not q or q.lower() in ("bunu", "şunu", "onu", "aç", "youtube"):
                return DesktopCommand("open_app", "youtube") if "youtube" in t.lower() else None
            return DesktopCommand(action, q)
        if action == "create":
            return DesktopCommand("create", _clean(groups["name"]), groups["kind"].lower(),
                                  (groups.get("content") or "").strip())
        if action == "open_app":
            return DesktopCommand("open_app", groups["app"])
        return DesktopCommand(action)
    return None


# ---- yürütme ----
def _app_target(name: str) -> tuple[str, str] | None:
    for rx, target, label in APPS:
        if re.fullmatch(rx, name.strip(), re.I):
            if target.endswith((".exe", ".EXE")) and target.lower() not in ("notepad.exe", "calc.exe", "explorer.exe",
                                                                             "mspaint.exe", "taskmgr.exe"):
                path = _app_path(target)
                return (path, label) if path else None
            return target, label
    return None


def _app_path(exe: str) -> str | None:
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                return winreg.QueryValue(k, None)
        except OSError:
            continue
    return None


def _open(target: str) -> None:
    os.startfile(target)  # ShellExecute: exe, URL ya da ms-settings: URI


def _known_folder(csidl: int) -> Path:
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return Path(buf.value)


DESKTOP, PICTURES = 0x10, 0x27
VK = {"volume_up": 0xAF, "volume_down": 0xAE, "mute": 0xAD, "media_pause": 0xB3, "media_play": 0xB3,
      "media_next": 0xB0, "media_prev": 0xB1}


def _press(vk: int, times: int = 1) -> None:
    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # KEYEUP
        time.sleep(0.02)


def first_youtube_video(query: str) -> str | None:
    """YouTube arama sayfasındaki ilk videonun adresi (resmi API gerekmez)."""
    r = httpx.get("https://www.youtube.com/results", params={"search_query": query}, timeout=8,
                  headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36",
                           "Accept-Language": "tr-TR,tr;q=0.9"}, cookies={"CONSENT": "YES+1", "SOCS": "CAI"})
    m = re.search(r'"videoRenderer":\{"videoId":"([\w-]{11})"', r.text) or re.search(r'"videoId":"([\w-]{11})"', r.text)
    return f"https://www.youtube.com/watch?v={m.group(1)}" if m else None


def _unique(path: Path) -> Path:
    """Var olan dosyanın üzerine asla yazılmaz: 'ad (2).txt' gibi yeni ad."""
    if not path.exists():
        return path
    for i in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise OSError("uygun dosya adı bulunamadı")


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def screenshot(folder: Path | None = None) -> Path:
    """Tüm ekranların görüntüsü (GDI), Resimler\\Stark klasörüne PNG olarak."""
    from PySide6.QtGui import QImage
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    x, y = u.GetSystemMetrics(76), u.GetSystemMetrics(77)          # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN
    w, h = u.GetSystemMetrics(78), u.GetSystemMetrics(79)          # SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN
    src = u.GetDC(None)
    dc = g.CreateCompatibleDC(src)
    bmp = g.CreateCompatibleBitmap(src, w, h)
    g.SelectObject(dc, bmp)
    g.BitBlt(dc, 0, 0, w, h, src, x, y, 0x00CC0020)               # SRCCOPY
    header = (ctypes.c_uint32 * 10)(40, w, (-h) & 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    g.GetDIBits(dc, bmp, 0, h, buf, header, 0)
    g.DeleteObject(bmp)
    g.DeleteDC(dc)
    u.ReleaseDC(None, src)
    folder = folder or (_known_folder(PICTURES) / "Stark")
    folder.mkdir(parents=True, exist_ok=True)
    path = _unique(folder / f"Ekran görüntüsü {datetime.now():%Y-%m-%d %H.%M.%S}.png")
    QImage(buf.raw, w, h, QImage.Format.Format_RGB32).copy().save(str(path))
    return path


def create_on_desktop(name: str, kind: str, content: str = "", desktop: Path | None = None) -> Path:
    desktop = desktop or _known_folder(DESKTOP)
    safe = _BAD_CHARS.sub("", name).strip(" .") or "Yeni"
    if kind == "klasör":
        path = _unique(desktop / safe)
        path.mkdir()
        return path
    if not Path(safe).suffix:
        safe += ".txt"
    path = _unique(desktop / safe)
    path.write_text(content + ("\n" if content else ""), encoding="utf-8")
    return path


TEXT = {
    "open": "{app} açılıyor patron.",
    "no_app": "{app} bu bilgisayarda kurulu görünmüyor patron.",
    "web_search": "Chrome'da “{q}” aramasını açıyorum patron.",
    "youtube_search": "YouTube'da “{q}” aramasını açıyorum patron.",
    "youtube_play": "YouTube'da “{q}” açılıyor patron.",
    "youtube_fallback": "Videoyu doğrudan bulamadım patron, “{q}” arama sonuçlarını açtım.",
    "screenshot": "Ekran görüntüsünü aldım patron, Resimler klasöründeki Stark klasörüne kaydettim.",
    "created_file": "Masaüstünde “{name}” dosyasını oluşturdum patron.",
    "created_folder": "Masaüstünde “{name}” klasörünü oluşturdum patron.",
    "volume_up": "Sesi açtım patron.", "volume_down": "Sesi kıstım patron.", "mute": "Sesi kapattım patron.",
    "media_pause": "Durdurdum patron.", "media_play": "Devam ettiriyorum patron.",
    "media_next": "Sonrakine geçtim patron.", "media_prev": "Öncekine döndüm patron.",
    "lock": "Ekranı kilitliyorum patron.",
    "failed": "Bunu yapamadım patron: {err}",
}


def execute(cmd: DesktopCommand, opener=_open) -> tuple[str, str]:
    """(söylenecek cevap, ekranda gösterilecek ek bilgi). Hata olursa açıklayıcı cevap döner."""
    t = TEXT
    try:
        if cmd.action == "open_app":
            found = _app_target(cmd.arg)
            if not found:
                return t["no_app"].format(app=cmd.arg.title()), ""
            opener(found[0])
            return t["open"].format(app=found[1]), ""
        if cmd.action == "web_search":
            chrome = _app_path("chrome.exe")
            url = f"https://www.google.com/search?q={quote_plus(cmd.arg)}"
            if chrome:
                import subprocess
                subprocess.Popen([chrome, url])
            else:
                opener(url)
            return t["web_search"].format(q=cmd.arg), url
        if cmd.action == "youtube_search":
            url = f"https://www.youtube.com/results?search_query={quote_plus(cmd.arg)}"
            opener(url)
            return t["youtube_search"].format(q=cmd.arg), url
        if cmd.action == "youtube_play":
            try:
                url = first_youtube_video(cmd.arg)
            except httpx.HTTPError:
                url = None
            if not url:
                url = f"https://www.youtube.com/results?search_query={quote_plus(cmd.arg)}"
                opener(url)
                return t["youtube_fallback"].format(q=cmd.arg), url
            opener(url)
            return t["youtube_play"].format(q=cmd.arg), url
        if cmd.action == "screenshot":
            path = screenshot()
            return t["screenshot"], str(path)
        if cmd.action == "create":
            path = create_on_desktop(cmd.arg, cmd.kind, cmd.content)
            key = "created_folder" if cmd.kind == "klasör" else "created_file"
            return t[key].format(name=path.name), str(path)
        if cmd.action in VK:
            _press(VK[cmd.action], 5 if cmd.action in ("volume_up", "volume_down") else 1)
            return t[cmd.action], ""
        if cmd.action == "lock":
            ctypes.windll.user32.LockWorkStation()
            return t["lock"], ""
    except Exception as e:  # noqa: BLE001 — kullanıcıya anlaşılır cevap
        return t["failed"].format(err=e), ""
    return t["failed"].format(err=cmd.action), ""
