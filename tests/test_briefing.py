from datetime import date, datetime

import pytest

from stark.core import briefing
from stark.memory.database import Repository


@pytest.fixture
def repo():
    r = Repository(":memory:")
    yield r
    r.close()


@pytest.mark.parametrize("text, ok", [
    ("Günaydın.", True), ("Günaydın Stark", True), ("Günün özeti", True), ("Bugün neler var?", True),
    ("Good morning", True), ("Günaydın demek istemiyorum ama", True),
    ("Bugün hava nasıl?", False), ("Sana günaydın dedim mi?", False),
])
def test_trigger(text, ok):
    assert briefing.is_trigger(text) is ok


def test_plan_dates_from_relative_stamps_and_explicit_dates():
    assert briefing.plan_date("Yarın veri yapıları sınavım var (söylendiği gün: 15.10.2026)") == date(2026, 10, 16)
    assert briefing.plan_date("Bugün dişçim var (söylendiği gün: 16.10.2026)") == date(2026, 10, 16)
    assert briefing.plan_date("Yarından sonra toplantı (söylendiği gün: 15.10.2026)") == date(2026, 10, 17)
    assert briefing.plan_date("17 Ekim'de doğum günü partisi") == date(date.today().year, 10, 17)
    assert briefing.plan_date("En sevdiğim renk mavi") is None


def test_compose(repo):
    repo.add_memory("Yarın veri yapıları sınavım var (söylendiği gün: 15.10.2026)")
    repo.add_memory("17 Ekim'de kardeşimin doğum günü")
    repo.add_memory("En sevdiğim renk mavi")
    repo.add_note("Kitabı iade et")
    text = briefing.compose(repo, "patron", "İzmir'de şu an 13 derece. Kaynak: Open-Meteo.", ["Başlık 1", "Başlık 2"],
                            now=datetime(2026, 10, 16, 8, 30))
    assert text.startswith("Günaydın patron. Bugün 16 Ekim Cuma.")
    assert "Bugün için hafızamdakiler: Veri yapıları sınavım var." in text
    assert "Yarın için: 17 Ekim'de kardeşimin doğum günü." in text
    assert "mavi" not in text and "Open-Meteo" not in text
    assert "1 notunuz var; sonuncusu: Kitabı iade et." in text and "Başlık 1; Başlık 2" in text


def test_compose_evening_without_internet(repo):
    text = briefing.compose(repo, "patron", None, [], now=datetime(2026, 10, 16, 20, 0))
    assert text == "İyi akşamlar patron. Bugün 16 Ekim Cuma."
