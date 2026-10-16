"""Hava durumu: Open-Meteo (ücretsiz, anahtarsız). Cevap kodla üretilir; rakamları model uyduramaz."""
import re

import httpx

from ..memory.database import tr_lower

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

PROVINCES = (
    "Adana Adıyaman Afyonkarahisar Ağrı Aksaray Amasya Ankara Antalya Ardahan Artvin Aydın Balıkesir Bartın Batman "
    "Bayburt Bilecik Bingöl Bitlis Bolu Burdur Bursa Çanakkale Çankırı Çorum Denizli Diyarbakır Düzce Edirne Elazığ "
    "Erzincan Erzurum Eskişehir Gaziantep Giresun Gümüşhane Hakkari Hatay Iğdır Isparta İstanbul İzmir Kahramanmaraş "
    "Karabük Karaman Kars Kastamonu Kayseri Kilis Kırıkkale Kırklareli Kırşehir Kocaeli Konya Kütahya Malatya Manisa "
    "Mardin Mersin Muğla Muş Nevşehir Niğde Ordu Osmaniye Rize Sakarya Samsun Siirt Sinop Sivas Şanlıurfa Şırnak "
    "Tekirdağ Tokat Trabzon Tunceli Uşak Van Yalova Yozgat Zonguldak"
).split()
# Türkçe hal ekleri ("İstanbul'da", "Ankaradaki", "İzmir'e"); "Van" → "vanilya" eşleşmesin diye sınırlı
_CASE = r"(?:['’]?(?:da|de|ta|te|daki|deki|dan|den|tan|ten|a|e|ya|ye|ın|in|un|ün|nın|nin|ı|i|yı|yi))?"

WMO_TR = {0: "açık", 1: "çoğunlukla açık", 2: "parçalı bulutlu", 3: "kapalı", 45: "sisli", 48: "sisli",
          51: "hafif çiseli", 53: "çiseli", 55: "yoğun çiseli", 56: "dondurucu çiseli", 57: "dondurucu çiseli",
          61: "hafif yağmurlu", 63: "yağmurlu", 65: "şiddetli yağmurlu", 66: "dondurucu yağmurlu",
          67: "dondurucu yağmurlu", 71: "hafif karlı", 73: "karlı", 75: "yoğun karlı", 77: "kar taneli",
          80: "hafif sağanak yağışlı", 81: "sağanak yağışlı", 82: "şiddetli sağanak yağışlı", 85: "kar sağanaklı",
          86: "yoğun kar sağanaklı", 95: "gök gürültülü fırtınalı", 96: "dolulu fırtınalı", 99: "dolulu fırtınalı"}
WMO_EN = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "foggy",
          51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
          71: "light snow", 73: "snow", 75: "heavy snow", 80: "light showers", 81: "showers", 82: "heavy showers",
          95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail"}


class WeatherError(Exception):
    pass


def find_city(text: str) -> str | None:
    low = tr_lower(text)
    for p in PROVINCES:
        if re.search(rf"\b{tr_lower(p)}{_CASE}\b", low):
            return p
    # İl listesinde olmayan yerler: "Londra'da hava", "Paris'te"
    m = re.search(r"\b([A-ZÇĞİÖŞÜ][\wçğıöşü]+)['’](?:da|de|ta|te|daki|deki)\b", text)
    if m:
        return m.group(1)
    m = re.search(r"\bin\s+([A-Z][\w-]+)", text)
    return m.group(1) if m else None


def find_day(text: str) -> int:
    low = tr_lower(text)
    if re.search(r"yarından sonra|öbür gün|day after tomorrow", low):
        return 2
    if re.search(r"\byarın|\btomorrow", low):
        return 1
    return 0


def locative(name: str) -> str:
    """Bulunma eki: İstanbul'da, İzmir'de, Muş'ta, Erzincan'da (ünlü uyumu + sert ünsüz)."""
    vowels = [ch for ch in tr_lower(name) if ch in "aeıioöuü"]
    vowel = "a" if vowels and vowels[-1] in "aıou" else "e"
    cons = "t" if tr_lower(name)[-1] in "çfhkpsşt" else "d"
    return f"{name}'{cons}{vowel}"


def _num(x: float) -> str:
    return str(round(x))


def forecast(city: str, day: int, language: str, client: httpx.Client | None = None) -> str:
    c = client or httpx.Client(timeout=8)
    try:
        geo = c.get(GEO_URL, params={"name": city, "count": 1, "language": language, "format": "json"}).json()
        if not geo.get("results"):
            raise WeatherError(f"'{city}' bulunamadı")
        g = geo["results"][0]
        data = c.get(FORECAST_URL, params={
            "latitude": g["latitude"], "longitude": g["longitude"], "timezone": "auto", "forecast_days": 3,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        }).json()
    except httpx.HTTPError as e:
        raise WeatherError(str(e)) from e
    finally:
        if client is None:
            c.close()
    return describe(g["name"], data, day, language)


def describe(name: str, data: dict, day: int, language: str) -> str:
    d = data["daily"]
    wmo = WMO_EN if language == "en" else WMO_TR
    cond = wmo.get(d["weather_code"][day], "")
    hi, lo, rain = _num(d["temperature_2m_max"][day]), _num(d["temperature_2m_min"][day]), \
        d["precipitation_probability_max"][day]
    if language == "en":
        when = ["Today", "Tomorrow", "The day after tomorrow"][day]
        parts = []
        if day == 0:
            cur = data["current"]
            parts.append(f"Right now it's {_num(cur['temperature_2m'])} degrees in {name}, "
                         f"{WMO_EN.get(cur['weather_code'], '')}.")
        parts.append(f"{when}{'' if day == 0 else ' in ' + name} will be {cond}, high {hi}, low {lo}"
                     + (f", {rain} percent chance of rain." if rain is not None else "."))
        return " ".join(parts) + " Source: Open-Meteo."
    when = ["Bugün", "Yarın", "Yarından sonra"][day]
    parts = []
    if day == 0:
        cur = data["current"]
        feels = _num(cur["apparent_temperature"])
        parts.append(f"{locative(name)} şu an {_num(cur['temperature_2m'])} derece, hava "
                     f"{WMO_TR.get(cur['weather_code'], '')}"
                     + (f", hissedilen {feels} derece." if feels != _num(cur["temperature_2m"]) else "."))
    parts.append(f"{when}{'' if day == 0 else ' ' + locative(name)} hava {cond}; en yüksek {hi}, en düşük {lo} derece"
                 + (f", yağış ihtimali yüzde {rain}." if rain is not None else "."))
    return " ".join(parts) + " Kaynak: Open-Meteo."
