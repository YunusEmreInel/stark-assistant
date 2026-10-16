"""Dosya bulma ve açma: Masaüstü, Belgeler, İndirilenler, Resimler. Yalnızca açar; değiştirmez, silmez.

Program/komut dosyaları (.exe, .msi, .bat, ...) asla çalıştırılmaz: klasörü açılıp dosya seçili gösterilir
("son indirdiğim dosyayı aç" bir kurulum dosyasını yanlışlıkla çalıştırmasın).
"""
import ctypes
import os
import re
import subprocess
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from ..memory.database import tr_lower

DANGEROUS = {".exe", ".msi", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".scr",
             ".com", ".pif", ".reg", ".hta", ".jar", ".msc", ".cpl", ".lnk", ".url", ".appx", ".msix", ".py", ".pyw",
             ".iso", ".img", ".vhd", ".vhdx", ".chm", ".msp", ".application", ".scf", ".ws", ".xll", ".appref-ms",
             ".library-ms", ".settingcontent-ms"}  # çalıştırılabilen ya da bağlanınca içinden program açılabilen türler
MAX_FILES = 20000
MAX_DEPTH = 4

_FOLDERS = {  # (eşleşme, bilinen klasör anahtarı, okunur ad)
    "desktop": (r"masaüst\w*", "Masaüstü"), "documents": (r"belgeler\w*|dokümanlar\w*", "Belgeler"),
    "downloads": (r"indirilenler\w*|indirdiklerim\w*|downloads", "İndirilenler"),
    "pictures": (r"resimler\w*|fotoğraflar\w*", "Resimler"),
}
_LOC = "|".join(f"(?P<{k}>{rx})" for k, (rx, _) in _FOLDERS.items())
_KIND = (r"dosya\w*|belge\w*|klasör\w*|pdf\w*|word\s+dosya\w*|sunum\w*|tablo\w*|excel\w*|resm\w*|fotoğraf\w*|"
         r"video\w*|ödev\w*|rapor\w*")
_OPEN = r"(?:aç|göster|bul\s+ve\s+aç|bulup\s+aç)\w*"

PATTERNS = [
    ("latest_download", re.compile(r"(?:en\s+)?son\s+indir(?:diğim|ilen|dığım)\s+(?:dosya\w*\s+)?" + _OPEN, re.I)),
    ("folder", re.compile(rf"^(?:{_LOC})\s+klasör\w*\s+{_OPEN}\W*$", re.I)),
    ("folder", re.compile(rf"^(?:{_LOC})\s+{_OPEN}\W*$", re.I)),
    ("file", re.compile(rf"^(?:(?:{_LOC})\s*(?:deki|daki|ndeki|ndaki|teki|taki)?\s+)?(?P<q>.+?)\s+(?:adlı\s+|isimli\s+)?"
                        rf"(?P<kind>{_KIND})\s+{_OPEN}\W*$", re.I)),
    ("file", re.compile(rf"^(?P<q>.+?)\s+(?:adlı|isimli)\s+(?:dosya\w*|belge\w*)\s+{_OPEN}\W*$", re.I)),
]


@dataclass(frozen=True)
class FileCommand:
    action: str            # file | folder | latest_download
    query: str = ""
    where: str = ""        # desktop | documents | downloads | pictures | ""
    kind: str = ""


def _where(m: re.Match) -> str:
    return next((k for k in _FOLDERS if m.groupdict().get(k)), "")


def parse(text: str) -> FileCommand | None:
    t = text.strip()
    for action, rx in PATTERNS:
        m = rx.search(t) if action == "latest_download" else rx.match(t)
        if not m:
            continue
        if action == "latest_download":
            return FileCommand("latest_download", where="downloads")
        if action == "folder":
            return FileCommand("folder", where=_where(m))
        q = re.sub(r"['’]\w+$", "", (m.group("q") or "").strip(" \"'.,"))  # "ödevimi" eki aramada atılır
        q = re.sub(r"^(?:bana\s+|benim\s+|şu\s+|o\s+)", "", q, flags=re.I)
        if not q or q.lower() in ("bu", "şu", "o"):
            return None
        kind = (m.groupdict().get("kind") or "").lower()
        return FileCommand("file", q, _where(m), kind)
    return None


# ---- klasörler ----
_KNOWN = {"desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
          "downloads": "{374DE290-123F-4565-9164-39C4925E467B}", "pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}"}


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]


