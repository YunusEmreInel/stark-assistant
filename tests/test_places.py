import pytest

from stark.tools import places


@pytest.mark.parametrize("text, expected", [
    ("Dün bornovada bir olay oldu.", "Dün Bornova'da bir olay oldu."),
    ("Dün İzmir Bor'novada bir olay oldu.", "Dün İzmir Bornova'da bir olay oldu."),
    ("Bu bornovada bir olay oldu. Bulur musun?", "Bu Bornova'da bir olay oldu. Bulur musun?"),
    ("Çeşme'ye gidiyorum", "Çeşme'ye gidiyorum"),
    ("torbalı yolunda kaza", "Torbalı yolunda kaza"),
    ("Efe Berberoğlu açıklama yaptı", "Efe Berberoğlu açıklama yaptı"),   # kişi adı: dokunulmaz
    ("En büyük ilçe Bornova'dır.", "En büyük ilçe Bornova'dır."),           # bilinmeyen ek: dokunulmaz
    ("Çok güzel bir gün", "Çok güzel bir gün"),
])
def test_normalize_aydin(text, expected):
    assert places.normalize(text, "İzmir") == expected


def test_other_city_untouched():
    assert places.normalize("bornovada", "İstanbul") == "bornovada"


@pytest.mark.parametrize("text, local", [
    ("Bornova'da dün ne oldu?", True), ("İzmir'de nöbetçi eczane hangisi?", True),
    ("Yakınlarda açık bir eczane var mı?", True), ("Çeşme'ye nasıl giderim?", True),
    ("Türkiye'nin coğrafi bölgeleri nelerdir?", False), ("Fotosentez nedir?", False),
])
def test_is_local(text, local):
    assert places.is_local(text, "İzmir") is local


def test_location_context_only_for_local_questions():
    from stark.ai.conversation import Conversation
    from stark.config import Settings
    s = Settings(city="İzmir")
    assert "Bornova" not in Conversation(s).build("Türkiye'nin coğrafi bölgeleri nelerdir?", "tr")[0]["content"]
    assert "Bornova" in Conversation(s).build("İzmir'de bugün ne var?", "tr")[0]["content"]


def test_context_and_hint():
    assert "Bornova" in places.context("İzmir") and "Bornova" in places.whisper_hint("İzmir")
    assert places.context("") == ""
