"""Bir sorunun internet gerektirip gerektirmediğine ve hangi araca gideceğine kodla karar verir."""
import re
from dataclasses import dataclass

from ..ai.conversation import LIVE_INFO
from . import currency, weather

EXPLICIT = re.compile(
    r"^(?:lütfen\s+)?(?:internette|webde|google'?da|googledan|internetten)\s+(?:ara(?:r\s+mısın|yın)?|bak|araştır)\w*"
    r"\s*[:,]?\s*(?P<q>.*)$|^(?P<q2>.+?)\s+(?:diye\s+)?(?:internette|webde|internetten|google'?da)\s+"
    r"(?:ara|bak|araştır)\w*\W*$|^(?:search\s+(?:the\s+web|online|the\s+internet)\s+for|look\s+up|google)\s+(?P<q3>.+)$",
    re.I)
WEATHER = re.compile(r"hava\s*(durumu|nasıl|nasil|kaç\s+derece|sıcak|soğuk|yağmur)|yağmur\s+yağacak|kar\s+yağacak|"
                     r"kaç\s+derece|sıcaklık|weather|forecast|temperature|will\s+it\s+rain", re.I)
CURRENCY = re.compile(r"dolar|euro|avro|sterlin|\bfrank\b|\byen\b|ruble|\bkur(u|lar)?\b|döviz|exchange\s+rate|"
                      r"dollar|pound", re.I)


# Modelin bilgisi eskidir: güncellik isteyen sorular aranır ("Python 3.14'te neler yeni?" → model "henüz çıkmadı" dedi)
RECENT = re.compile(
    r"\b(yeni(lik)?(ler)?|yenilikleri|son\s+(sürüm|versiyon|durum|gelişme|dakika)|güncel|sürüm|versiyon|"
    r"çıktı\s+mı|çıkacak|ne\s+zaman\s+çık|bu\s+(yıl|hafta|ay|sezon)|geçen\s+(hafta|ay)|şu\s+an(ki)?|"
    r"20[2-3]\d|latest|newest|release[sd]?|version|current(ly)?|this\s+(year|week|month))\b", re.I)
# Kesin cevaplı bilgi soruları (bilgi doğrulama modu): model bunları tutarlı yakalayamıyor
FACT = re.compile(
    r"\bkaç\s+(?:tane\s+|adet\s+)?[a-zçğıöşü]{3,}|\bhangi(?:si|leri|sidir)?\b|\bkim(?:dir|di)?\b|\bne\s+zaman\b|"
    r"\bhangi\s+yıl|\ben\s+(?:büyük|yüksek|uzun|küçük|kalabalık|eski|derin|hızlı|zengin|çok)\w*|"
    r"\b\w+(?:leri|ları)(?:ni|nı)?\s+(?:nelerdir|neler|anlat|say|listele|sırala)\w*|\bnelerdir\b|"
    r"\bhow\s+many\b|\bwho\s+(?:is|was|invented|wrote|discovered)\b|\bwhen\s+(?:did|was)\b|\bwhich\b|"
    r"\b(?:largest|highest|longest|biggest|tallest)\b", re.I)
NEWS = re.compile(r"haber|gündem|son\s+dakika|neler\s+oluyor|ne\s+oldu|news|headlines|"
                  r"maç|skor|kaç\s+kaç|kazandı|yendi|puan\s+durumu|match|score|won\b|"
                  r"olay|kaza|patla|yangın|deprem|\bsel\b|cinayet|saldırı|kavga|öldü|yaralı|gözaltı|tutukla|"
                  r"operasyon|accident|explosion|fire\b|earthquake|killed|arrest", re.I)
# Arama motoruna gidecek anahtar kelimeler: soru kalıpları ve ekler atılır
_STOP = set("""neler ne nedir neydi var mı mi mu mü acaba bana bize söyler söyleyebilir misin misiniz musun musunuz
bir bu şu kaç nasıl oldu olan olarak bitti bugünkü lütfen hakkında ile ve de da peki şimdi biliyor
what is are the a an of did do does tell me about please""".split())


# Haber aramasında yalnızca özel isimler işe yarıyor: "Fenerbahçe" dünkü maçı buluyor,
# "Fenerbahçe son maçı" / "Fenerbahçe maç sonucu" hiç sonuç döndürmüyor (ölçüm, 16.10.2026).
_NEWS_GENERIC = ("son", "maç", "sonuç", "skor", "kazan", "yend", "yenil", "oyna", "haber", "gündem", "bugün", "dün",
                 "olay", "bul", "anlat", "araştır",
                 "neler", "dakika", "latest", "last", "match", "score", "game", "news", "today", "yesterday",
                 "result")


# "Gündemde neler var?" genel özet ister (sorgu olduğu gibi kalır; yalnız "Türkiye" İngilizce, ilgisiz
# haber getiriyordu). "Fenerbahçe'nin son maçı?" tek olay sorar (yalnız özel isim aranır).
NEWS_LIST = re.compile(r"gündem|neler|son\s+dakika|haberler|headlines|what'?s\s+(new|happening)", re.I)


# Konu bildirmeyen kelimeler: "Zafer Partisi'nde yeni haberler var mı, bugün ne oldu mesela?" → konu: Zafer Partisi
_NOT_TOPIC = ("yeni", "mesela", "önemli", "neymiş", "oluyor", "olmuş", "gelişme", "türkiye", "dünya", "ülke",
              "var", "yok", "acil")


