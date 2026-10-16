"""Ayarlar penceresinde fare tekerleğiyle aşağı inmek açılır liste/sayı kutularının değerini değiştirmemeli."""
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QScrollArea

from stark.config import Settings
from stark.ui.settings_dialog import SettingsDialog


class FakeEngine:
    class llm:
        @staticmethod
        def list_models():
            return ["qwen3:4b-instruct"]

    class capture:
        level = 0.0


def wheel(widget, steps=-3):
    ev = QWheelEvent(QPointF(5, 5), QPointF(widget.mapToGlobal(QPoint(5, 5))), QPoint(0, 0),
                     QPoint(0, 120 * steps), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, ev)


def test_wheel_scrolls_page_instead_of_changing_values():
    QApplication.instance() or QApplication([])
    dlg = SettingsDialog(FakeEngine(), Settings(tts_speed=1.0, llm_idle_unload_min=1))
    dlg.resize(560, 400)
    dlg.show()
    voice, speed, unload = dlg.voice.currentIndex(), dlg.speed.value(), dlg.unload.value()
    bar = dlg.findChild(QScrollArea).verticalScrollBar()
    for w in (dlg.voice, dlg.speed, dlg.unload, dlg.language):
        wheel(w)
    assert (dlg.voice.currentIndex(), dlg.speed.value(), dlg.unload.value()) == (voice, speed, unload)
    assert bar.value() > 0  # sayfa kaydı
    dlg.close()
