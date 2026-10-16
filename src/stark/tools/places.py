"""Kullanıcının yaşadığı şehrin ilçeleri: konuşma tanıma ve dil modeli yerel ilçe adlarını tanımıyordu
("bornovada", "Bor'novada" → "bornova ne demek?"). İlçe adları Whisper'a ipucu olarak, modele bağlam olarak verilir
ve metindeki yazım hataları kodla düzeltilir.

İlçe listesi kişisel veridir (nerede yaşadığınızı gösterir): kodda değil, kullanıcının kendi bilgisayarında
~/.stark/yerler.json dosyasında durur, ör. {"İzmir": ["Bornova", "Karşıyaka", "Buca"]}. Dosya yoksa yalnızca
şehir adı ve "Şunu öğren" ile öğretilen özel adlar kullanılır."""
import json
import re

from ..config import APP_DIR
from ..memory.database import tr_lower

PLACES_FILE = APP_DIR / "yerler.json"


def _load() -> dict[str, list[str]]:
    try:
        data = json.loads(PLACES_FILE.read_text(encoding="utf-8"))
        return {str(k): [str(x) for x in v] for k, v in data.items() if isinstance(v, list)}
    except (OSError, ValueError, AttributeError):
        return {}


DISTRICTS: dict[str, list[str]] = _load()
# Türkçe hal ekleri (kesme işaretli ya da işaretsiz)
_SUFFIX = (r"(?P<suf>ndaki|ndeki|ndan|nden|nda|nde|nın|nin|nun|nün|na|ne|nı|ni|nu|nü|"
           r"daki|deki|dan|den|tan|ten|da|de|ta|te|ya|ye|yı|yi|ın|in|un|ün|a|e|ı|i)?")


def districts(city: str) -> list[str]:
    return DISTRICTS.get(city, [])


def _pattern(name: str) -> re.Pattern:
    # "Bor'novada" gibi yanlış yerde kesme işareti: harflerin arasına isteğe bağlı kesme işareti
    letters = "['’]?".join(re.escape(ch) for ch in tr_lower(name))
    # Kesme işareti yalnızca bilinen bir hal ekiyle birlikte tüketilir: "Bornova'dır" bozulmasın
    return re.compile(rf"\b{letters}(?:['’]?{_SUFFIX[:-1]})?(?![\wçğıöşü])")


def known_names(city: str, learned: list[str] = ()) -> list[str]:
    """Yazımı düzeltilecek adlar: şehrin ilçeleri + kullanıcının öğrettiği bilgilerdeki özel adlar."""
    names = list(districts(city))
    for n in learned:
        if len(n) >= 4 and n not in names and " " not in n:
            names.append(n)
    return names


def normalize(text: str, city: str, learned: list[str] = ()) -> str:
    """"bornovada" / "Bor'novada" → "Bornova'da" (şehrin ilçeleri ve öğretilen özel adlar)."""
    low = tr_lower(text)
    out = text
    for name in known_names(city, learned):
        rx = _pattern(name)
        # Eşleşmeyi küçük harfli kopyada bul, aynı konumdan orijinal metni değiştir (uzunluk değişebilir)
        for m in reversed(list(rx.finditer(low))):
            suf = m.group("suf") or ""
            out = out[:m.start()] + name + (f"'{suf}" if suf else "") + out[m.end():]
        low = tr_lower(out)
    return out


def whisper_hint(city: str, learned: list[str] = ()) -> str:
    names = [city] if city else []
    names += [n for n in known_names(city, learned) if n not in names]
    return f" {', '.join(names[:40])}." if names else ""


LOCAL_HINT = re.compile(r"\b(burada|buralarda|yakın|yakınlarda|civar|çevrede|bizim\s+(?:il|ilçe|şehir|mahalle)|"
                        r"yerel|mahalle|ilçe|near\s+me|nearby|local)\w*", re.I)


def is_local(text: str, city: str, learned: list[str] = ()) -> bool:
    """Soru yerel mi? (şehir/ilçe adı ya da "burada, yakınlarda" gibi ifadeler)"""
    if not city:
        return False
    low = tr_lower(text)
    names = [city] + known_names(city, learned)
    return bool(LOCAL_HINT.search(text)) or any(re.search(rf"\b{re.escape(tr_lower(n))}", low) for n in names)


def context(city: str) -> str:
    """Yalnızca yerel sorularda modele verilir: her soruda verilince model ilçe adlarını ilgisiz cevaplara
    karıştırıyordu ("Karadeniz Bölgesi Bornova, Nazilli gibi iller içerir")."""
    if not city:
        return ""
    names = districts(city)
    text = f"The user lives in {city}, Türkiye."
    if names:
        text += f" Districts of {city}: {', '.join(names)}."
    return text + " Place names the user mentions are real places; never ask what they mean."
