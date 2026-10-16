"""Motor üzerinden hafıza akışı (geçici veritabanı): hatırla → sor → listele → unut → kişisel soru."""
import sys
import tempfile
import time
from pathlib import Path

from stark.cli import ConsoleUI
from stark.config import Settings
from stark.core import engine as engine_mod
from stark.core import events as ev
from stark.core.states import State

sys.stdout.reconfigure(encoding="utf-8")
engine_mod.DB_FILE = Path(tempfile.mkdtemp()) / "smoke.db"


class UI(ConsoleUI):
    def on_state(self, state):
        pass


e = engine_mod.Engine(Settings.load(), UI())
e.start()
while e.state is State.INITIALIZING:
    time.sleep(0.2)
for text in ["Bunu hatırla: en sevdiğim renk mavi.", "En sevdiğim renk ne?", "Annemin adını biliyor musun?",
             "Neleri hatırlıyorsun?", "Unut: en sevdiğim renk.", "Neleri hatırlıyorsun?"]:
    e.post(ev.WakeDetected(manual=True))
    time.sleep(0.6)
    e.post(ev.AckDone(e.controller.session))
    e.post(ev.SpeechStarted())
    e.post(ev.SpeechEnded(__import__("numpy").zeros(1600, dtype="float32")))
    time.sleep(0.2)
    e.controller.handle  # durum TRANSCRIBING; ASR yerine metni doğrudan ver
    e.post(ev.TranscriptReady(e.controller.session, text, "tr"))
    t0 = time.monotonic()
    while e.state is not State.LISTENING and time.monotonic() - t0 < 40:
        time.sleep(0.2)
print("kalıcı sohbet kaydı:", e.repo.list_conversations())
e.shutdown()
