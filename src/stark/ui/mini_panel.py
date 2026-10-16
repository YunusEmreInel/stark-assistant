"""Ana pencere gizliyken uyanınca köşede beliren küçük panel. Klavye odağını çalmaz."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..core.states import State
from .orb import OrbWidget
from .style import STATE_TEXT


class MiniPanel(QWidget):
    def __init__(self, engine):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(230, 250)
        self.orb = OrbWidget(lambda: (engine.mic_level, engine.tts_level))
        self.orb.setStyleSheet("background: transparent")
        self.label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter, wordWrap=True)
        self.label.setStyleSheet("background: rgba(14,14,16,235); color: #E8A23A; border: 1px solid #26262B;"
                                 "border-radius: 6px; padding: 5px; font-size: 8.5pt; font-weight: 600;"
                                 "letter-spacing: 2px")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self.orb, 1)
        lay.addWidget(self.label)

    def set_state(self, state: State) -> None:
        self.orb.set_state(state)
        self.label.setText(STATE_TEXT[state.value].upper())

    def popup(self) -> None:
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - self.width() - 16, geo.bottom() - self.height() - 16)
        self.show()  # activateWindow çağrılmaz: başka uygulamaya yazarken odak kaymaz
