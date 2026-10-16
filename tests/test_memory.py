import sqlite3

import pytest

from stark.ai.conversation import Conversation
from stark.config import Settings
from stark.memory import actions
from stark.memory.commands import MemoryCommand, parse
from stark.memory.database import Repository


@pytest.fixture
def repo(tmp_path):
    r = Repository(tmp_path / "stark.db")
    yield r
    r.close()


# ---- komut tanıma ----
@pytest.mark.parametrize("text, payload", [
    ("Bunu hatırla: doğum günüm 5 Mayıs.", "doğum günüm 5 Mayıs"),
    ("Hatırla, yarın saat 9'da sınavım var.", "yarın saat 9'da sınavım var"),
    ("Unutma, annemin adı Ayşe.", "annemin adı Ayşe"),
    ("En sevdiğim renk mavi, bunu hatırla.", "En sevdiğim renk mavi"),
    ("Kahveyi şekersiz içiyorum, bunu unutma.", "Kahveyi şekersiz içiyorum"),
    ("Remember that my birthday is May 5th.", "my birthday is May 5th"),
])
def test_remember_commands(text, payload):
    assert parse(text) == MemoryCommand("remember", payload)


@pytest.mark.parametrize("text, cmd", [
    ("Unut: doğum günüm.", MemoryCommand("forget", "doğum günüm")),
    ("Doğum günü bilgisini hafızandan sil.", MemoryCommand("forget", "Doğum günü")),
    ("Bunu unut.", MemoryCommand("forget_last")),
    ("Forget my birthday.", MemoryCommand("forget", "my birthday")),
    ("Neleri hatırlıyorsun?", MemoryCommand("list")),
    ("Hakkımda ne biliyorsun?", MemoryCommand("list")),
    ("What do you remember about me?", MemoryCommand("list")),
])
def test_forget_and_list_commands(text, cmd):
    assert parse(text) == cmd


@pytest.mark.parametrize("text, payload", [
    ("Şunu öğren: Bornova, İzmir'in bir ilçesidir.", "Bornova, İzmir'in bir ilçesidir"),
    ("Öğren, Gülbahçe Bornova'da bir mahalle.", "Gülbahçe Bornova'da bir mahalle"),
    ("Bil ki Torbalı İzmir'e bağlı bir ilçedir.", "Torbalı İzmir'e bağlı bir ilçedir"),
    ("Hayır, doğrusu şu: Fenerbahçe'nin teknik direktörü İsmail Kartal.",
     "Fenerbahçe'nin teknik direktörü İsmail Kartal"),
    ("Learn that Bornova is a district of İzmir.", "Bornova is a district of İzmir"),
])
def test_learn_commands(text, payload):
    assert parse(text) == MemoryCommand("learn", payload)


@pytest.mark.parametrize("text", ["Bilgisayarım bozuldu.", "Öğrenci belgesi nasıl alınır?",
                                  "Ne öğrenmeliyim?", "Bunu biliyor musun?"])
def test_learn_non_commands(text):
    cmd = parse(text)
    assert cmd is None or cmd.action != "learn"


def test_learned_facts_go_to_prompt_and_asr_hints(repo):
    from stark.memory.database import KNOWLEDGE
    from stark.tools import places
    repo.add_memory("Gülbahçe, Bornova'da bir mahalledir", KNOWLEDGE)
    repo.add_memory("En sevdiğim renk mavi")
    assert "Gülbahçe" in repo.learned_names()
    assert "Gülbahçe" in places.whisper_hint("İzmir", repo.learned_names())
    assert places.normalize("gülbahçede yangın", "İzmir", repo.learned_names()) == "Gülbahçe'de yangın"
    system = Conversation(Settings(), repo).build("Gülbahçe nerede?", "tr")[0]["content"]
    assert "Facts the user taught you" in system and "Gülbahçe, Bornova'da" in system
    reply, _ = actions.apply(MemoryCommand("list_learned"), repo, "tr")
    assert "Gülbahçe" in reply and "mavi" not in reply


def test_old_database_gets_kind_column(tmp_path):
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, content TEXT NOT NULL, created_at TEXT NOT NULL)")
    con.execute("INSERT INTO memories (content, created_at) VALUES ('Eski kayıt', '2026-10-15T10:00:00')")
    con.commit()
    con.close()
    r = Repository(db)
    assert r.kinds() == {1: "personal"} and r.list_memories()[0][1] == "Eski kayıt"
    r.close()


@pytest.mark.parametrize("text, cmd", [
    ("Not al: Cuma günü kitap iade et.", MemoryCommand("note", "Cuma günü kitap iade et")),
    ("Şunu not et, yarın 10'da toplantı var", MemoryCommand("note", "yarın 10'da toplantı var")),
    ("Süt ve ekmek al, bunu not al.", MemoryCommand("note", "Süt ve ekmek al")),
    ("Notlarımı oku.", MemoryCommand("note_list")),
    ("Notlarımda ne var?", MemoryCommand("note_list")),
    ("Son notu sil.", MemoryCommand("note_delete_last")),
    ("Notlarımı masaüstüne aktar.", MemoryCommand("note_export")),
])
def test_note_commands(text, cmd):
    assert parse(text) == cmd


def test_note_actions(repo, tmp_path, monkeypatch):
    from stark.tools import desktop
    monkeypatch.setattr(desktop, "_known_folder", lambda csidl: tmp_path)
    reply, _ = actions.apply(MemoryCommand("note", "Süt al"), repo, "tr")
    actions.apply(MemoryCommand("note", "Kitap iade et"), repo, "tr")
    assert "Not aldım" in reply and len(repo.list_notes()) == 2 and repo.list_memories() == []  # hafızaya karışmaz
    assert "Kitap iade et" in actions.apply(MemoryCommand("note_list"), repo, "tr")[0]
    actions.apply(MemoryCommand("note_export"), repo, "tr")
    assert "Süt al" in (tmp_path / "Stark notları.txt").read_text(encoding="utf-8")
    reply, _ = actions.apply(MemoryCommand("note_delete_last"), repo, "tr")
    assert "Kitap iade et" in reply and [c for _, c, _ in repo.list_notes()] == ["Süt al"]


