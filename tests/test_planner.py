from stark.ai import search_planner
from stark.tools import router


def test_parse_planner_replies():
    assert search_planner.parse("NONE") is None
    assert search_planner.parse("WEB: İzmir Bornova tüp patlaması") == ("search", "İzmir Bornova tüp patlaması")
    assert search_planner.parse("NEWS: Fenerbahçe") == ("news", "Fenerbahçe")
    assert search_planner.parse('  web: "Elon Musk"  ') == ("search", "Elon Musk")
    assert search_planner.parse("Bence arama gerekmez.") is None   # biçim dışı → arama yok
    assert search_planner.parse("WEB:") is None


def test_previous_turns_go_into_planner_prompt():
    msgs = search_planner.build_messages("Evet, ara.", [("Dün Bornova'da tüp patladı mı?", "Bilmiyorum.")],
                                         "2026-10-16")
    assert "Dün Bornova'da tüp patladı mı?" in msgs[1]["content"] and "2026-10-16" in msgs[0]["content"]


def test_canned_intro_and_abilities_follow_settings():
    from stark.core import canned
    assert "Ben Stark" in canned.reply_for("Kendini tanıtır mısın?", "tr", True)
    assert "internetten" in canned.reply_for("Neler yapabilirsin?", "tr", True)
    assert "internetten" not in canned.reply_for("Neler yapabilirsin?", "tr", False)
    assert canned.reply_for("What can you do?", "en", True).startswith("I can talk")
    assert canned.reply_for("Fotosentez nedir?", "tr", True) is None
    assert canned.reply_for("Bu yemeği nasıl yapabilirim?", "tr", True) is None


def test_asked_day():
    from datetime import date

    from stark.core.engine import asked_day
    d = date(2026, 10, 16)
    assert asked_day("Dün Bornova'da ne oldu?", d) == "2026-10-15"
    assert asked_day("Bugünkü maç kaç kaç?", d) == "2026-10-16"
    assert asked_day("Fenerbahçe'nin son maçı?", d) is None


def test_event_queries_go_to_news_with_names_only():
    assert router.NEWS.search("İzmir Bornova ev tüp patlama")
    assert router.news_keywords("İzmir Bornova olay dün") == "İzmir Bornova"
