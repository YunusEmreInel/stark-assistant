"""Web araması: yerel SearXNG (varsa), yoksa DuckDuckGo (ddgs). İlk birkaç sayfanın okunabilir metni alınır.

İnternetten gelen metin talimat değil VERİDİR; modele bu açıkça söylenir. Her istekte zaman ve boyut sınırı var.
"""
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

MAX_PAGE_BYTES = 1_500_000
PAGE_CHARS = 30_000      # sayfanın tamamı okunur; modele yalnızca soruyla ilgili paragraflar gider
CHUNK_CHARS = 450
FETCH_TIMEOUT = 5
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Stark/0.1 (personal assistant)",
           "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7"}
WIKI_HEADERS = {"User-Agent": "StarkAssistant/1.0 (personal voice assistant; https://github.com/) httpx",
                "Accept-Language": "tr-TR,tr;q=0.9"}


class SearchError(Exception):
    pass


@dataclass
class Source:
    title: str
    url: str
    snippet: str
    text: str = ""          # modele gidecek (seçilmiş) metin
    date: str = ""
    publisher: str = ""     # haber akışlarında yayıncı adı (bağlantı yönlendirme adresi olabilir)
    full: str = ""          # sayfanın okunmuş tam metni

    @property
    def site(self) -> str:
        return self.publisher or urlparse(self.url).netloc.removeprefix("www.")


def _searxng(query: str, base_url: str, language: str, limit: int) -> list[Source]:
    r = httpx.get(f"{base_url}/search", params={"q": query, "format": "json", "language": language},
                  timeout=6, headers=HEADERS)
    r.raise_for_status()
    out = []
    for item in r.json().get("results", [])[:limit]:
        out.append(Source(item.get("title", ""), item.get("url", ""), item.get("content", ""),
                          date=(item.get("publishedDate") or "")[:10]))
    return out


def _ddg(query: str, language: str, limit: int) -> list[Source]:
    """ddgs birden fazla arama motorunu dener; sık sorguda geçici boş dönebildiği için bir kez yeniden dener."""
    from ddgs import DDGS
    region = "tr-tr" if language == "tr" else "us-en"
    results: list[dict] = []
    for attempt in range(2):
        try:
            with DDGS(timeout=6) as d:
                results = d.text(query, region=region, max_results=limit, backend="auto") or []
        except Exception:  # noqa: BLE001 — "No results found" de istisna olarak geliyor
            results = []
        if results:
            break
        time.sleep(1.5)
    return [Source(x.get("title", ""), x.get("href", ""), x.get("body", "")) for x in results]


def search(query: str, language: str, searxng_url: str = "", limit: int = 5) -> tuple[list[Source], str]:
    """(sonuçlar, kullanılan sağlayıcı). SearXNG erişilemezse DuckDuckGo'ya düşer."""
    errors = []
    if searxng_url:
        try:
            res = _searxng(query, searxng_url, language, limit)
            if res:
                return res, "SearXNG"
        except (httpx.HTTPError, ValueError) as e:
            errors.append(f"SearXNG: {e}")
    try:
        res = _ddg(query, language, limit)
        if res:
            return res, "DuckDuckGo"
    except Exception as e:  # noqa: BLE001 — ddgs çeşitli hatalar fırlatabiliyor
        errors.append(f"DuckDuckGo: {e}")
    raise SearchError("; ".join(errors) or "sonuç yok")


def _page_text(url: str) -> str:
    import trafilatura
    try:
        # Vikipedi tarayıcı taklidi yapan istemcileri 403 ile reddediyor; kendini tanıtan istemciye izin veriyor
        headers = WIKI_HEADERS if "wikipedia.org" in url else HEADERS
        with httpx.stream("GET", url, timeout=FETCH_TIMEOUT, headers=headers, follow_redirects=True) as r:
            if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
                return ""
            body = b""
            for chunk in r.iter_bytes():
                body += chunk
                if len(body) > MAX_PAGE_BYTES:
                    break
    except httpx.HTTPError:
        return ""
    text = trafilatura.extract(body.decode(r.encoding or "utf-8", errors="replace"),
                               include_comments=False, include_tables=False, favor_precision=True) or ""
    return text[:PAGE_CHARS]


def enrich(sources: list[Source], pages: int = 5, prefer: str = "") -> None:
    """İlk birkaç sonucun sayfa metnini paralel okur (Google Haberler yönlendirmeleri okunamaz, atlanır).
    prefer: verilirse başlığı bu metinle en çok örtüşen sonuçlar okunur (en yeni ama ilgisiz haber yerine)."""
    targets = [s for s in sources if "news.google.com" not in s.url]
    if prefer:
        want = _stems(prefer)
        targets.sort(key=lambda s: -len(_stems(s.title) & want))  # sıralama kararlı: eşitlikte yeni olan önde
    targets = targets[:pages]
    if not targets:
        return
    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        for src, text in zip(targets, pool.map(lambda s: _page_text(s.url), targets)):
            src.full = text


# ---- soruyla ilgili paragrafları seçme ----
_STOP = set("""için ile gibi daha çok olan olarak ama veya hem değil bir bu şu o ne nasıl neden niye kaç hangi
mı mi mu mü var yok son yeni the and for with from that this what how when where which""".split())


