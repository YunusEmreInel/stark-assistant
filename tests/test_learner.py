from datetime import datetime, timedelta

import pytest

from stark.ai.conversation import Conversation
from stark.config import Settings
from stark.memory import learner
from stark.memory.database import KNOWLEDGE, PERSONAL, PREFERENCE, Repository


@pytest.fixture
def repo():
    r = Repository(":memory:")
    yield r
    r.close()


def test_parse_lines():
    reply = "personal: Yarın sınavım var\n- preference: Daha kısa cevap ver\nknowledge: Bornova İzmir'de\nfoo"
    assert learner.parse(reply) == [(PERSONAL, "Yarın sınavım var"), (PREFERENCE, "Daha kısa cevap ver"),
                                    (KNOWLEDGE, "Bornova İzmir'de")]
    assert learner.parse("NONE") == []


def test_grounding_rejects_invented_facts():
    said = "Bu dönem bilgisayar mühendisliğinde ikinci sınıftayım, yarın veri yapıları sınavım var."
    assert learner.grounded("Bilgisayar mühendisliğinde ikinci sınıftayım", said)
    assert learner.grounded("Yarın veri yapıları sınavım var", said)
    assert not learner.grounded("İstanbul Teknik Üniversitesi'nde okuyorum", said)   # söylenmedi
    assert not learner.grounded("Annemin adı Ayşe", said)


def test_store_dedupes_and_marks_source(repo):
    said = "Kahveyi şekersiz içerim."
    assert learner.store(repo, [(PERSONAL, "Kahveyi şekersiz içerim")], said) == ["Kahveyi şekersiz içerim"]
    assert learner.store(repo, [(PERSONAL, "Kahveyi şekersiz içerim.")], said) == []   # aynısı var
    assert repo.sources() == {1: "auto"}


def test_clean_and_relative_dates(repo):
    assert learner.clean("Bornova İzmir'in bir ilçesi, sen yanlış söyledin.") == "Bornova İzmir'in bir ilçesi"
    assert learner.clean("hayır, daha kısa cevap ver") == "Daha kısa cevap ver"
    said = "Yarın veri yapıları sınavım var."
    saved = learner.store(repo, [(PERSONAL, "Yarın veri yapıları sınavım var")], said)
    assert saved[0].startswith("Yarın veri yapıları sınavım var (söylendiği gün: ")


def test_trivial_messages_skipped():
    assert not learner.worth_checking("Teşekkürler.")
    assert not learner.worth_checking("Tamam")
    assert learner.worth_checking("Yarın sabah dokuzda toplantım var.")


def test_research_memory_expires(repo):
    assert learner.remember_research(repo, "Fenerbahçe'nin son maçı?", "Aston Villa'ya 6-0 yenildi.", ["DHA"], True)
    assert len(repo.list_memories()) == 1
    # süresi geçmiş kayıt artık listelenmez ve modele gitmez
    repo._exec("UPDATE memories SET expires_at = ?", ((datetime.now() - timedelta(days=1)).isoformat(),))
    assert repo.list_memories() == [] and len(repo.list_memories(include_expired=True)) == 1


def test_preferences_always_in_prompt(repo):
    repo.add_memory("Cevapları en fazla iki cümle tut", PREFERENCE, source="auto")
    system = Conversation(Settings(), repo).build("Fotosentez nedir?", "tr")[0]["content"]
    assert "standing preferences" in system and "iki cümle" in system
