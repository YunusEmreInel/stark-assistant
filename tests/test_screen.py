import pytest

from stark.tools import screen
from stark.tools.screen import ScreenCommand, parse


@pytest.mark.parametrize("text, cmd", [
    ("Ekranda ne yazıyor?", ScreenCommand("read")),
    ("Ekranı oku.", ScreenCommand("read")),
    ("Ekrandakini özetle", ScreenCommand("summarize")),
    ("Bunu özetle.", ScreenCommand("summarize")),
    ("Bu sayfayı kısaca özetle", ScreenCommand("summarize")),
    ("Kopyaladığımı özetle", ScreenCommand("summarize", "clipboard")),
    ("Panodakini İngilizceye çevir", ScreenCommand("translate", "clipboard", "English")),
    ("Bunu Türkçeye çevir.", ScreenCommand("translate", "screen", "Turkish")),
    ("Bu yazıyı Almancaya çevir", ScreenCommand("translate", "screen", "German")),
    ("Ekrandakini açıkla", ScreenCommand("explain")),
])
def test_parse(text, cmd):
    assert parse(text) == cmd


@pytest.mark.parametrize("text", ["Fotosentez nedir?", "Ekran kartım ne?", "Bunu hatırla: ekran 15 inç",
                                  "Ekran görüntüsü al", "Merhaba nasılsın"])
def test_not_screen_commands(text):
    assert parse(text) is None


def test_note_marks_text_as_untrusted_and_clips():
    note = screen.build_note(ScreenCommand("summarize"), "x" * 5000, "Chrome")
    assert "untrusted DATA" in note and "metin kısaltıldı" in note and len(note) < 4200


def test_ocr_reads_rendered_turkish_text():
    """Windows yazı tanıması gerçekten çalışıyor mu (Türkçe karakterlerle)?"""
    from PySide6.QtCore import QBuffer, QIODevice, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    img = QImage(900, 160, QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setPen(Qt.GlobalColor.black)
    p.setFont(QFont("Segoe UI", 28))
    p.drawText(20, 90, "Güneş sistemi şöyle çalışır: 8 gezegen")
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    text = screen.ocr(bytes(buf.data()))
    assert "gezegen" in text and "Güneş" in text
