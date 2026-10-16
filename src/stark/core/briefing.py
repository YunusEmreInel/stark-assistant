"""Günaydın özeti: tarih, hava, hafızadaki bugünkü/yarınki planlar, notlar ve kısa gündem.

Tamamı kodla derlenir (rakam ve plan uydurulamaz). İnternet kapalıysa hava ve gündem atlanır.
"""
import re
from datetime import date, datetime, timedelta

from ..ai.text_for_speech import _MONTHS
from ..memory.database import PERSONAL, Repository, tr_lower

TRIGGER = re.compile(r"^\W*(?:günaydın|günün\s+özeti|bugün\s+(?:neler\s+var|ne\s+var|programım\s+ne)|"
                     r"good\s+morning|daily\s+brief(?:ing)?)\b", re.I)
DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
STAMP = re.compile(r"\(söylendiği gün: (\d{2})\.(\d{2})\.(\d{4})\)")
DMY = re.compile(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{4}))?\b")
DAY_MONTH = re.compile(r"\b(\d{1,2})\s+(" + "|".join(m.lower() for m in _MONTHS["tr"]) + r")\b")


def is_trigger(text: str) -> bool:
    return bool(TRIGGER.match(text.strip()))


def plan_date(content: str) -> date | None:
    """Hafıza kaydının ait olduğu gün: "yarın ... (söylendiği gün: 15.10.2026)" → 16.10.2026,
    ya da metindeki "17 Ekim" / "17.10" tarihleri."""
    low = tr_lower(content)
    stamp = STAMP.search(content)
    if stamp:
        said = date(int(stamp.group(3)), int(stamp.group(2)), int(stamp.group(1)))
        if re.search(r"\byarından\s+sonra\b", low):
            return said + timedelta(days=2)
        if re.search(r"\byarın", low):
            return said + timedelta(days=1)
        if re.search(r"\bbugün", low):
            return said
    body = STAMP.sub("", content)
    today = date.today()
    m = DAY_MONTH.search(tr_lower(body))
    if m:
        month = [x.lower() for x in _MONTHS["tr"]].index(m.group(2)) + 1
        try:
            return date(today.year, month, int(m.group(1)))
        except ValueError:
            return None
    m = DMY.search(body)
    if m and 1 <= int(m.group(2)) <= 12:
        try:
            return date(int(m.group(3) or today.year), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _as_plan(content: str) -> str:
    """Kaydı söylenebilir hale getirir: tarih damgasını ve "yarın/bugün" kelimesini atar."""
    text = STAMP.sub("", content).strip()
    text = re.sub(r"\b(?:yarından\s+sonra|yarın|bugün)\b\s*", "", text, flags=re.I).strip(" ,.")
    return text[:1].upper() + text[1:] if text else content


def plans(repo: Repository, today: date | None = None) -> tuple[list[str], list[str]]:
    today = today or date.today()
    todays, tomorrows = [], []
    for _, content, _ in repo.list_memories(PERSONAL):
        d = plan_date(content)
        if d == today:
            todays.append(_as_plan(content))
        elif d == today + timedelta(days=1):
            tomorrows.append(_as_plan(content))
    return todays, tomorrows


def compose(repo: Repository, address: str, weather_text: str | None, headlines: list[str],
            now: datetime | None = None) -> str:
    now = now or datetime.now()
    greet = "Günaydın" if now.hour < 12 else "İyi günler" if now.hour < 18 else "İyi akşamlar"
    parts = [f"{greet} {address}. Bugün {now.day} {_MONTHS['tr'][now.month - 1]} {DAYS_TR[now.weekday()]}."]
    if weather_text:
        parts.append(weather_text.replace(" Kaynak: Open-Meteo.", "").strip())
    todays, tomorrows = plans(repo, now.date())
    if todays:
        parts.append("Bugün için hafızamdakiler: " + "; ".join(todays) + ".")
    if tomorrows:
        parts.append("Yarın için: " + "; ".join(tomorrows) + ".")
    notes = repo.list_notes()
    if notes:
        parts.append(f"{len(notes)} notunuz var; sonuncusu: {notes[-1][1].rstrip('.')}.")
    if headlines:
        parts.append("Gündemden başlıklar: " + "; ".join(h.rstrip(".") for h in headlines[:3]) + ".")
    return " ".join(parts)