def _stems(text: str) -> set[str]:
    words = re.findall(r"[0-9a-zçğıöşü]+", text.replace("I", "ı").replace("İ", "i").lower())
    return {w[:5] for w in words if len(w) >= 3 and w not in _STOP}


def _chunks(text: str) -> list[str]:
    """Paragraflara böler, kısa paragrafları ~CHUNK_CHARS uzunluğa kadar birleştirir."""
    out, cur = [], ""
    for para in (p.strip() for p in text.split("\n")):
        if not para:
            continue
        if cur and len(cur) + len(para) > CHUNK_CHARS:
            out.append(cur)
            cur = ""
        cur = f"{cur} {para}".strip()
        while len(cur) > CHUNK_CHARS * 2:  # tek çok uzun paragraf
            cut = cur.rfind(". ", 0, CHUNK_CHARS) + 1 or CHUNK_CHARS
            out.append(cur[:cut].strip())
            cur = cur[cut:].strip()
    if cur:
        out.append(cur)
    return out


def select_passages(sources: list[Source], question: str, budget: int = 3600) -> None:
    """Her kaynağın tam metninden soruyla en çok ortak kelimesi olan paragrafları seçip src.text'e yazar.
    Sayfanın başı çoğu zaman menü/çerez uyarısı olduğundan ilk N karakteri vermek cevabı kaçırıyordu."""
    q = _stems(question)
    scored = []
    for si, src in enumerate(sources):
        for ci, chunk in enumerate(_chunks(src.full)):
            st = _stems(chunk)
            hits = len(q & st)
            if hits:
                scored.append((hits + 0.05 * len(st & q) / max(1, len(q)), -ci, si, ci, chunk))
    scored.sort(reverse=True)
    picked: dict[int, list[tuple[int, str]]] = {}
    used = 0
    for _, _, si, ci, chunk in scored:
        if used + len(chunk) > budget:
            continue
        picked.setdefault(si, []).append((ci, chunk))
        used += len(chunk)
    for si, src in enumerate(sources):
        parts = [c for _, c in sorted(picked.get(si, []))]
        src.text = " … ".join(parts)


def relevance(sources: list[Source], query: str) -> float:
    """Sorgu kelimelerinin sonuçlarda geçme oranı (0–1). Düşükse sorgu değiştirilip yeniden aranır."""
    q = _stems(query)
    if not q:
        return 1.0
    corpus = _stems(" ".join(f"{s.title} {s.snippet} {s.text}" for s in sources))
    return len(q & corpus) / len(q)


_TIME = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b(?![.,]\d)")  # 19:00 / 19.00 / 20.45 (45.000 değil)
_SCORE = re.compile(r"\b(\d{1,2})\s*[-–:]\s*(\d{1,2})\b")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _digits(x: str) -> str:
    return re.sub(r"\D", "", x)


def unsupported_numbers(answer: str, sources: list[Source]) -> list[str]:
    """Cevapta geçip kaynaklarda geçmeyen skorlar ve sayılar (model uydurmuş olabilir).

    Skorlar ("2-1") bütün olarak, tek haneli olmayan sayılar (yıl, fiyat, sıcaklık) rakamlarıyla aranır.
    Tek haneli sayılar kaynaklarda zaten hep bulunacağından kontrol edilmez."""
    corpus = " ".join(f"{s.title} {s.snippet} {s.text} {s.date}" for s in sources)
    # Saatler ayrı karşılaştırılır: kaynakta "19:00", cevapta "19.00" ya da "saat 19" aynı saattir
    times = {(int(h), int(m)) for h, m in _TIME.findall(corpus)}
    bad = []
    for h, m in _TIME.findall(answer):
        if (int(h), int(m)) not in times:
            bad.append(f"{h}:{m}")
    answer = _TIME.sub(" ", answer)
    corpus = _TIME.sub(" ", corpus)
    scores = {f"{a}-{b}" for a, b in _SCORE.findall(corpus)}
    corpus_digits = {_digits(n) for n in _NUMBER.findall(corpus)} | {str(h) for h, _ in times}
    for a, b in _SCORE.findall(answer):
        if f"{a}-{b}" not in scores:
            bad.append(f"{a}-{b}")
    rest = _SCORE.sub(" ", answer)
    for n in _NUMBER.findall(rest):
        d = _digits(n)
        short = d[:-3] if d.endswith("000") and len(d) > 3 else d  # "45.000" ↔ kaynakta "45 bin"
        # Tam eşleşme: alt dize araması "99"u "1999" içinde bulup uydurmayı kaçırıyordu
        if len(d) >= 2 and d not in corpus_digits and short not in corpus_digits:
            bad.append(n)
    return bad


def as_prompt(sources: list[Source], max_chars: int = 3600) -> str:
    """Modele verilecek kaynak bloğu (numaralı, sınırlı uzunlukta)."""
    parts, used = [], 0
    for i, s in enumerate(sources, 1):
        body = (s.text or s.snippet).strip().replace("\n", " ")
        block = f"[{i}] {s.title} ({s.site}{', ' + s.date if s.date else ''})\n{body}"
        if used + len(block) > max_chars:
            block = block[:max(0, max_chars - used)]
        if not block:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)
