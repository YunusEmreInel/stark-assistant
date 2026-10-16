import pytest

from stark.core.dismissal import reply_for


@pytest.mark.parametrize("text, reply", [
    ("Teşekkürler.", "Rica ederim patron."),
    ("Teşekkür ederim.", "Rica ederim patron."),
    ("Sağ ol.", "Rica ederim patron."),
    ("Sağol Stark!", "Rica ederim patron."),
    ("Tamam, çok teşekkürler.", "Rica ederim patron."),
    ("Eyvallah.", "Rica ederim patron."),
    ("Şimdilik bu kadar.", "Rica ederim patron."),
    ("Tamam bu kadar, teşekkürler.", "Rica ederim patron."),
    ("İyi geceler.", "İyi geceler patron."),
    ("Görüşürüz.", "Görüşürüz patron."),
    ("Thanks!", "You're welcome, boss."),
    ("Thank you very much.", "You're welcome, boss."),
    ("That's all.", "You're welcome, boss."),
    ("Good night.", "Good night, boss."),
])
def test_dismissals(text, reply):
    assert reply_for(text) == reply


@pytest.mark.parametrize("text", [
    "Teşekkürler, bir de yarın hava nasıl olacak?",
    "Teşekkür etmenin İngilizcesi nedir?",
    "Bu kadar mı?",                      # soru: (?) noktalaması eşleşmez
    "Sağ olsun, annem de selam söyledi.",
    "Fotosentez nedir?",
    "Thanks for the info, what about Mars?",
])
def test_not_dismissals(text):
    assert reply_for(text) is None


@pytest.mark.parametrize("text, stop", [
    ("Dur.", True), ("Sus!", True), ("Tamam dur", True), ("Stop.", True), ("Bekle", True),
    ("Durum nedir?", False), ("Arabayı durdur", False), ("Yeter.", False), ("Duraklat", False),
])
def test_stop(text, stop):
    from stark.core.dismissal import is_stop
    assert is_stop(text) is stop
