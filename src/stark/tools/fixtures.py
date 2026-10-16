"""Süper Lig takımlarının maç programı ve sonuçları: ESPN'in herkese açık fikstür verisi (anahtar gerekmez).

Haber başlıkları maç saatini yazmıyor, haber metinleri de çoğu zaman okunamıyordu; model saat uyduruyor ya da
geçmiş maçı "yarınki" diye anlatıyordu. Fikstür yapılandırılmış veridir: cevabı kod kurar, model karışmaz.
"""
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
TR_TZ = timezone(timedelta(hours=3))  # Türkiye (UTC+3); testlerde kullanılır, uygulama bilgisayarın saat dilimini kullanır
# Sezon başında güncellenen liste ESPN'den okunur; erişilemezse bu yedek kullanılır
FALLBACK_TEAMS = {"Alanyaspor": "9078", "Amed SFK": "132335", "Besiktas": "1895", "Caykur Rizespor": "7656",
                  "Erzurum BB": "19267", "Eyupspor": "20729", "Fenerbahce": "436", "Galatasaray": "432",
                  "Gaziantep FK": "20070", "Genclerbirligi": "996", "Goztepe": "789", "Istanbul Basaksehir": "7914",
                  "Kasimpasa": "6870", "Kocaelispor": "995", "Konyaspor": "7648", "Samsunspor": "11429",
                  "Trabzonspor": "997", "Çorum FK": "132334"}
TR_NAMES = {"Besiktas": "Beşiktaş", "Fenerbahce": "Fenerbahçe", "Caykur Rizespor": "Çaykur Rizespor",
            "Erzurum BB": "Erzurumspor", "Eyupspor": "Eyüpspor", "Genclerbirligi": "Gençlerbirliği",
            "Goztepe": "Göztepe", "Istanbul Basaksehir": "Başakşehir", "Kasimpasa": "Kasımpaşa",
            "Gaziantep FK": "Gaziantep", "Slavia Prague": "Slavia Prag", "Atlético Madrid": "Atletico Madrid",
            "Bayern Munich": "Bayern Münih", "Internazionale": "Inter", "Ajax Amsterdam": "Ajax", "Shakhtar Donetsk": "Şahtar Donetsk"}
ALIASES = {"fb": "Fenerbahce", "fener": "Fenerbahce", "gs": "Galatasaray", "cimbom": "Galatasaray",
           "bjk": "Besiktas", "ts": "Trabzonspor", "trabzon": "Trabzonspor", "basaksehir": "Istanbul Basaksehir",
           "rize": "Caykur Rizespor", "rizespor": "Caykur Rizespor", "erzurumspor": "Erzurum BB",
           "gaziantep": "Gaziantep FK", "antep": "Gaziantep FK", "corum": "Çorum FK", "amedspor": "Amed SFK",
           "amed": "Amed SFK"}
LEAGUES = {"Turkish Super Lig": "Süper Lig", "UEFA Champions League": "Şampiyonlar Ligi",
           "UEFA Europa League": "Avrupa Ligi", "UEFA Conference League": "Konferans Ligi",
           "Turkish Cup": "Türkiye Kupası", "Spanish LALIGA": "La Liga",
           "English Premier League": "Premier Lig", "German Bundesliga": "Bundesliga", "Italian Serie A": "Serie A",
           "French Ligue 1": "Ligue 1", "Portuguese Primeira Liga": "Portekiz Ligi", "Dutch Eredivisie": "Eredivisie",
           "English FA Cup": "FA Cup", "Spanish Copa del Rey": "İspanya Kral Kupası", "Club Friendly": "hazırlık maçı", "Turkish Super Cup": "Süper Kupa"}
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım",
          "Aralık"]
DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

RESULT = re.compile(r"son\s+maç|kaç\s+kaç|skor|kazan|yendi|yenildi|kaybetti|berabere|sonuç|bitti|dünkü\s+maç|"
                    r"\bdün\b.*maç", re.I)
UPCOMING = re.compile(r"\byarın\w*|ne\s+zaman|saat\s+kaç|\bkaçta|hangi\s+(?:gün|kanal)|sonraki|sıradaki|"
                      r"gelecek\s+maç|önümüzdeki|bugün\w*\s+maç|bugünkü|\bmaçı\s+var\s+mı|maç\s+var\s+mı", re.I)
OTHER_SPORT = re.compile(r"basketbol|voleybol|hentbol|kadın|euroleague|u19|altyapı", re.I)


@dataclass(frozen=True)
class FixtureQuery:
    team: str           # ESPN adı: "Fenerbahce"
    mode: str           # "next" | "result"
    day: int | None = None  # bugüne göre gün farkı: 1 = yarın, 0 = bugün, -1 = dün


