"""Çok turlu konuşma (aynı oturum, 10 sn penceresi içinde): takip cümlelerinin bağlamı doğru kurup kurmadığı."""
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from stark.cli import ConsoleUI
from stark.config import Settings
from stark.core import engine as engine_mod
from stark.core import events as ev
from stark.core.states import State

sys.stdout.reconfigure(encoding="utf-8")
engine_mod.DB_FILE = Path(tempfile.mkdtemp()) / "smoke.db"
s = Settings.load()
s.internet_enabled = True


class UI(ConsoleUI):
    def on_state(self, state):
        pass

    def on_assistant_text(self, text, final):
        if final:
            print(f"Stark: {text.split(chr(10) + chr(10) + 'Kaynaklar')[0]}\n", flush=True)


e = engine_mod.Engine(s, UI())
e.start()
while e.state is State.INITIALIZING:
    time.sleep(0.2)
e.post(ev.WakeDetected(manual=True))
time.sleep(0.6)
e.post(ev.AckDone(e.controller.session))
for text in sys.argv[1:]:
    while e.state is not State.LISTENING:
        time.sleep(0.2)
    t0 = time.monotonic()
    e.post(ev.SpeechStarted())
    e.post(ev.SpeechEnded(np.zeros(1600, dtype="float32")))
    time.sleep(0.15)
    e.post(ev.TranscriptReady(e.controller.session, text, "tr"))
    time.sleep(1)
    while e.state is not State.LISTENING and time.monotonic() - t0 < 90:
        time.sleep(0.2)
e.shutdown()
