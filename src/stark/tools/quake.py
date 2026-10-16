"""Son depremler: Kandilli Rasathanesi'nin herkese açık listesi (son 500 deprem, Türkiye saati).

Haber aramasıyla "son deprem nerede oldu?" sorusuna model "İstanbul, Ankara ve İzmir'de" gibi uyduruyordu.
Liste yapılandırılmış veridir: cevabı kod kurar.
"""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

URL = "http://www.koeri.boun.edu.tr/scripts/lst0.asp"
PROVINCES = ["Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin", "Aydın",
             "Balıkesir", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum",
             "Denizli", "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun",
             "Gümüşhane", "Hakkari", "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu",
             "Kayseri", "Kırklareli", "Kırşehir", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş",
             "Mardin", "Muğla", "Muş", "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop",
             "Sivas", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak",
             "Aksaray", "Bayburt", "Karaman", "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova",
             "Karabük", "Kilis", "Osmaniye", "Düzce"]
TRIGGER = re.compile(r"deprem|sarsıntı|zelzele|earthquake", re.I)
QUESTION = re.compile(r"oldu|nerede|nereye|son\b|kaç|büyüklü|şiddet|var\s+m|mı\s+ol|az\s+önce|şimdi|bugün|dün|"
                      r"sallan|hissed", re.I)
BIG = re.compile(r"büyük|şiddetli|korkutan|ciddi|yıkıcı", re.I)
_ROW = re.compile(r"^(\d{4})\.(\d\d)\.(\d\d)\s+(\d\d):(\d\d):\d\d\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s+"
                  r"([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+(.+?)\s{2,}", re.M)


def _fold(s: str) -> str:
    return s.replace("İ", "I").replace("ı", "i").upper().translate(str.maketrans("ÇĞÖŞÜ", "CGOSU"))


_BY_FOLD = {_fold(p): p for p in PROVINCES}


@dataclass(frozen=True)
class QuakeQuery:
    province: str | None = None   # "İzmir"
    big: bool = False             # "son büyük deprem": 4 ve üstü


@dataclass
class Quake:
    when: datetime
    depth: float
    magnitude: float
    place: str        # "IKIZBASAK-DIVRIGI (SIVAS)"

    @property
    def province(self) -> str:
        m = re.search(r"\(([^)]+)\)", self.place)
        return _BY_FOLD.get(_fold(m.group(1)), m.group(1).title()) if m else ""

    @property
    def spoken_place(self) -> str:
        """"IKIZBASAK-DIVRIGI (SIVAS)" → "Sivas Divrigi"; denizdeki depremler "Ege Denizi" gibi kalır."""
        district = re.sub(r"\s*\(.*\)", "", self.place).split("-")[-1].strip().title()
        prov = self.province
        if not prov:
            return self.place.title()
        return prov if _fold(district) == _fold(prov) else f"{prov} {district}"


def parse(text: str) -> QuakeQuery | None:
    if not TRIGGER.search(text) or not QUESTION.search(text):
        return None
    words = re.findall(r"\w+", re.sub(r"['’]\w*", "", text))
    province = next((_BY_FOLD[_fold(w)] for w in words if _fold(w) in _BY_FOLD), None)
    return QuakeQuery(province, bool(BIG.search(text)))


def fetch(client=None) -> list[Quake]:
    raw = (client or httpx).get(URL, timeout=10, follow_redirects=True).content
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("windows-1254", "replace")
    out = []
    for y, mo, d, h, mi, depth, md, ml, mw, place in _ROW.findall(text):
        mags = [float(x) for x in (mw, ml, md) if re.fullmatch(r"\d+(?:\.\d+)?", x) and float(x) > 0]
        if mags:
            out.append(Quake(datetime(int(y), int(mo), int(d), int(h), int(mi)), float(depth), mags[0],
                             place.strip()))
    return out  # en yeni başta


def _num(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _when(q: Quake, now: datetime) -> str:
    days = (now.date() - q.when.date()).days
    day = {0: "bugün", 1: "dün"}.get(days, f"{q.when.day}.{q.when.month:02d}")
    return f"{day} saat {q.when:%H.%M}"


def describe(q: Quake, now: datetime) -> str:
    return (f"{_when(q, now)}, {q.spoken_place}, büyüklüğü {_num(q.magnitude)}, "
            f"derinliği {q.depth:.0f} kilometre")


def answer(query: QuakeQuery, now: datetime | None = None, client=None) -> str:
    now = now or datetime.now()
    quakes = fetch(client)
    if not quakes:
        return "Kandilli'nin deprem listesine şu an ulaşamadım patron."
    pool = [q for q in quakes if q.province == query.province] if query.province else quakes
    if query.big:
        pool = [q for q in pool if q.magnitude >= 4.0]
    if not pool:
        span = (now - quakes[-1].when).days or 1
        size = "4 ve üzeri büyüklükte " if query.big else ""
        return f"Kandilli'ye göre son {span} günde {query.province + ' ilinde ' if query.province else ''}" \
               f"{size}deprem olmamış patron."
    where = f"{query.province} ilindeki " if query.province else ""
    reply = f"Kandilli'ye göre {where}son {'büyük ' if query.big else ''}deprem {describe(pool[0], now)}."
    if not query.big:
        day = [q for q in quakes if now - q.when <= timedelta(hours=24) and q.magnitude >= 3.5]
        biggest = max(day, key=lambda q: q.magnitude, default=None)
        if biggest and biggest is not pool[0] and (not query.province or biggest.province == query.province):
            reply += f" Son 24 saatin en büyüğü: {describe(biggest, now)}."
    return reply
