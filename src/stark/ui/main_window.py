"""Ana pencere: başlık çubuğu, küre, durum, konuşma paneli, araç çubuğu, durum çubuğu. X → tepsiye gizler."""
import html
import re
import time

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QToolButton,
                               QVBoxLayout, QWidget)

from ..core.states import State
from . import help_text
from .orb import OrbWidget
from .style import ACCENT, ICON, STATE_HINT, STATE_TEXT
from .taskbar import set_identity
from .window_style import dark_title_bar

MAX_ENTRIES = 12  # panelde son birkaç tur; tamamı "Geçmiş"te


def _tool(icon: str, tip: str, name: str = "") -> QToolButton:
    b = QToolButton(text=icon, toolTip=tip)
    b.setAccessibleName(tip.split("  (")[0])  # simge yazı tipi karakteri yerine okunur ad (ekran okuyucu/otomasyon)
    if name:
        b.setObjectName(name)
    b.setFixedSize(QSize(40, 40))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def _render(text: str) -> str:
    """Model metnini güvenli HTML'e çevirir: kod blokları, **kalın**, satır sonları."""
    out = []
    for i, part in enumerate(text.split("```")):
        if i % 2:
            code = part.split("\n", 1)[1] if "\n" in part else part
            out.append("<pre style='background:#0A0A0B;border:1px solid #222226;padding:8px;"
                       f"font-family:Cascadia Mono,Consolas;font-size:9.5pt'>{html.escape(code.strip())}</pre>")
        else:
            t = html.escape(part.strip("\n"))
            # Uzun (ör. Google Haberler) adresler yerine kısa bir bağlantı işareti
            t = re.sub(r"(https?://[^\s<]+)", rf"<a style='color:{ACCENT};text-decoration:none' href='\1'>↗</a>", t)
            t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
            t = re.sub(r"`([^`]+)`", r"<span style='font-family:Cascadia Mono,Consolas'>\1</span>", t)
            out.append(t.replace("\n", "<br>"))
    return "".join(out)


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stark — Kullanım kılavuzu")
        self.resize(640, 720)
        view = QTextBrowser()
        view.setHtml(help_text.guide_html())
        close = QPushButton("Kapat")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addWidget(view)
        lay.addLayout(row)
        dark_title_bar(self)


