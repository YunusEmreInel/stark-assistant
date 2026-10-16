"""Model çıktısını seslendirmeye uygun düz metne çevirir."""
import re

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")
_URL = re.compile(r"https?://([^/\s]+)\S*")

CODE_NOTE = {"tr": "Kodu ekrana yazdım.", "en": "I put the code on the screen."}


_ISO_DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_MONTHS = {"tr": ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
                  "Kasım", "Aralık"],
           "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                  "October", "November", "December"]}


def humanize_dates(text: str, language: str = "tr") -> str:
    """Kaynaklardan gelen "2026-10-15" biçimini okunur hale getirir: "15 Ekim 2026"."""
    months = _MONTHS.get(language, _MONTHS["tr"])

    def repl(m: re.Match) -> str:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not 1 <= mo <= 12:
            return m.group(0)
        return f"{d} {months[mo - 1]} {y}" if language != "en" else f"{months[mo - 1]} {d}, {y}"
    return _ISO_DATE.sub(repl, text)


def strip_emoji(text: str) -> str:
    """Ekranda ve sohbet geçmişinde emoji kalmasın (model geçmişte görünce alışkanlığı sürdürüyor)."""
    return re.sub(r"[ \t]+(\n|$)", r"\1", _EMOJI.sub("", text))


_MATH = {"tr": {"×": "çarpı", "÷": "bölü", "^": "üzeri", "=": "eşittir", "+": "artı"},
         "en": {"×": "times", "÷": "divided by", "^": "to the power of", "=": "equals", "+": "plus"}}


def _math_words(t: str, language: str) -> str:
    """Hesap sonuçları sesli okunabilsin: işaretler kelimeye, binlik noktalar kaldırılır (9.315 → 9315)."""
    words = _MATH.get(language, _MATH["tr"])
    t = re.sub(r"\b\d{1,3}(?:\.\d{3})+\b(?!,\d)", lambda m: m.group(0).replace(".", ""), t)
    for sym, word in words.items():
        t = t.replace(f" {sym} ", f" {word} ")
    t = re.sub(r"(?<=\d) - (?=\d)", " eksi " if language != "en" else " minus ", t)
    return t


def to_speech(text: str, language: str = "tr") -> str:
    """Boş dönerse cümle seslendirilmez."""
    t = text.strip()
    if t.startswith("```"):
        return CODE_NOTE.get(language, CODE_NOTE["tr"])
    t = _URL.sub(lambda m: m.group(1).removeprefix("www."), t)
    t = re.sub(r"`([^`]*)`", r"\1", t)                 # satır içi kod
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)     # [metin](bağlantı)
    t = re.sub(r"(\*\*|__|\*|_|~~)(.+?)\1", r"\2", t)  # kalın/italik
    t = re.sub(r"^\s{0,3}(#{1,6}|>|[-*+•]|\d+[.)])\s+", "", t, flags=re.M)  # başlık/liste/alıntı
    t = re.sub(r"^\s*\|?[-:| ]+\|?\s*$", "", t, flags=re.M)  # tablo ayırıcı
    t = t.replace("|", ", ")
    t = _EMOJI.sub("", t)
    t = _math_words(t, language)
    t = re.sub(r"[*#_~]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t
