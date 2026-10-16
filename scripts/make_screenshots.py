"""README görsellerini üretir: docs/images/main-panel.png ve docs/images/corner-panel.png.

Sohbet içeriği gösterilmez (konuşma alanı boş), motor başlatılmaz. README İngilizce olduğundan pencere
yazıları yalnızca görsel için İngilizceye çevrilir (uygulamanın kendi arayüzü Türkçedir).
Kullanım: .venv\\Scripts\\python.exe scripts\\make_screenshots.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPoint, QRect, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from stark.config import Settings  # noqa: E402
from stark.core.states import State  # noqa: E402
from stark.ui.icon import app_icon  # noqa: E402
from stark.ui.main_window import MainWindow  # noqa: E402
from stark.ui.mini_panel import MiniPanel  # noqa: E402
from stark.ui.style import QSS  # noqa: E402

OUT = ROOT / "docs" / "images"


class DemoEngine:
    """Pencerenin ihtiyaç duyduğu kadar motor: modeller yüklenmez, mikrofon açılmaz."""
    def __init__(self):
        self.s = Settings()
        self.state = State.LISTENING
        self.mic_level, self.tts_level = 0.25, 0.0

    def __getattr__(self, name):
        return lambda *a, **k: None


def desktop_corner(panel: QPixmap) -> QPixmap:
    """Mini paneli masaüstünün sağ alt köşesinde, görev çubuğunun üstünde gösterir."""
    w, h, bar = 620, 380, 40
    img = QPixmap(w, h)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, QColor("#1d2b3f"))
    grad.setColorAt(1, QColor("#3a4a63"))
    p.fillRect(img.rect(), grad)
    p.fillRect(QRect(0, h - bar, w, bar), QColor(32, 32, 36, 240))
    p.setPen(QColor("#d8d8dc"))
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(QRect(w - 90, h - bar, 80, bar), Qt.AlignmentFlag.AlignCenter, "14:05\n16.10.2026")
    p.drawPixmap(QPoint(w - panel.width() - 16, h - bar - panel.height() - 16), panel)
    p.end()
    return img


def english_labels(win) -> None:
    """Görseldeki Türkçe pencere yazılarının İngilizcesi (yalnızca README görseli için)."""
    from PySide6.QtWidgets import QLabel
    win.status.setText("LISTENING")
    win.hint.setText("Go ahead · goes back to sleep after 10 s of silence")
    win.chip.setText("<span style='color:#E8A23A'>●</span>&nbsp; Microphone on")
    win.transcript.setHtml("<p style='color:#5A5A62'>No conversation yet.</p>")
    win.footer_left.setText(f"{win.engine.s.llm_model}  ·  whisper {win.engine.s.whisper_model}  ·  local")
    for label in win.findChildren(QLabel):
        if label.text() == "KONUŞMA":
            label.setText("CONVERSATION")


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    OUT.mkdir(parents=True, exist_ok=True)
    engine = DemoEngine()
    win = MainWindow(engine, app_icon())
    win.set_state(State.LISTENING)
    english_labels(win)
    win.show()
    mini = MiniPanel(engine)
    mini.set_state(State.LISTENING)
    mini.label.setText("LISTENING")
    mini.move(-2000, -2000)  # ekranda görünmesin; yalnızca çizilsin
    mini.show()

    def capture():
        win.grab().save(str(OUT / "main-panel.png"))
        desktop_corner(mini.grab()).save(str(OUT / "corner-panel.png"))
        print("kaydedildi:", OUT / "main-panel.png", OUT / "corner-panel.png", flush=True)
        os._exit(0)  # pencere X'i tepsiye gizlediğinden normal çıkış beklemede kalıyordu

    QTimer.singleShot(1500, capture)  # küre animasyonu birkaç kare dönsün
    app.exec()


if __name__ == "__main__":
    main()