def known_folder(key: str) -> Path:
    u = uuid.UUID(_KNOWN[key])
    g = _GUID(u.fields[0], u.fields[1], u.fields[2])
    g.Data4[:] = list(u.bytes[8:])
    out = ctypes.c_wchar_p()
    ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out))
    path = Path(out.value)
    ctypes.windll.ole32.CoTaskMemFree(out)
    return path


# ---- arama ----
_KIND_EXT = {"pdf": {".pdf"}, "word": {".doc", ".docx", ".odt", ".rtf"}, "sunum": {".ppt", ".pptx", ".odp"},
             "tablo": {".xls", ".xlsx", ".csv", ".ods"}, "excel": {".xls", ".xlsx", ".csv"},
             "resm": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"},
             "fotoğraf": {".png", ".jpg", ".jpeg", ".heic", ".webp"}, "video": {".mp4", ".mkv", ".avi", ".mov", ".webm"}}


_ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def _words(text: str) -> list[str]:
    """Karşılaştırma kökleri; Türkçe karakterler katlanır: dosya adı çoğu zaman "odev", "yapilari" diye yazılır."""
    return [w[:5].translate(_ASCII) for w in re.findall(r"[0-9a-zçğıöşüâîû]+", tr_lower(text)) if len(w) >= 2]


def _iter_files(root: Path, folders: bool):
    count = 0
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "$")) and d not in ("node_modules", "AppData")
                       and len(Path(dirpath).parts) - base_depth < MAX_DEPTH]
        for name in (dirnames if folders else filenames):
            count += 1
            if count > MAX_FILES:
                return
            yield Path(dirpath) / name


def find(query: str, where: str = "", kind: str = "", roots: list[Path] | None = None) -> Path | None:
    """Adıyla en iyi eşleşen dosya/klasör. Tüm sorgu kelimeleri ad içinde geçmeli; eşitlikte en yeni."""
    roots = roots or [known_folder(where)] if where else roots or [known_folder(k) for k in _KNOWN]
    q = _words(query)
    if not q:
        return None
    exts = next((e for k, e in _KIND_EXT.items() if kind.startswith(k)), None)
    folders = kind.startswith("klasör")
    best, best_key = None, None
    for root in roots:
        if not root.exists():
            continue
        for p in _iter_files(root, folders):
            if exts and p.suffix.lower() not in exts:
                continue
            name = _words(p.stem if not folders else p.name)
            if not all(any(n.startswith(w) or w.startswith(n) for n in name) for w in q):
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            key = (len(q) / max(1, len(name)), mtime)  # daha az fazladan kelime, sonra daha yeni
            if best_key is None or key > best_key:
                best, best_key = p, key
    return best


def latest(folder: Path) -> Path | None:
    files = [p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")
             and p.suffix.lower() not in {".tmp", ".crdownload", ".part"}] if folder.exists() else []
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


# ---- açma ----
def open_safely(path: Path, opener=os.startfile) -> bool:
    """True: dosya açıldı. False: program dosyasıydı, yalnızca klasörde seçili gösterildi."""
    if path.is_file() and path.suffix.lower() in DANGEROUS:
        subprocess.Popen(["explorer.exe", "/select,", str(path)])
        return False
    opener(str(path))
    return True


TEXT = {
    "opened": "“{name}” açılıyor patron.",
    "program": "“{name}” bir program dosyası; güvenlik için çalıştırmadım, bulunduğu klasörü açıp işaretledim patron.",
    "folder": "{name} klasörünü açıyorum patron.",
    "not_found": "“{q}” adında bir dosya bulamadım patron. Masaüstü, Belgeler, İndirilenler ve Resimler'e baktım.",
    "empty": "{name} klasörü boş görünüyor patron.",
}


def execute(cmd: FileCommand, opener=os.startfile) -> tuple[str, str]:
    try:
        if cmd.action == "folder":
            folder = known_folder(cmd.where or "documents")
            opener(str(folder))
            return TEXT["folder"].format(name=_FOLDERS[cmd.where or "documents"][1]), str(folder)
        if cmd.action == "latest_download":
            path = latest(known_folder("downloads"))
            if not path:
                return TEXT["empty"].format(name="İndirilenler"), ""
        else:
            path = find(cmd.query, cmd.where, cmd.kind)
            if not path:
                return TEXT["not_found"].format(q=cmd.query), ""
        opened = open_safely(path, opener)
        return (TEXT["opened"] if opened else TEXT["program"]).format(name=path.name), str(path)
    except Exception as e:  # noqa: BLE001
        return f"Dosyayı açamadım patron: {e}", ""
