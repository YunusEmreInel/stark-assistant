"""Döviz: Frankfurter (Avrupa Merkez Bankası referans kurları, ücretsiz, anahtarsız). Cevap kodla üretilir."""
import re
from datetime import date

import httpx

from ..memory.database import tr_lower

URL = "https://api.frankfurter.dev/v1/latest"
NAMES = [  # (eşleşme, kod, Türkçe ad, İngilizce ad)
    (r"dolar|dollar|usd", "USD", "dolar", "dollar"),
    (r"euro|avro|eur\b", "EUR", "euro", "euro"),
    (r"sterlin|pound|gbp", "GBP", "sterlin", "pound"),
    (r"isviçre frangı|frank|chf", "CHF", "İsviçre frangı", "Swiss franc"),
    (r"\byen\b|jpy", "JPY", "yen", "yen"),
    (r"ruble|rub\b", "RUB", "ruble", "ruble"),
    (r"türk lira|\blira|\btl\b|try", "TRY", "Türk lirası", "Turkish lira"),
]


class CurrencyError(Exception):
    pass


def find_pair(text: str) -> tuple[str, str] | None:
    """Metinde geçen para birimleri: ilk bulunan baz, ikincisi hedef (yoksa TRY)."""
    low = tr_lower(text)
    found = sorted((m.start(), code) for rx, code, _, _ in NAMES for m in [re.search(rx, low)] if m)
    codes = list(dict.fromkeys(code for _, code in found))
    if not codes or codes == ["TRY"]:
        return None
    base = codes[0] if codes[0] != "TRY" else codes[1]
    target = next((c for c in codes if c != base), "TRY")
    return base, target


def _name(code: str, language: str) -> str:
    for _, c, tr, en in NAMES:
        if c == code:
            return en if language == "en" else tr
    return code


def quote(base: str, target: str, language: str, client: httpx.Client | None = None) -> str:
    c = client or httpx.Client(timeout=8, follow_redirects=True)
    try:
        data = c.get(URL, params={"base": base, "symbols": target}).json()
        rate = data["rates"][target]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise CurrencyError(str(e)) from e
    finally:
        if client is None:
            c.close()
    return describe(base, target, rate, data.get("date", ""), language)


def describe(base: str, target: str, rate: float, day: str, language: str) -> str:
    try:
        d = date.fromisoformat(day)
        day_tr = f"{d.day}.{d.month:02d}.{d.year}"
    except ValueError:
        day_tr = day
    if language == "en":
        return (f"One {_name(base, 'en')} is {rate:.2f} {_name(target, 'en')}s. This is the European Central Bank "
                f"reference rate for {day}; market rates may differ slightly.")
    value = f"{rate:.2f}".replace(".", ",")
    return (f"1 {_name(base, 'tr')} {value} {_name(target, 'tr')} ediyor. Bu, Avrupa Merkez Bankası'nın "
            f"{day_tr} tarihli referans kuru; piyasadaki kur biraz farklı olabilir.")
