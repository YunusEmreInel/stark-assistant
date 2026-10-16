"""Haber kaynakları (ücretsiz, anahtarsız RSS): Google Haberler ve Bing Haberler arama akışları, gündem için
ulusal ajans akışları. Hepsi tarihli; "dün ne oldu?" gibi sorular tarihe göre süzülebilir.

Ölçüm: yerel bir olay haberi için ddgs hiçbir şey bulamazken Google Haberler RSS olayı tarihiyle buldu.
"""
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import httpx

from ..memory.database import tr_lower
from .web import HEADERS, SearchError, Source

GOOGLE = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{hl}"
BING = "https://www.bing.com/news/search?q={q}&format=rss&setlang={hl}"
AGENDA_FEEDS = {  # gündem soruları için
    "AA": "https://www.aa.com.tr/tr/rss/default?cat=guncel",
    "TRT Haber": "https://www.trthaber.com/manset_articles.rss",
    "NTV": "https://www.ntv.com.tr/gundem.rss",
    "Hürriyet": "https://www.hurriyet.com.tr/rss/gundem",
}
ATOM = "{http://www.w3.org/2005/Atom}"


def _local_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        d = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d.astimezone() if d.tzinfo else d


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def _parse_feed(content: bytes, default_site: str = "") -> list[tuple[Source, datetime | None]]:
    root = ET.fromstring(content)
    out = []
    for it in root.findall(".//item") or root.findall(f".//{ATOM}entry"):
        title = (it.findtext("title") or it.findtext(f"{ATOM}title") or "").strip()
        link = it.findtext("link") or ""
        if not link:
            el = it.find(f"{ATOM}link")
            link = el.get("href", "") if el is not None else ""
        site = (it.findtext("source") or default_site).strip()
        if site and title.endswith(f" - {site}"):
            title = title[: -len(site) - 3]  # Google: "Başlık - Kaynak"
        when = _local_date(it.findtext("pubDate") or it.findtext(f"{ATOM}updated") or "")
        desc = _strip_html(it.findtext("description") or it.findtext(f"{ATOM}summary") or "")
        if desc.startswith(title[:40]):
            desc = ""  # Google açıklaması yalnızca başlığı tekrarlıyor
        src = Source(title, link.strip(), desc, date=when.date().isoformat() if when else "")
        src.publisher = site
        out.append((src, when))
    return out


def _get(url: str) -> bytes:
    r = httpx.get(url, headers=HEADERS, timeout=7, follow_redirects=True)
    r.raise_for_status()
    return r.content


def _norm(title: str) -> str:
    return re.sub(r"\W+", " ", tr_lower(title)).strip()[:60]


# "Partizan Fenerbahçe canlı izle şifresiz 【TRT1】" türü spam sayfalar (ölçüm: 8 sonucun 7'si böyleydi)
SPAM = re.compile(r"canlı\s*(izle|yayın)|şifresiz|\bizle\b|【|】|\$\$|→|!!|\[\[|selçuk\s*sport|taraftarium|"
                  r"justin\s*tv|live\s*stream|watch\s+live|free\s+stream", re.I)
PER_PUBLISHER = 2
# Her gün yayımlanan rutin/SEO sayfaları: "Son dakika deprem mi oldu?" gündem özetinde gerçek olay sanıldı
ROUTINE = re.compile(r"\bmi\s+oldu\?|nerede\s+oldu|son\s+depremler|namaz\s+vakit|altın\s+fiyat|döviz\s+kur|"
                     r"hangi\s+kanalda|saat\s+kaçta|ne\s+zaman\s*,|maç\s+özeti|nöbetçi\s+eczane|burç|"
                     r"\bloto\b|şans\s+topu|hava\s+durumu", re.I)


def _merge(items: list[tuple[Source, datetime | None]], limit: int, drop_routine: bool = False) -> list[Source]:
    """Spamı atar, aynı haberin kopyalarını tek tutar, yayıncı başına en fazla 2 haber, en yeni üstte."""
    seen, out, per_site = set(), [], {}
    for src, _ in sorted(items, key=lambda x: x[1] or datetime.min.astimezone(), reverse=True):
        key = _norm(src.title)
        if key in seen or not src.title or SPAM.search(src.title):
            continue
        if drop_routine and ROUTINE.search(src.title):
            continue
        site = src.site.lower()
        if per_site.get(site, 0) >= PER_PUBLISHER:
            continue
        seen.add(key)
        per_site[site] = per_site.get(site, 0) + 1
        out.append(src)
        if len(out) >= limit:
            break
    return out