def _fold(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower().translate(str.maketrans("çğıöşü", "cgiosu"))


FOREIGN_LEAGUES = ("eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "por.1", "ned.1")
FOREIGN_ALIASES = {"barselona": "Barcelona", "barca": "Barcelona", "bayern munih": "Bayern Munich",
                   "psg": "Paris Saint-Germain", "inter": "Internazionale", "manchester united": "Manchester United",
                   "man united": "Manchester United", "manchester city": "Manchester City", "liverpul": "Liverpool",
                   "juve": "Juventus", "atletico madrid": "Atlético Madrid", "atletiko madrid": "Atlético Madrid",
                   "real madrit": "Real Madrid", "ajaks": "Ajax Amsterdam", "benfika": "Benfica"}
_GENERIC = {"real", "city", "united", "club", "athletic", "sporting", "inter", "atletico"}
_foreign: dict[str, str] = {}          # ESPN adı → kimlik (ilk yabancı takım sorusunda yüklenir)
_foreign_keys: dict[str, str] = {}     # katlanmış ad/kısa ad → ESPN adı
_lock = threading.Lock()


def _load_foreign(client=None) -> None:
    with _lock:
        if _foreign:
            return
        def league(slug):
            d = (client or httpx).get(f"{BASE}/{slug}/teams", timeout=10).json()
            return [x["team"] for x in d["sports"][0]["leagues"][0]["teams"]]
        with ThreadPoolExecutor(max_workers=len(FOREIGN_LEAGUES)) as pool:
            for teams in pool.map(league, FOREIGN_LEAGUES):
                for t in teams:
                    _foreign[t["displayName"]] = t["id"]
                    for key in {t["displayName"], t.get("shortDisplayName") or ""}:
                        k = _fold(key)
                        if len(k) >= 4 and k not in _GENERIC:
                            _foreign_keys.setdefault(k, t["displayName"])
        for alias, name in FOREIGN_ALIASES.items():
            if name in _foreign:
                _foreign_keys[alias] = name


def _clean_words(text: str) -> list[str]:
    return re.findall(r"\w+", _fold(re.sub(r"['’]\w*", "", text)))


def find_team(text: str, teams=FALLBACK_TEAMS) -> str | None:
    words = _clean_words(text)
    for w in words:
        if w in ALIASES:
            return ALIASES[w]
    for name in teams:
        key = _fold(name).split()[0] if name != "Istanbul Basaksehir" else "basaksehir"
        if len(key) >= 4 and any(w.startswith(key) for w in words):
            return name
    return None


def find_foreign_team(text: str, client=None) -> str | None:
    _load_foreign(client)
    joined = f" {' '.join(_clean_words(text))} "
    hits = [k for k in _foreign_keys if f" {k} " in joined]
    return _foreign_keys[max(hits, key=len)] if hits else None  # "manchester city", "city" değil


def _mode(text: str) -> tuple[str, int | None] | None:
    if OTHER_SPORT.search(text) or not re.search(r"maç|skor|kaç\s+kaç|oyna|kazan|yendi|yenildi|berabere", text, re.I):
        return None
    day = 1 if re.search(r"\byarın", text, re.I) else 0 if re.search(r"\bbugün", text, re.I) else \
        -1 if re.search(r"\bdün", text, re.I) else None
    if RESULT.search(text) and not re.search(r"\byarın|ne\s+zaman|saat\s+kaç|kaçta", text, re.I):
        return "result", day
    if UPCOMING.search(text):
        return "next", day
    return None


def is_match_question(text: str) -> bool:
    """Maç saati/sonucu sorusu mu (takım henüz bilinmeden; yabancı takım listesi gerekirse yüklenir)."""
    return _mode(text) is not None


def parse(text: str, foreign: bool = False, client=None) -> FixtureQuery | None:
    mode = _mode(text)
    if not mode:
        return None
    team = find_team(text) or (find_foreign_team(text, client) if foreign else None)
    return FixtureQuery(team, *mode) if team else None


# ---- veri ----
@dataclass
class Match:
    when: datetime          # bilgisayarın saat diliminde
    home: str
    away: str
    league: str
    state: str              # pre | in | post
    home_score: int | None = None
    away_score: int | None = None
    clock: str = ""


def _team_id(team: str) -> str:
    return FALLBACK_TEAMS.get(team) or _foreign.get(team, "")


def _events(team_id: str, upcoming: bool, client=None, tz=None) -> list[Match]:
    url = f"{BASE}/all/teams/{team_id}/schedule" + ("?fixture=true" if upcoming else "")
    data = (client or httpx).get(url, timeout=10).json()
    out = []
    for e in data.get("events", []):
        c = e["competitions"][0]
        teams = {x["homeAway"]: x for x in c["competitors"]}
        if "home" not in teams or "away" not in teams:
            continue
        status = c.get("status", {}).get("type", {})
        score = lambda x: int(x["score"]["value"]) if isinstance(x.get("score"), dict) else None  # noqa: E731
        league = e.get("league", {}).get("name", "") if isinstance(e.get("league"), dict) else ""
        out.append(Match(datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(tz),
                         teams["home"]["team"]["displayName"], teams["away"]["team"]["displayName"],
                         LEAGUES.get(league, league), status.get("state", "pre"),
                         score(teams["home"]), score(teams["away"]), c.get("status", {}).get("displayClock", "")))
    return sorted(out, key=lambda m: m.when)


def tr(name: str) -> str:
    return TR_NAMES.get(name, name)


def gen(name: str) -> str:
    """Tamlayan eki: Fenerbahçe'nin, Galatasaray'ın, Trabzonspor'un, Göztepe'nin."""
    low = name.lower()
    if re.search(r"[^aeıioöuü]y$", low):  # "City" → "Siti": "City'nin"
        low = low[:-1] + "i"
    vowels = [c for c in low if c in "aeıioöuü"]
    last = vowels[-1] if vowels else "ı"
    suffix = {"a": "ın", "ı": "ın", "e": "in", "i": "in", "o": "un", "u": "un", "ö": "ün", "ü": "ün"}[last]
    return f"{name}'{'n' if low[-1] in 'aeıioöuü' else ''}{suffix}"


def _when(m: Match, today: date) -> str:
    d = m.when.date()
    rel = {0: "bugün", 1: "yarın", -1: "dün"}.get((d - today).days)
    base = f"{d.day} {MONTHS[d.month - 1]} {DAYS[d.weekday()]}"
    return f"{rel}, {base}" if rel else base


def _score_line(m: Match, team: str) -> str:
    us_home = m.home == team
    ours, theirs = (m.home_score, m.away_score) if us_home else (m.away_score, m.home_score)
    opp = tr(m.away if us_home else m.home)
    if ours is None or theirs is None:
        return f"{tr(team)} - {opp} maçının skoru henüz yok"
    verb = "kazandı" if ours > theirs else "kaybetti" if ours < theirs else "berabere kaldı"
    return f"{tr(m.home)} {m.home_score}, {tr(m.away)} {m.away_score}. {tr(team)} {verb}"


def answer(q: FixtureQuery, now: datetime | None = None, client=None) -> str:
    now = now or datetime.now().astimezone()  # maç saati bilgisayarın saat diliminde söylenir
    tz = now.tzinfo
    today = now.date()
    team_id = _team_id(q.team)
    name = tr(q.team)
    if q.mode == "next":
        matches = [m for m in _events(team_id, True, client, tz) if m.state != "post"]
        live = [m for m in _events(team_id, False, client, tz) if m.state == "in"]
        if live:
            m = live[0]
            return (f"{name} şu an {tr(m.away if m.home == q.team else m.home)} ile oynuyor patron: "
                    f"{tr(m.home)} {m.home_score}, {tr(m.away)} {m.away_score}.")
        if not matches:
            return f"{gen(name)} programda görünen bir maçı yok patron."
        target = [m for m in matches if q.day is not None and (m.when.date() - today).days == q.day]
        m = (target or matches)[0]
        place = "evinde" if m.home == q.team else "deplasmanda"
        opp = tr(m.away if m.home == q.team else m.home)
        line = (f"{tr(m.home)} - {tr(m.away)}, {_when(m, today)} saat {m.when:%H.%M}, {m.league}. "
                f"{name} {place}, rakip {opp}.")
        if q.day is not None and not target:
            day_word = {0: "Bugün", 1: "Yarın", -1: "Dün"}.get(q.day, "O gün")
            return f"{day_word} {gen(name)} maçı yok patron. Sıradaki maçı: {line}"
        return f"{gen(name)} maçı: {line}"
    # sonuç
    played = [m for m in _events(team_id, False, client, tz) if m.state in ("post", "in")]
    if q.day is not None:
        played = [m for m in played if (m.when.date() - today).days == q.day] or []
        if not played:
            day_word = {0: "Bugün", 1: "Yarın", -1: "Dün"}.get(q.day, "O gün")
            return f"{day_word} {gen(name)} oynadığı bir maç yok patron."
    if not played:
        return f"{gen(name)} bu sezon oynanmış maçını bulamadım patron."
    m = played[-1]
    if m.state == "in":
        return f"Maç şu an oynanıyor patron ({m.clock}): {tr(m.home)} {m.home_score}, {tr(m.away)} {m.away_score}."
    return f"{gen(name)} son maçı {_when(m, today)}, {m.league}: {_score_line(m, q.team)}."