@pytest.mark.parametrize("text", [
    "Fotosentez nedir?",
    "Bunu hatırlıyor musun?",          # soru, komut değil
    "Hatırla, dün ne yaptık?",         # soru içerikli: kaydedilmez
    "Hatırla.",                         # içerik yok
    "Unutmak neden olur?",
    "Remember when we talked?",
])
def test_non_commands(text):
    assert parse(text) is None


@pytest.mark.parametrize("text", [
    "Annemin adını biliyor musun?", "Doğum günüm ne zaman?", "Kardeşimin adı neydi?",
    "En sevdiğim renk ne?", "Kaç yaşındayım?", "Nereliyim?", "What is my mother's name?", "When is my birthday?",
])
def test_personal_questions(text):
    from stark.memory.commands import is_personal_question
    assert is_personal_question(text)


@pytest.mark.parametrize("text", [
    "Atatürk kaç yaşında öldü?", "Doğum günü nasıl kutlanır?", "Senin favori filmin ne?",
    "Fotosentez nedir?", "Telefon nasıl çalışır?", "Annem için hediye önerir misin",
    "Benimle konuşmaya hazır mısın?",
])
def test_not_personal_questions(text):
    from stark.memory.commands import is_personal_question
    assert not is_personal_question(text)


# ---- veritabanı ----
def test_memory_add_list_delete_is_real_delete(repo, tmp_path):
    a = repo.add_memory("En sevdiğim renk mavi")
    repo.add_memory("Doğum günüm 5 Mayıs")
    assert [c for _, c, _ in repo.list_memories()] == ["En sevdiğim renk mavi", "Doğum günüm 5 Mayıs"]
    repo.delete_memory(a)
    assert [c for _, c, _ in repo.list_memories()] == ["Doğum günüm 5 Mayıs"]
    repo.delete_all_memories()
    assert repo.list_memories() == []
    # silinen metin dosyada başka tabloda/özette kalmamalı
    raw = sqlite3.connect(tmp_path / "stark.db").execute(
        "SELECT group_concat(content) FROM memories").fetchone()[0]
    assert raw is None


def test_find_memory_handles_turkish_suffixes(repo):
    repo.add_memory("Doğum günüm 5 Mayıs")
    repo.add_memory("Kardeşimin adı Elif")
    assert repo.find_memory("doğum günü")[1] == "Doğum günüm 5 Mayıs"
    assert repo.find_memory("KARDEŞİM")[1] == "Kardeşimin adı Elif"
    assert repo.find_memory("araba") is None


def test_conversations_persist_and_delete(repo):
    s = Settings()
    c = Conversation(s, repo)
    c.record("Merhaba", "Merhaba, nasıl yardımcı olabilirim?")
    c.record("Fotosentez nedir?", "Bitkilerin besin üretmesidir.")
    c.reset()
    c.record("Yeni sohbet", "Tamam.")
    convs = repo.list_conversations()
    assert [t for _, _, t, _ in convs] == ["Yeni sohbet", "Merhaba"]
    first = convs[1][0]
    assert [r for r, _, _ in repo.messages(first)] == ["user", "assistant", "user", "assistant"]
    repo.delete_conversation(first)
    assert len(repo.list_conversations()) == 1 and repo.messages(first) == []


def test_history_limit_and_memory_in_prompt(repo):
    s = Settings(history_turns=3)
    repo.add_memory("En sevdiğim renk mavi")
    c = Conversation(s, repo)
    for i in range(6):
        c.record(f"soru {i}", f"cevap {i}")
    msgs = c.build("son soru", "tr")
    users = [m["content"] for m in msgs if m["role"] == "user"]
    assert users == ["User: soru 3", "User: soru 4", "User: soru 5", "User: son soru"]
    assert "En sevdiğim renk mavi" not in msgs[0]["content"]  # ilgisiz kayıt modele gitmez
    assert "En sevdiğim renk mavi" in c.build("En sevdiğim renk neydi?", "tr")[0]["content"]


def test_relevant_memories_only_matching(repo):
    repo.add_memory("Kardeşimin adı Elif")
    repo.add_memory("En sevdiğim renk mavi")
    assert repo.relevant_memories("Kardeşimin adını hatırlıyor musun?") == ["Kardeşimin adı Elif"]
    assert repo.relevant_memories("Annemin adını biliyor musun?") == []
    assert repo.relevant_memories("Fotosentez nedir?") == []


# ---- komut uygulama ----
def test_apply_remember_and_forget(repo):
    reply, last = actions.apply(MemoryCommand("remember", "Doğum günüm 5 Mayıs"), repo, "tr")
    assert "kaydettim" in reply and last[1] == "Doğum günüm 5 Mayıs"
    reply, last = actions.apply(MemoryCommand("list"), repo, "tr", last)
    assert "Doğum günüm 5 Mayıs" in reply
    reply, last = actions.apply(MemoryCommand("forget", "doğum günüm"), repo, "tr", last)
    assert "sildim" in reply and repo.list_memories() == [] and last is None


def test_forget_last_only_targets_this_session(repo):
    repo.add_memory("Eski bir bilgi")  # önceki oturumdan
    reply, _ = actions.apply(MemoryCommand("forget_last"), repo, "tr", None)
    assert "Neyi unutmamı" in reply and len(repo.list_memories()) == 1