def search(query: str, language: str, days: int = 7, limit: int = 8, drop_routine: bool = False,
           on_day: str | None = None) -> list[Source]:
    """Google Haberler + Bing Haberler; son `days` gün, en yeni üstte. Bing açıklama ve gerçek bağlantı verir.
    on_day ("2026-10-15"): Google'dan yalnızca o gün yayımlanan haberler ("dün ne oldu" sorusunda bugünün
    haberleri o günkülerin önüne geçiyordu)."""
    hl, gl = ("tr", "TR") if language != "en" else ("en", "US")
    if on_day:
        nxt = (datetime.fromisoformat(on_day) + timedelta(days=1)).strftime("%Y-%m-%d")
        gq = f"{query} after:{on_day} before:{nxt}"
    else:
        gq = f"{query} when:{days}d"
    urls = {"google": GOOGLE.format(q=quote(gq), hl=hl, gl=gl),
            "bing": BING.format(q=quote(query), hl=hl)}
    items: list[tuple[Source, datetime | None]] = []
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {name: pool.submit(_get, url) for name, url in urls.items()}
        for name, fut in futures.items():
            try:
                items += _parse_feed(fut.result())
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}: {e}")
    cutoff = datetime.now().astimezone() - timedelta(days=days)
    items = [(s, w) for s, w in items if w is None or w >= cutoff]
    if not items:
        raise SearchError("haber bulunamadı" + (f" ({'; '.join(errors)})" if errors else ""))
    # Bing öğeleri (açıklamalı, doğrudan bağlantılı) aynı başlıklı Google öğesinin önüne geçsin
    items.sort(key=lambda x: "bing.com" not in x[0].url)
    return _merge(items, limit, drop_routine)


def agenda(limit: int = 12, hours: int = 24) -> list[Source]:
    """Ulusal ajansların son `hours` saatlik manşetleri (gündem özeti için)."""
    items: list[tuple[Source, datetime | None]] = []
    with ThreadPoolExecutor(max_workers=len(AGENDA_FEEDS)) as pool:
        futures = {site: pool.submit(_get, url) for site, url in AGENDA_FEEDS.items()}
        for site, fut in futures.items():
            try:
                items += _parse_feed(fut.result(), default_site=site)
            except Exception:  # noqa: BLE001 — bir akış çalışmazsa diğerleri yeter
                pass
    cutoff = datetime.now().astimezone() - timedelta(hours=hours)
    items = [(s, w) for s, w in items if w and w >= cutoff]
    if not items:
        raise SearchError("gündem akışları okunamadı")
    return _merge(items, limit, drop_routine=True)


_TEAM = r"[A-ZÇĞİÖŞÜ][\wçğıöşü.]+(?:\s+[A-ZÇĞİÖŞÜ][\wçğıöşü.]+)?"
_FIXTURE = re.compile(rf"({_TEAM})\s*[-–]\s*({_TEAM})(?:['’]\w+)?\s+(?:maç|karşılaşma)", re.U)


def upcoming_fixture(sources, team_words: str) -> tuple[str, str] | None:
    """Haber başlıklarından sorulan takımın sıradaki maçı: ("Fenerbahçe", "Alanyaspor").
    Başlıklar "X-Y maçı ne zaman, saat kaçta" kalıbındadır; en yeni haberlerde en çok geçen eşleşme seçilir."""
    wanted = {w.lower()[:5] for w in re.findall(r"\w{3,}", team_words)}
    counts: dict[tuple[str, str], float] = {}
    for rank, s in enumerate(sources):
        for a, b in _FIXTURE.findall(s.title):
            if {a.lower()[:5], b.lower()[:5]} & wanted:
                counts[(a, b)] = counts.get((a, b), 0) + 1 + 0.1 / (rank + 1)  # eşitlikte daha yeni haber
    return max(counts, key=counts.get) if counts else None
