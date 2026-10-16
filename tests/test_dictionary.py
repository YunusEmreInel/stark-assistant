import sqlite3

import pytest

from stark.tools import dictionary
from stark.tools.dictionary import DictQuery, parse


@pytest.mark.parametrize("text, query", [
    ("According kelimesinin Türkçesini bul.", DictQuery("according")),
    ("according kelimesinin türkçesi ne?", DictQuery("according")),
    ("Run'ın Türkçesi ne?", DictQuery("run")),
    ("Achieve Türkçe ne demek?", DictQuery("achieve")),
    ("İngilizce thoroughly ne demek?", DictQuery("thoroughly")),
    ("Serendipity ne demek?", DictQuery("serendipity", explicit=False)),
    ("Take off ne demek?", DictQuery("take off", explicit=False)),
    ("What does eventually mean?", DictQuery("eventually")),
    ("Kitap kelimesinin İngilizcesi ne?", DictQuery("kitap", True, True)),
    ("Kitabın İngilizcesi nedir?", DictQuery("kitab", True, True)),
])
def test_parse(text, query):
    assert parse(text) == query


@pytest.mark.parametrize("text", ["Fotosentez nasıl olur?", "Bunu özetle", "Bu ne demek?", "Hava nasıl?",
                                  "Neleri hatırlıyorsun?"])
def test_not_dictionary(text):
    assert parse(text) is None


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "sozluk.db"
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE senses(word TEXT, pos TEXT, source TEXT, gloss TEXT, turkish TEXT, example TEXT, ord INT);
        CREATE TABLE forms(form TEXT, base TEXT);
        CREATE TABLE turkish(word TEXT PRIMARY KEY);
        INSERT INTO senses VALUES
          ('according','adv','tr','','(according to) ... de belirtildiği üzere, -e göre','',0),
          ('according','adv','tr','','bir şeyle orantılı veya alakalı olarak, -e göre','',1),
          ('according','adj','en','agreeing','uygun, uyumlu','',0),
          ('go','verb','tr','','gitmek','I go to school.',0),
          ('go','verb','en','to move','gitmek, yürümek','',0),
          ('book','noun','en','printed work','kitap','',0),
          ('set','noun','tr','','küme','',0);
        INSERT INTO forms VALUES ('went','go');
        INSERT INTO turkish VALUES ('set'), ('kitap');
    """)
    c.commit()
    c.close()
    monkeypatch.setattr(dictionary, "DB_PATH", path)
    dictionary._db.cache_clear()
    dictionary._vocabulary.cache_clear()
    yield
    dictionary._db().close()
    dictionary._db.cache_clear()
    dictionary._vocabulary.cache_clear()


def test_according_is_answered_from_data(db):
    e = dictionary.lookup("according")
    text = dictionary.spoken(e)
    assert "“according to” kalıbında: de belirtildiği üzere, e göre" in text
    assert "Zarf olarak" in text and "Sıfat olarak: uygun, uyumlu" in text
    assert "göre göre" not in text
    assert "Vikisözlük" in dictionary.detail(e)


def test_inflected_form_points_to_base(db):
    e = dictionary.lookup("went")
    assert e.word == "go" and "“went”, “go” sözcüğünün çekimli biçimi" in dictionary.spoken(e)
    assert "Örnek: I go to school." in dictionary.detail(e)


def test_misheard_word_is_matched(db):
    e = dictionary.lookup("acording")
    assert e.word == "according" and "“according” olarak anladım" in dictionary.spoken(e)


def test_turkish_to_english_and_turkish_words(db):
    assert dictionary.to_english("kitap") == dictionary.to_english("kitab") == [("book", "noun")]
    assert dictionary.is_turkish_word("set") and not dictionary.is_turkish_word("according")
    assert dictionary.lookup("qwertyuiop") is None
