from datetime import date, datetime

import pytest

from stark.core.engine import past_dates
from stark.tools import fixtures, router, web
from stark.tools.fixtures import TR_TZ, FixtureQuery, parse


@pytest.mark.parametrize("text, query", [
    ("Fenerbahçe'nin yarınki maç saat kaçta?", FixtureQuery("Fenerbahce", "next", 1)),
    ("Galatasaray'ın sonraki maçı ne zaman?", FixtureQuery("Galatasaray", "next")),
    ("GS maçı ne zaman?", FixtureQuery("Galatasaray", "next")),
    ("Beşiktaş bugün maç var mı?", FixtureQuery("Besiktas", "next", 0)),
    ("Fenerbahçe'nin son maçı kaç kaç bitti?", FixtureQuery("Fenerbahce", "result")),
    ("Trabzonspor dün kazandı mı?", FixtureQuery("Trabzonspor", "result", -1)),
])
def test_parse(text, query):
    assert parse(text) == query


@pytest.mark.parametrize("text", ["Fenerbahçe basketbol maçı ne zaman?", "Fenerbahçe başkanı kim?",
                                  "Real Madrid maçı ne zaman?", "Yarın hava nasıl?"])
def test_not_fixture_questions(text):
    assert parse(text) is None


def _event(when, home, away, state="pre", hs=None, as_=None, league="Turkish Super Lig"):
    side = lambda name, ha, sc: {"homeAway": ha, "team": {"displayName": name},  # noqa: E731
                                 **({"score": {"value": float(sc)}} if sc is not None else {})}
    return {"date": when, "league": {"name": league}, "competitions": [{
        "competitors": [side(home, "home", hs), side(away, "away", as_)],
        "status": {"type": {"state": state}, "displayClock": "90'"}}]}


class FakeClient:
    def __init__(self, upcoming, played):
        self.upcoming, self.played = upcoming, played

    def get(self, url, timeout=0):
        events = self.upcoming if "fixture=true" in url else self.played
        return type("R", (), {"json": lambda self_: {"events": events}})()


NOW = datetime(2026, 10, 16, 15, 0, tzinfo=TR_TZ)
CLIENT = FakeClient(
    upcoming=[_event("2026-10-17T16:00Z", "Fenerbahce", "Alanyaspor"),
              _event("2026-10-20T16:45Z", "Fenerbahce", "Slavia Prague", league="UEFA Champions League")],
    played=[_event("2026-10-14T19:00Z", "Aston Villa", "Fenerbahce", "post", 6, 0, "UEFA Champions League")])


def test_next_match_tomorrow_in_turkish_time():
    reply = fixtures.answer(FixtureQuery("Fenerbahce", "next", 1), NOW, CLIENT)
    assert reply == ("Fenerbahçe'nin maçı: Fenerbahçe - Alanyaspor, yarın, 17 Ekim Cumartesi saat 19.00, Süper Lig. "
                     "Fenerbahçe evinde, rakip Alanyaspor.")


def test_no_match_on_asked_day_gives_next_one():
    reply = fixtures.answer(FixtureQuery("Fenerbahce", "next", 0), NOW, CLIENT)
    assert reply.startswith("Bugün Fenerbahçe'nin maçı yok patron. Sıradaki maçı: Fenerbahçe - Alanyaspor")


def test_last_result():
    reply = fixtures.answer(FixtureQuery("Fenerbahce", "result"), NOW, CLIENT)
    assert reply == ("Fenerbahçe'nin son maçı 14 Ekim Çarşamba, Şampiyonlar Ligi: Aston Villa 6, Fenerbahçe 0. "
                     "Fenerbahçe kaybetti.")


def test_genitive_suffixes():
    assert [fixtures.gen(n) for n in ("Fenerbahçe", "Galatasaray", "Trabzonspor", "Göztepe", "Beşiktaş")] == \
        ["Fenerbahçe'nin", "Galatasaray'ın", "Trabzonspor'un", "Göztepe'nin", "Beşiktaş'ın"]


def test_time_written_differently_is_not_rejected():
    src = [web.Source(title="Fenerbahçe-Alanyaspor maçı saat 19:00'da", url="u", snippet="")]
    assert web.unsupported_numbers("Maç 19.00'da başlıyor", src) == []
    assert web.unsupported_numbers("Maç 20.00'da başlıyor", src) == ["20:00"]


def test_past_date_in_upcoming_answer_is_caught():
    today = date(2026, 10, 16)
    assert past_dates("Yarınki maç 14 Ekim 2026 Çarşamba", today) == ["14 Ekim"]
    assert past_dates("Maç 17 Ekim Cumartesi", today) == []


@pytest.mark.parametrize("text, site", [
    ("Maç Kolik sitesine girip bakabilirsin.", "mackolik.com"),
    ("Vikipedi'den bak", "tr.wikipedia.org"),
    ("Sporx sitesine bak", "Sporx"),
    ("Ahmet'e bak", None), ("İnternetten bak", None), ("bu sayfaya bak", None),
])
def test_site_request(text, site):
    assert router.site_request(text) == site


def test_foreign_team_found_from_league_lists(monkeypatch):
    class Teams:
        def get(self, url, timeout=0):
            teams = [{"team": {"displayName": "Manchester City", "shortDisplayName": "Man City", "id": "382"}},
                     {"team": {"displayName": "Manchester United", "shortDisplayName": "Man United", "id": "360"}},
                     {"team": {"displayName": "Real Madrid", "shortDisplayName": "Real Madrid", "id": "86"}},
                     {"team": {"displayName": "Barcelona", "shortDisplayName": "Barcelona", "id": "83"}}]
            return type("R", (), {"json": lambda self_: {"sports": [{"leagues": [{"teams": teams}]}]}})()
    monkeypatch.setattr(fixtures, "_foreign", {})
    monkeypatch.setattr(fixtures, "_foreign_keys", {})
    assert parse("Real Madrid'in yarınki maçı saat kaçta?") is None  # yabancı liste yüklenmeden bulunmaz
    q = parse("Manchester City'nin sonraki maçı ne zaman?", foreign=True, client=Teams())
    assert q == FixtureQuery("Manchester City", "next")
    assert parse("Barselona'nın son maçı kaç kaç bitti?", foreign=True).team == "Barcelona"
    assert fixtures.gen("Manchester City") == "Manchester City'nin"