def topic_words(text: str) -> list[str]:
    """Haber sorusundaki konu kelimeleri (genel kelimeler ve tekrarlar atılır)."""
    out: list[str] = []
    for w in keywords(text).split():
        low = w.replace("İ", "i").lower()
        if len(low) > 1 and not low.startswith(_NEWS_GENERIC + _NOT_TOPIC) and low not in (x.lower() for x in out):
            out.append(w)
    return out


def is_agenda(text: str) -> bool:
    """Genel gündem özeti mi ("Gündemde neler var?", "Son dakika haberleri")? Bir konu adı geçiyorsa
    ("Zafer Partisi'nde neler oldu?") o konunun haberleri aranır, genel manşetler değil."""
    return bool(NEWS_LIST.search(text)) and not topic_words(text)


def news_keywords(text: str) -> str:
    if NEWS_LIST.search(text):
        return " ".join(topic_words(text)) or keywords(text)
    words = [w for w in keywords(text).split() if not w.lower().startswith(_NEWS_GENERIC)]
    return " ".join(words) or keywords(text)


def keywords(text: str) -> str:
    words = []
    for w in re.findall(r"[\wçğıöşüÇĞİÖŞÜ'’.+#-]+", text):
        base = re.split(r"['’]", w)[0].strip(".-")  # "Türkiye'nin" → "Türkiye"
        if base and base.lower() not in _STOP:
            words.append(base)
    return " ".join(words) or text


# "Maç Kolik sitesine bak", "Vikipedi'den bak": önceki soru o sitede aranır
SITE_REQUEST = re.compile(r"^(?:bir\s+de\s+|o\s+zaman\s+|peki\s+)?(?P<site>[\wçğıöşüÇĞİÖŞÜ .]{2,30}?)['’]?\s*"
                          r"(?P<kind>sitesin(?:e|den|de)|sayfasın(?:a|dan|da)|['’]?(?:den|dan|ye|ya|e|a)\s+)\s*"
                          r"(?:girip\s+|gir\w*\s+(?:ve\s+)?)?(?:bak|ara|kontrol\s+et)\w*\W*$", re.I)
KNOWN_SITES = {"mackolik": "mackolik.com", "sahadan": "sahadan.com", "transfermarkt": "transfermarkt.com.tr",
               "vikipedi": "tr.wikipedia.org", "wikipedia": "tr.wikipedia.org", "eksisozluk": "eksisozluk.com",
               "eksi": "eksisozluk.com", "tff": "tff.org", "fotomac": "fotomac.com.tr", "fanatik": "fanatik.com.tr",
               "hurriyet": "hurriyet.com.tr", "ntv": "ntv.com.tr", "ntvspor": "ntvspor.net", "trthaber": "trthaber.com",
               "beinsports": "beinsports.com.tr", "sozcu": "sozcu.com.tr", "milliyet": "milliyet.com.tr",
               "sabah": "sabah.com.tr", "aa": "aa.com.tr", "anadoluajansi": "aa.com.tr", "tdk": "sozluk.gov.tr"}


def site_request(text: str) -> str | None:
    """Söylenen site adı: bilinen siteler için alan adı ("Maç Kolik" → mackolik.com), değilse adın kendisi."""
    m = SITE_REQUEST.match(text.strip())
    if not m:
        return None
    name = m.group("site").strip()
    if re.search(r"\b(?:internet|google|web|chrome|youtube)\b", name, re.I) or len(name.split()) > 3:
        return None  # "internetten bak" açık arama komutu; "YouTube'da ara" bilgisayar komutu
    if re.match(r"(?:bu|şu|o)\b", name, re.I):
        return None  # "bu sayfaya bak" ekranı okuma isteği
    key = re.sub(r"[\s.]|com$|net$", "", name.replace("İ", "i").lower().translate(str.maketrans("çğıöşü", "cgiosu")))
    if key in KNOWN_SITES:
        return KNOWN_SITES[key]
    # "Ahmet'e bak" site değil: bilinmeyen adlar yalnızca "… sitesine/sayfasına" denirse
    return name if m.group("kind").lower().startswith(("site", "sayfa")) else None


@dataclass(frozen=True)
class Route:
    kind: str           # "weather" | "currency" | "search" | "news"
    query: str = ""
    city: str | None = None
    day: int = 0
    pair: tuple[str, str] | None = None


def route(text: str, default_city: str = "") -> Route | None:
    t = text.strip()
    m = EXPLICIT.match(t)
    if m:
        q = (m.group("q") or m.group("q2") or m.group("q3") or "").strip(" ?.!")
        if len(keywords(q).split()) < 1 or q.lower() in ("bunu", "şunu", "onu", "this", "that", "it"):
            # "İnternetten araştır." — aranacak konu önceki sorudadır; motor onu kullanır
            return Route("search", "")
        return Route("news", news_keywords(q)) if NEWS.search(q) else Route("search", keywords(q))
    if WEATHER.search(t):
        return Route("weather", city=weather.find_city(t) or default_city or None, day=weather.find_day(t))
    if CURRENCY.search(t) and re.search(r"\b(?:neden|niçin|niye|sebeb\w*|yüzünden|why)\b", t, re.I):
        return Route("news", news_keywords(t))  # "Dolar neden yükseldi?": kur değil haber/yorum
    if CURRENCY.search(t):
        pair = currency.find_pair(t)
        if pair:
            return Route("currency", pair=pair)
        return Route("search", keywords(t))  # ör. "altın kuru", "bitcoin"
    if NEWS.search(t):
        return Route("news", news_keywords(t))
    if LIVE_INFO.search(t) or RECENT.search(t):
        return Route("search", keywords(t))
    return None
