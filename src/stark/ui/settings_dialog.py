"""Ayarlar: mikrofon/hoparlör, canlı giriş seviyesi, uyandırma testi, dil, modeller, ses, otomatik başlatma."""
import sys
import time
import winreg
from dataclasses import replace

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
                               QPushButton, QSpinBox, QVBoxLayout)

from ..audio.capture import list_devices
from ..config import BACKUP_DIR, MODELS_DIR, WHISPER_REVISIONS, Settings
from ..memory import backup
from ..core.states import State
from .window_style import dark_title_bar

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULT = "Windows varsayılanı"
# Yeniden başlatma gerektiren ayarlar (model/aygıt motor açılırken yüklenir)
RESTART_FIELDS = ("input_device", "output_device", "llm_model", "whisper_model", "language", "tts_voice_tr")


def autostart_command() -> str:
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pyw}" -m stark'


def autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, "Stark")
            return True
    except OSError:
        return False


def set_autostart(on: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "Stark", 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, "Stark")
            except OSError:
                pass


class SettingsDialog(QDialog):
    def __init__(self, engine, settings: Settings, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.s = settings
        self.setWindowTitle("Stark — Ayarlar")
        self.setMinimumWidth(480)

        # Ses
        self.input = QComboBox()
        self.input.addItems([DEFAULT] + list_devices("input"))
        self.output = QComboBox()
        self.output.addItems([DEFAULT] + list_devices("output"))
        self._select(self.input, settings.input_device)
        self._select(self.output, settings.output_device)
        self.level = QProgressBar(maximum=100, textVisible=False)
        self.wake_info = QLabel("“Stark” de; algılanınca burada görünür.")
        self.wake_info.setObjectName("hint")
        self._wake_count = 0
        audio = QGroupBox("Ses")
        f = QFormLayout(audio)
        f.addRow("Mikrofon", self.input)
        f.addRow("Giriş seviyesi", self.level)
        f.addRow("Hoparlör", self.output)
        f.addRow("Uyandırma testi", self.wake_info)

        # Konuşma
        self.language = QComboBox()
        self.language.addItems(["Türkçe", "İngilizce", "Otomatik"])
        self.language.setCurrentIndex({"tr": 0, "en": 1, "auto": 2}.get(settings.language, 0))
        self.voice = QComboBox()
        voices = sorted(p.name for p in MODELS_DIR.glob("vits-piper-tr_TR-*"))
        for v in voices:
            self.voice.addItem(v.split("-")[3].capitalize(), v)  # vits-piper-tr_TR-fahrettin-medium → Fahrettin
        self.voice.setCurrentIndex(max(0, self.voice.findData(settings.tts_voice_tr)))
        self.speed = QDoubleSpinBox(minimum=0.7, maximum=1.5, singleStep=0.05, value=settings.tts_speed)
        self.listen = QDoubleSpinBox(minimum=5, maximum=30, singleStep=1, value=settings.listen_timeout_s, suffix=" sn")
        self.address_tr = QLineEdit(settings.address_tr)
        self.address_en = QLineEdit(settings.address_en)
        talk = QGroupBox("Konuşma")
        f = QFormLayout(talk)
        self.user_name = QLineEdit(settings.user_name, placeholderText="ör. Ali (isteğe bağlı)")
        f.addRow("Adınız", self.user_name)
        f.addRow("Dil", self.language)
        f.addRow("Hitap (Türkçe, “siz” ile)", self.address_tr)
        f.addRow("Hitap (İngilizce)", self.address_en)
        f.addRow("Türkçe ses", self.voice)
        f.addRow("Konuşma hızı", self.speed)
        f.addRow("Dinleme süresi", self.listen)

        # Modeller
        self.llm = QComboBox(editable=True)
        self.llm.addItems(engine.llm.list_models() or [settings.llm_model])
        self.llm.setCurrentText(settings.llm_model)
        self.asr = QComboBox()
        # large-v3-turbo sunulmuyor: 4 GB ekran kartında dil modeliyle birlikte sığmıyor
        self.asr.addItems([m for m in WHISPER_REVISIONS if m != "tiny"])  # small, medium
        self.asr.setCurrentText(settings.whisper_model)
        self.unload = QSpinBox(minimum=0, maximum=120, value=settings.llm_idle_unload_min, suffix=" dk")
        self.unload.setSpecialValueText("Hep bellekte")
        models = QGroupBox("Modeller (yerel, ücretsiz)")
        f = QFormLayout(models)
        f.addRow("Dil modeli (Ollama)", self.llm)
        f.addRow("Uykudan sonra bellekten çıkar", self.unload)
        f.addRow("Konuşma tanıma", self.asr)
        note = QLabel("medium: Türkçe'de en doğru (~1 sn). small: daha hızlı ama daha çok hata yapar. Dil modeli bellekten "
                      "ve konuşma tanıma modeli ekran kartından çıkar (ekran kartında ~3,8 GB boşalır); “Stark” deyince siz "
                      "konuşurken yeniden yüklenir.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        f.addRow(note)

        # İnternet
        self.internet = QCheckBox("İnternet erişimi (web araması, hava durumu, döviz)")
        self.internet.setChecked(settings.internet_enabled)
        self.city = QLineEdit(settings.city, placeholderText="ör. İstanbul")
        net = QGroupBox("İnternet")
        f = QFormLayout(net)
        f.addRow(self.internet)
        self.fact_check = QCheckBox("Bilgi sorularını internetten doğrula (kaç, hangisi, kim, ne zaman — 5-10 sn)")
        self.fact_check.setChecked(settings.fact_check)
        f.addRow(self.fact_check)
        f.addRow("Varsayılan şehir", self.city)
        net_note = QLabel("Açıkken yalnızca güncel bilgi gerektiren sorularda sorgunuz dış servislere gider: "
                          "arama için yerel SearXNG ya da DuckDuckGo, hava için Open-Meteo, döviz için Frankfurter "
                          "(Avrupa Merkez Bankası). Diğer sohbetler yine yalnızca bu bilgisayarda kalır.")
        net_note.setObjectName("hint")
        net_note.setWordWrap(True)
        f.addRow(net_note)

        # Sistem
        self.autostart = QCheckBox("Windows açılınca Stark'ı başlat")
        self.autostart.setChecked(autostart_enabled())
        self.auto_learn = QCheckBox("Konuşmalardan kendiliğinden öğren (yalnızca sizin söyledikleriniz)")
        self.auto_learn.setChecked(settings.auto_learn)
        system = QGroupBox("Sistem")
        v = QVBoxLayout(system)
        v.addWidget(self.autostart)
        v.addWidget(self.auto_learn)
        backups = backup.list_backups(BACKUP_DIR)
        self.backup_label = QLabel(f"Günlük yedek: {len(backups)} adet (son 7 gün), {BACKUP_DIR}")
        self.backup_label.setObjectName("hint")
        self.backup_label.setWordWrap(True)
        delete_backups = QPushButton("Yedekleri sil")
        delete_backups.clicked.connect(self._delete_backups)
        row = QHBoxLayout()
        row.addWidget(self.backup_label, 1)
        row.addWidget(delete_backups)
        v.addLayout(row)
        privacy = QLabel("Ses kaydı diske yazılmaz. Konuşma tanıma, dil modeli ve ses bu bilgisayarda çalışır.")
        privacy.setObjectName("hint")
        privacy.setWordWrap(True)
        v.addWidget(privacy)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Kaydet")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        for w in (audio, talk, models, net, system):
            lay.addWidget(w)
        lay.addWidget(buttons)

        dark_title_bar(self)
        self._timer = QTimer(self, interval=80)
        self._timer.timeout.connect(lambda: self.level.setValue(min(100, int(engine.capture.level * 900))))
        self._timer.start()

    def _delete_backups(self) -> None:
        if QMessageBox.question(self, "Stark", "Tüm günlük yedekler kalıcı olarak silinsin mi?") \
                == QMessageBox.StandardButton.Yes:
            n = backup.delete_all(BACKUP_DIR)
            self.backup_label.setText(f"{n} yedek dosyası silindi.")

    @staticmethod
    def _select(combo: QComboBox, name: str) -> None:
        i = combo.findText(name) if name else 0
        combo.setCurrentIndex(max(0, i))

    def on_engine_state(self, prev: State, state: State) -> None:
        if prev is State.IDLE and state in (State.LISTENING, State.TRANSCRIBING):
            self._wake_count += 1
            self.wake_info.setText(f"✓ Algılandı ({self._wake_count}. kez, {time.strftime('%H:%M:%S')})")

    def result_settings(self) -> Settings:
        dev = lambda c: "" if c.currentIndex() == 0 else c.currentText()  # noqa: E731
        return replace(
            self.s,
            input_device=dev(self.input), output_device=dev(self.output),
            language=["tr", "en", "auto"][self.language.currentIndex()],
            internet_enabled=self.internet.isChecked(), city=self.city.text().strip(),
            fact_check=self.fact_check.isChecked(), user_name=self.user_name.text().strip(),
            auto_learn=self.auto_learn.isChecked(),
            address_tr=self.address_tr.text().strip() or "patron",
            address_en=self.address_en.text().strip() or "boss",
            tts_voice_tr=self.voice.currentData() or self.s.tts_voice_tr,
            tts_speed=round(self.speed.value(), 2), listen_timeout_s=self.listen.value(),
            llm_model=self.llm.currentText().strip(), llm_idle_unload_min=self.unload.value(), whisper_model=self.asr.currentText())

    def apply_autostart(self) -> None:
        if self.autostart.isChecked() != autostart_enabled():
            set_autostart(self.autostart.isChecked())
