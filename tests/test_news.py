from datetime import datetime, timedelta

from stark.tools import news, web

GOOGLE_RSS = """<?xml version="1.0"?><rss><channel>
<item><title>İzmir Bornova'da tüp parlaması yangına neden oldu - Son Dakika</title>
<link>https://news.google.com/rss/articles/abc</link><pubDate>{d1}</pubDate>
<description>&lt;a href="x"&gt;İzmir Bornova'da tüp parlaması yangına neden oldu&lt;/a&gt;</description>
<source url="https://www.sondakika.com">Son Dakika</source></item>
<item><title>Eski haber - Hürriyet</title><link>https://news.google.com/rss/articles/def</link>
<pubDate>{d2}</pubDate><source url="https://hurriyet.com.tr">Hürriyet</source></item>
</channel></rss>"""


def _rfc(dt):
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def test_parse_google_feed_strips_publisher_and_dates():
    now = datetime.utcnow()
    xml = GOOGLE_RSS.format(d1=_rfc(now - timedelta(hours=3)), d2=_rfc(now - timedelta(days=20)))
    items = news._parse_feed(xml.encode())
    src, when = items[0]
    assert src.title == "İzmir Bornova'da tüp parlaması yangına neden oldu"
    assert src.site == "Son Dakika" and src.snippet == ""  # açıklama başlığı tekrarlıyordu
    assert src.date == when.date().isoformat()


def test_merge_dedupes_and_sorts_newest_first():
    a = web.Source("Bornova'da tüp parlaması", "u1", "")
    b = web.Source("Bornova’da tüp parlaması!", "u2", "")      # aynı haber, farklı noktalama
    c = web.Source("Başka haber", "u3", "")
    now = datetime.now().astimezone()
    merged = news._merge([(c, now - timedelta(hours=5)), (a, now - timedelta(hours=1)), (b, now)], 10)
    assert [s.url for s in merged] == ["u2", "u3"]


def test_spam_and_routine_pages_filtered():
    now = datetime.now().astimezone()
    items = [(web.Source("$$#→【TRT1-CANLI+!】 Partizan Fenerbahçe maçı izle", "u1", ""), now),
             (web.Source("Son dakika deprem mi oldu? Az önce deprem nerede oldu?", "u2", ""), now),
             (web.Source("Bakan Kurum: Hasar tespit çalışması başladı", "u3", ""), now)]
    assert [s.url for s in news._merge(items, 10, drop_routine=True)] == ["u3"]
    assert [s.url for s in news._merge(items, 10)] == ["u2", "u3"]


def test_exact_number_match():
    srcs = [web.Source("İBB davası, savunmanın 2. günü", "u", "1999 yılında kurulan", date="2026-10-16")]
    assert web.unsupported_numbers("Davanın 99. duruşması sürdü.", srcs) == ["99"]


def test_select_passages_finds_answer_in_middle_of_page():
    menu = "\n".join(f"Menü bağlantısı {i} anasayfa spor ekonomi" for i in range(40))
    answer = "Fenerbahçe, Aston Villa deplasmanında 6-0 mağlup oldu ve gruptaki ilk yenilgisini aldı."
    src = web.Source("Maç sonucu", "https://x.com/a", "", full=f"{menu}\n{answer}\n{menu}")
    web.select_passages([src], "Fenerbahçe son maçı kaç kaç bitti Aston Villa", budget=600)
    assert "6-0" in src.text


def test_relevance():
    srcs = [web.Source("Python 3.14 yenilikleri", "u", "t-string ve zstd desteği")]
    assert web.relevance(srcs, "Python 3.14 yenilikleri") == 1.0
    assert web.relevance(srcs, "Bornova tüp patlaması") == 0.0
