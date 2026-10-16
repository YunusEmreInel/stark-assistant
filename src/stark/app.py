"""Stark masaüstü uygulaması: pencere + sistem tepsisi + motor. Tek örnek çalışır."""
import os
import sys
import time
from dataclasses import asdict

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .config import Settings
from .core.engine import Engine
from .core.states import State
from .ui.bridge import Bridge
from .ui.history_dialog import HistoryDialog
from .ui.hotkeys import GlobalHotkeys
from .ui.icon import app_icon
from .ui.main_window import MainWindow
from .ui.mini_panel import MiniPanel
from .ui.settings_dialog import RESTART_FIELDS, SettingsDialog
from .ui.style import QSS, STATE_TEXT

INSTANCE_KEY = "stark-assistant-single-instance"


class StarkApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.settings = Settings.load()
        self.bridge = Bridge()
        self.engine = Engine(self.settings, self.bridge)
        self.icon = app_icon()
        self.icon_paused = app_icon(muted=True)
        self.icon_error = app_icon(error=True)
        app.setWindowIcon(self.icon)
        self.window = MainWindow(self.engine, self.icon)
        self.mini = MiniPanel(self.engine)
        self.settings_dialog: SettingsDialog | None = None
        self._prev_state = State.INITIALIZING
        self._quitting = False

        self._build_tray()
        self.window.hidden_to_tray.connect(self._on_hidden)
        self.window.settings_btn.clicked.connect(self.open_settings)
        self.window.history_btn.clicked.connect(
            lambda: HistoryDialog(self.engine.repo, self.window).exec())
        self.window.quit_btn.clicked.connect(self.quit)

        b = self.bridge
        b.state.connect(self._on_state)
        b.status.connect(self.window.set_status)
        b.user_text.connect(self.window.set_user_text)
        b.assistant_text.connect(self.window.set_answer)
        b.error.connect(self.window.show_error)
        b.timing.connect(self.window.show_timing)

        self.hotkeys = GlobalHotkeys()
        self.hotkeys.register("Uyandır (Ctrl+Alt+W)", "W", self.engine.wake)
        self.hotkeys.register("Yanıtı durdur (Ctrl+Alt+S)", "S", self.engine.stop_response)
        app.installNativeEventFilter(self.hotkeys)
        if self.hotkeys.failed:
            QTimer.singleShot(3000, lambda: self.window.show_error(
                "Bu kısayollar başka bir uygulamada kullanılıyor: " + ", ".join(self.hotkeys.failed)))

        self.engine.start()
        self.window.show()
        # Geliştirme: STARK_SNAPSHOT=dosya.png ise pencere yalnızca kendini (başka uygulamaları değil) kaydeder
        snap = os.environ.get("STARK_SNAPSHOT")
        if snap:
            QTimer.singleShot(int(os.environ.get("STARK_SNAPSHOT_DELAY", "20000")),
                              lambda: self.window.grab().save(snap))

    # ---- tepsi ----
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.icon)
        self.tray.setToolTip("Stark")
        menu = QMenu()
        self.act_show = QAction("Göster", triggered=self.window.bring_to_front)
        self.act_wake = QAction("Uyandır", triggered=self.engine.wake)
        self.act_pause = QAction("Duraklat", triggered=self.engine.toggle_pause)
        self.act_quit = QAction("Tamamen çık", triggered=self.quit)
        for a in (self.act_show, self.act_wake, self.act_pause):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(self.act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.window.bring_to_front() if r in (QSystemTrayIcon.ActivationReason.Trigger,
                                                            QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self._menu = menu
        self.tray.show()

    def _on_hidden(self) -> None:
        if not self.settings.extra.get("tray_notice_shown"):
            self.tray.showMessage("Stark arka planda çalışıyor",
                                  "Pencereyi kapattın ama Stark tepside dinlemeye devam ediyor. "
                                  "Tamamen kapatmak için tepsi simgesine sağ tıklayıp “Tamamen çık”ı seç.",
                                  self.icon, 8000)
            self.settings.extra["tray_notice_shown"] = True
            self.settings.save()

    # ---- durum ----
    def _on_state(self, state: State) -> None:
        prev, self._prev_state = self._prev_state, state
        self.window.set_state(state)
        self.mini.set_state(state)
        self.tray.setToolTip(f"Stark — {STATE_TEXT[state.value]}")
        self.tray.setIcon(self.icon_paused if state is State.PAUSED else
                          self.icon_error if state is State.ERROR else self.icon)
        self.act_pause.setText("Devam et" if state is State.PAUSED else "Duraklat")
        if self.settings_dialog:
            self.settings_dialog.on_engine_state(prev, state)
        # Pencere gizliyken uyanınca odak çalmayan mini panel
        if not self.window.isVisible():
            if prev is State.IDLE and state in (State.LISTENING, State.TRANSCRIBING):
                self.mini.popup()
            elif state in (State.IDLE, State.PAUSED, State.STOPPED):
                self.mini.hide()
        else:
            self.mini.hide()
        if state is State.ERROR and not self.window.isVisible():
            self.tray.showMessage("Stark", "Bir sorun oluştu. Ayrıntı için pencereyi aç.", self.icon_error, 5000)

    # ---- ayarlar ----
    def open_settings(self) -> None:
        dlg = SettingsDialog(self.engine, self.settings, self.window)
        self.settings_dialog = dlg
        accepted = dlg.exec()
        self.settings_dialog = None
        if not accepted:
            return
        new = dlg.result_settings()
        dlg.apply_autostart()
        needs_restart = any(getattr(new, f) != getattr(self.settings, f) for f in RESTART_FIELDS)
        new.save()
        # Yeniden başlatma gerektirmeyenler hemen uygulanır (bileşenler aynı Settings nesnesini paylaşır)
        for k, v in asdict(new).items():
            setattr(self.settings, k, v)
        self.engine.controller.listen_timeout = new.listen_timeout_s
        if needs_restart:
            r = QMessageBox.question(self.window, "Stark", "Bu değişiklikler için Stark yeniden başlamalı. Şimdi?")
            if r == QMessageBox.StandardButton.Yes:
                self.restart()

    # ---- çıkış ----
    def restart(self) -> None:
        self.quit(restart=True)

    def quit(self, restart: bool = False) -> None:
        if self._quitting:
            return
        self._quitting = True
        # Önce "çalışıyorum" kanalını kapat ve görünür her şeyi gizle: kapanış birkaç saniye sürerken yapılan
        # yeni bir çift tıklama, kapanmakta olan bu örneği "açık" sanıp sessizce çıkmasın.
        self.app.instance_server.close()
        self.window.hide()
        self.mini.hide()
        self.tray.hide()
        self.app.processEvents()
        self.hotkeys.unregister_all()
        self.engine.shutdown()  # mikrofon, TTS, LLM istekleri kapanır; Ollama süreci kapatılmaz
        if restart:
            QProcess.startDetached(sys.executable, ["-m", "stark"])
        self.app.quit()


APP_USER_MODEL_ID = "Stark.VoiceAssistant"


def main() -> int:
    # Kendi uygulama kimliği: aksi halde Windows görev çubuğunda pencereyi pythonw.exe'ye bağlayıp
    # Python simgesini gösteriyor. Pencere oluşturulmadan önce ayarlanmalı.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Stark")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(QSS)

    # Tek örnek: ikinci açılış çalışan Stark'a sinyal verir. Yalnızca "tamam" onayı gelirse çıkar; onay gelmezse
    # (ör. o örnek kapanmaktaysa) onun bitmesini bekleyip kendisi normal şekilde açılır.
    command = b"quit" if "--quit" in sys.argv else b"show"
    if _signal_running_instance(command):
        return 0
    if command == b"quit":
        return 0  # kapatılacak çalışan Stark yok
    QLocalServer.removeServer(INSTANCE_KEY)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)  # yalnızca aynı Windows kullanıcısı bağlanır
    server.listen(INSTANCE_KEY)
    app.instance_server = server

    stark = StarkApp(app)

    def on_connection():
        conn = server.nextPendingConnection()
        if conn is None:
            return
        conn.waitForReadyRead(300)
        data = bytes(conn.readAll())
        conn.write(b"ok")  # ikinci örnek bu onayı görünce çıkar
        conn.waitForBytesWritten(300)
        conn.disconnected.connect(conn.deleteLater)
        if data.startswith(b"quit"):
            QTimer.singleShot(0, stark.quit)
        else:  # içerik gelmese bile (eski sürümler) pencere gösterilir
            stark.window.bring_to_front()

    server.newConnection.connect(on_connection)
    code = app.exec()
    # CUDA/ctranslate2 iş parçacıklarının yorumlayıcı kapanışında asılı kalmaması için doğrudan çık
    sys.stdout.flush()
    os._exit(code)


def _signal_running_instance(command: bytes) -> bool:
    """Çalışan Stark'a komut yollar; onay ("ok") alınırsa True. Kapanmakta olan örnek onay vermez."""
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if not sock.waitForConnected(300):
        return False
    try:  # çalışan Stark'ın penceresini öne alabilmesi için Windows'tan izin ver
        import ctypes
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
    except (AttributeError, OSError):
        pass
    sock.write(command)
    sock.waitForBytesWritten(300)
    acknowledged = sock.waitForReadyRead(2000) and bytes(sock.readAll()).startswith(b"ok")
    sock.abort()
    if acknowledged:
        return True
    # Onay yok: o örnek kapanıyor. Kanalı bırakmasını bekle (en çok ~8 sn), sonra normal açılışa devam et.
    for _ in range(40):
        probe = QLocalSocket()
        probe.connectToServer(INSTANCE_KEY)
        if not probe.waitForConnected(100):
            return False
        probe.abort()
        time.sleep(0.2)
    return False