class MainWindow(QWidget):
    hidden_to_tray = Signal()

    def __init__(self, engine, icon: QIcon):
        super().__init__()
        self.engine = engine
        self.entries: list[list] = []  # [rol, metin, saat]
        self.setWindowTitle("Stark")
        self.setWindowIcon(icon)
        self.resize(560, 760)
        self.setMinimumSize(440, 600)

        # ---- başlık ----
        header = QFrame(objectName="header")
        header.setFixedHeight(44)
        brand = QLabel("STARK", objectName="brand")
        self.chip = QLabel("", objectName="chip")
        self.chip.setFixedHeight(24)
        self.quit_btn = _tool(ICON["power"], "Tamamen çık", "flat")
        self.quit_btn.setFixedSize(QSize(30, 30))
        # ⓘ: üzerine gelince özet, tıklayınca tüm komutlar (içerik: ui/help_text.py)
        self.info_btn = _tool(ICON["info"], "Stark neler yapabilir?", "flat")
        self.info_btn.setFixedSize(QSize(30, 30))
        self.info_btn.setToolTip(help_text.tooltip_html())
        self.info_btn.clicked.connect(lambda: HelpDialog(self).exec())
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 0, 8, 0)
        h.addWidget(brand)
        h.addStretch(1)
        h.addWidget(self.chip)
        h.addSpacing(6)
        h.addWidget(self.info_btn)
        h.addWidget(self.quit_btn)

        # ---- küre ve durum ----
        self.orb = OrbWidget(lambda: (engine.mic_level, engine.tts_level))
        self.status = QLabel("", objectName="stateTitle", alignment=Qt.AlignmentFlag.AlignCenter)
        self.hint = QLabel("", objectName="stateHint", alignment=Qt.AlignmentFlag.AlignCenter)

        # ---- konuşma paneli ----
        panel = QFrame(objectName="panel")
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("KONUŞMA", objectName="panelTitle"))
        title_row.addStretch(1)
        self.transcript = QTextBrowser(objectName="transcript", openExternalLinks=True)
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(14, 10, 10, 10)
        pv.addLayout(title_row)
        pv.addWidget(self.transcript)

        # ---- hata ----
        self.error_bar = QFrame(objectName="errorBar")
        self.error_label = QLabel("", wordWrap=True)
        self.retry_btn = QPushButton("Tekrar dene")
        self.retry_btn.clicked.connect(engine.retry)
        dismiss = QPushButton("Kapat")
        dismiss.clicked.connect(lambda: self.error_bar.hide())
        eb = QHBoxLayout(self.error_bar)
        eb.setContentsMargins(10, 6, 6, 6)
        eb.addWidget(self.error_label, 1)
        eb.addWidget(self.retry_btn)
        eb.addWidget(dismiss)
        self.error_bar.hide()

        # ---- araç çubuğu ----
        self.pause_btn = _tool(ICON["pause"], "Dinlemeyi duraklat")
        self.stop_btn = _tool(ICON["stop"], "Yanıtı durdur  (Ctrl+Alt+S)")
        self.wake_btn = _tool(ICON["mic"], "Uyandır  (Ctrl+Alt+W)", "mic")
        self.wake_btn.setFixedSize(QSize(56, 56))
        self.new_btn = _tool(ICON["new"], "Yeni sohbet")
        self.history_btn = _tool(ICON["history"], "Geçmiş ve hafıza")
        self.settings_btn = _tool(ICON["settings"], "Ayarlar")
        self.wake_btn.clicked.connect(engine.wake)
        self.pause_btn.clicked.connect(engine.toggle_pause)
        self.stop_btn.clicked.connect(engine.stop_response)
        self.new_btn.clicked.connect(self._new_conversation)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addStretch(1)
        bar.addWidget(self.pause_btn)
        bar.addWidget(self.stop_btn)
        bar.addSpacing(14)
        bar.addWidget(self.wake_btn)
        bar.addSpacing(14)
        bar.addWidget(self.new_btn)
        bar.addWidget(self.history_btn)
        bar.addWidget(self.settings_btn)
        bar.addStretch(1)

        # ---- durum çubuğu ----
        footer = QFrame(objectName="footer")
        footer.setFixedHeight(26)
        self.footer_left = QLabel("", objectName="footerText")
        self.footer_right = QLabel("", objectName="footerText")
        f = QHBoxLayout(footer)
        f.setContentsMargins(14, 0, 14, 0)
        f.addWidget(self.footer_left)
        f.addStretch(1)
        f.addWidget(self.footer_right)
        s = engine.s
        self.footer_left.setText(f"{s.llm_model}  ·  whisper {s.whisper_model}  ·  yerel")

        body = QVBoxLayout()
        body.setContentsMargins(16, 8, 16, 12)
        body.setSpacing(6)
        body.addWidget(self.orb, 5)
        body.addWidget(self.status)
        body.addWidget(self.hint)
        body.addSpacing(8)
        body.addWidget(panel, 4)
        body.addWidget(self.error_bar)
        body.addSpacing(6)
        body.addLayout(bar)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(header)
        lay.addLayout(body, 1)
        lay.addWidget(footer)
        self._render_transcript()
        self.set_state(State.INITIALIZING)
        dark_title_bar(self)
        set_identity(int(self.winId()), "Stark.VoiceAssistant")  # görev çubuğunda Python simgesi görünmesin

    # ---- motor sinyalleri ----
    def set_state(self, state: State) -> None:
        self.orb.set_state(state)
        self.status.setText(STATE_TEXT[state.value].upper())
        if state is not State.ERROR:
            self.hint.setText(STATE_HINT[state.value])
            self.error_bar.hide()
        busy = state in (State.TRANSCRIBING, State.THINKING, State.SPEAKING)
        ready = state not in (State.INITIALIZING, State.ERROR, State.STOPPED)
        self.stop_btn.setEnabled(busy)
        self.wake_btn.setEnabled(ready)
        self.pause_btn.setEnabled(ready)
        paused = state is State.PAUSED
        self.pause_btn.setText(ICON["play"] if paused else ICON["pause"])
        self.pause_btn.setToolTip("Dinlemeye devam et" if paused else "Dinlemeyi duraklat")
        mic_on = state not in (State.PAUSED, State.STOPPED, State.ERROR, State.INITIALIZING)
        dot = ACCENT if mic_on else "#5A5A62"
        self.chip.setText(f"<span style='color:{dot}'>●</span>&nbsp; Mikrofon {'açık' if mic_on else 'kapalı'}")

    def set_status(self, text: str) -> None:
        self.hint.setText(text)

    def set_user_text(self, text: str) -> None:
        self.entries.append(["user", text, time.strftime("%H:%M")])
        self._render_transcript()

    def set_answer(self, text: str, final: bool) -> None:
        if not self.entries or self.entries[-1][0] != "stark":
            self.entries.append(["stark", text, time.strftime("%H:%M")])
        else:
            self.entries[-1][1] = text
        self._render_transcript()

    def _render_transcript(self) -> None:
        if not self.entries:
            self.transcript.setHtml("<p style='color:#5A5A62'>Henüz konuşma yok.</p>")
            return
        rows = []
        for role, text, at in self.entries[-MAX_ENTRIES:]:
            name, color = ("SİZ", "#8A8A94") if role == "user" else ("STARK", ACCENT)
            body_color = "#B8B8C0" if role == "user" else "#ECECEE"
            rows.append(
                f"<div style='margin:0 0 12px 0'>"
                f"<span style='color:{color};font-size:8pt;font-weight:600;letter-spacing:1px'>{name}</span>"
                f"&nbsp;&nbsp;<span style='color:#4E4E56;font-size:8pt'>{at}</span><br>"
                f"<span style='color:{body_color}'>{_render(text)}</span></div>")
        self.transcript.setHtml("".join(rows))
        sb = self.transcript.verticalScrollBar()
        sb.setValue(sb.maximum())

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.retry_btn.setVisible(self.engine.state is State.ERROR)
        self.error_bar.show()

    def show_timing(self, t: dict) -> None:
        if "first_audio" in t:
            self.footer_right.setText(f"Yanıt süresi {t['first_audio']:.1f} sn")
        if t.get("model"):  # ör. "Groq · Qwen3.8 27B" ya da "yerel · qwen3:4b-instruct"
            self.footer_left.setText(f"{t['model']}  ·  whisper {self.engine.s.whisper_model}")

    def _new_conversation(self) -> None:
        self.engine.new_conversation()
        self.entries.clear()
        self._render_transcript()
        self.hint.setText("Yeni sohbet başladı")

    # ---- pencere ----
    def changeEvent(self, e) -> None:
        if e.type() in (QEvent.Type.ActivationChange, QEvent.Type.WindowStateChange):
            # Pencere arkada ya da simge durumundayken uykudaki küre çizilmesin
            self.orb.set_window_active(self.isActiveWindow() and not self.isMinimized())
        super().changeEvent(e)

    def closeEvent(self, e: QCloseEvent) -> None:
        # X uygulamayı kapatmaz; tepside çalışmaya devam eder
        e.ignore()
        self.hide()
        self.hidden_to_tray.emit()

    def bring_to_front(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        try:  # Qt'nin activateWindow'u arka plandan çağrılınca Windows tarafından yok sayılabiliyor
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except (AttributeError, OSError):
            pass
