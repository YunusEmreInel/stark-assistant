"""İnternet araçlarının çevrimdışı testleri (ağ isteği yok)."""
import pytest

from stark.tools import currency, router, weather, web


@pytest.mark.parametrize("text, kind", [
    ("Bugün hava nasıl?", "weather"),
    ("Yarın Ankara'da yağmur yağacak mı?", "weather"),
    ("Dolar kaç lira?", "currency"),
    ("Euro ne kadar?", "currency"),
    ("Altın fiyatı ne kadar?", "search"),
    ("Son dakika haberler neler?", "news"),
    ("Türkiye'nin gündeminde neler var?", "news"),
    ("Fenerbahçe maçı kaç kaç bitti?", "news"),
    ("Python 3.14 sürümünde neler yeni?", "search"),
    ("iPhone 18 ne zaman çıkacak?", "search"),
    ("Dünyanın en yüksek dağı hangisi?", None),
    ("İnternette ara: Python 3.14 yenilikleri", "search"),
    ("Kuantum bilgisayarlar diye internette araştır", "search"),
    ("Search the web for Rust release date", "search"),
    ("Fotosentez nedir?", None),
    ("Bana bir fıkra anlat.", None),
])
def test_route_kinds(text, kind):
    r = router.route(text, "İstanbul")
    assert (r.kind if r else None) == kind


def test_keywords():
    assert router.keywords("Türkiye'nin gündeminde bugün neler var?") == "Türkiye gündeminde bugün"
    assert router.keywords("Fenerbahçe'nin son maçı kaç kaç bitti?") == "Fenerbahçe son maçı"


@pytest.mark.parametrize("text, fact", [
    ("Güneş sisteminde kaç gezegen var?", True), ("Türkiye'nin coğrafi bölgelerini anlatır mısın?", True),
    ("Türkiye'nin en yüksek dağı hangisi?", True), ("Telefonu kim icat etti?", True),
    ("İstanbul ne zaman fethedildi?", True), ("How many planets are there?", True),
    ("Fotosentez nedir?", False), ("Bana bir fıkra anlat.", False), ("Saat kaç?", False),
    ("Canım sıkılıyor.", False), ("Python'da liste nasıl ters çevrilir?", False),
])
def test_fact_questions(text, fact):
    assert bool(router.FACT.search(text)) is fact


def test_news_keywords_keep_only_names():
    assert router.route("Fenerbahçe'nin son maçı kaç kaç bitti?").query == "Fenerbahçe"
    assert router.route("Galatasaray dün kazandı mı?").query == "Galatasaray"
    assert router.route("Türkiye'nin gündeminde bugün neler var?").query == "Türkiye gündeminde bugün"
    assert router.route("Son dakika haberler neler?").query == "Son dakika haberler"


@pytest.mark.parametrize("text", ["İnternetten araştır.", "İnternette ara", "internetten araştır bunu"])
def test_bare_search_command_has_empty_query(text):
    r = router.route(text)
    assert r.kind == "search" and r.query == ""


def test_route_explicit_query_extracted():
    assert router.route("İnternette ara: Python 3.14 yenilikleri").query == "Python 3.14 yenilikleri"
    assert router.route("Kuantum bilgisayarlar diye internette araştır").query == "Kuantum bilgisayarlar"


@pytest.mark.parametrize("text, city, day", [
    ("İstanbul'da hava nasıl?", "İstanbul", 0),
    ("yarın izmirde hava nasıl olacak", "İzmir", 1),
    ("Ankara için hava durumu", "Ankara", 0),
    ("Londra'da hava nasıl?", "Londra", 0),
    ("Yarından sonra Van'da kar yağacak mı?", "Van", 2),
    ("vanilyalı dondurma havası", None, 0),
])
def test_weather_city_and_day(text, city, day):
    assert weather.find_city(text) == city
    assert weather.find_day(text) == day


def test_weather_uses_default_city_when_missing():
    assert router.route("Hava nasıl?", "Bursa").city == "Bursa"
    assert router.route("Hava nasıl?", "").city is None


@pytest.mark.parametrize("name, loc", [("İstanbul", "İstanbul'da"), ("İzmir", "İzmir'de"), ("Muş", "Muş'ta"),
                                       ("Erzincan", "Erzincan'da"), ("Sinop", "Sinop'ta"), ("Ordu", "Ordu'da")])
def test_locative(name, loc):
    assert weather.locative(name) == loc


def test_weather_describe_turkish():
    data = {"current": {"temperature_2m": 18.4, "apparent_temperature": 16.6, "weather_code": 2},
            "daily": {"weather_code": [61, 0, 3], "temperature_2m_max": [20.2, 22, 19],
                      "temperature_2m_min": [13.6, 14, 12], "precipitation_probability_max": [70, 0, 10]}}
    assert weather.describe("İzmir", data, 0, "tr") == (
        "İzmir'de şu an 18 derece, hava parçalı bulutlu, hissedilen 17 derece. Bugün hava hafif yağmurlu; "
        "en yüksek 20, en düşük 14 derece, yağış ihtimali yüzde 70. Kaynak: Open-Meteo.")
    assert weather.describe("İzmir", data, 1, "tr").startswith("Yarın İzmir'de hava açık; en yüksek 22")


@pytest.mark.parametrize("text, pair", [
    ("Dolar kaç lira?", ("USD", "TRY")),
    ("Euro ne kadar?", ("EUR", "TRY")),
    ("Euro kaç dolar?", ("EUR", "USD")),
    ("Kaç TL bir sterlin?", ("GBP", "TRY")),
    ("Lira ne durumda?", None),
])
def test_currency_pair(text, pair):
    assert currency.find_pair(text) == pair


def test_currency_describe():
    assert currency.describe("USD", "TRY", 41.2345, "2026-10-15", "tr") == (
        "1 dolar 41,23 Türk lirası ediyor. Bu, Avrupa Merkez Bankası'nın 15.10.2026 tarihli referans kuru; "
        "piyasadaki kur biraz farklı olabilir.")


def test_unsupported_numbers_catches_invented_score_and_date():
    srcs = [web.Source("Fenerbahçe Haberleri", "https://x.com", "Fenerbahçe maç ve derbi hazırlıkları, fikstür",
                       date="2026-10-02")]
    bad = web.unsupported_numbers("Son maç 2-1 bitti, 10 Haziran 2026'da oynandı, 52 bin kişi izledi.", srcs)
    assert "2-1" in bad and "52" in bad
    assert "2026" not in bad  # kaynak tarihinde geçiyor


def test_supported_numbers_pass():
    srcs = [web.Source("Fenerbahçe 3-0 kazandı", "https://x.com", "Kadıköy'de 45 bin seyirci önünde",
                       date="2026-10-12")]
    assert web.unsupported_numbers("Fenerbahçe 3-0 kazandı, 45.000 seyirci vardı.", srcs) == []
    assert web.unsupported_numbers("Maç 12 Ekim'de oynandı.", srcs) == []


def test_sources_prompt_is_bounded_and_numbered():
    srcs = [web.Source(f"Başlık {i}", f"https://www.site{i}.com/a", "özet", text="x" * 2000) for i in range(5)]
    p = web.as_prompt(srcs, max_chars=3000)
    assert p.startswith("[1] Başlık 0 (site0.com)") and len(p) <= 3000 + 10
    assert "[3]" not in p or len(p) <= 3010
