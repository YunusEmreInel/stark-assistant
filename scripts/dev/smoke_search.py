"""Motor üzerinden internet akışı (geçici veritabanı): hava, döviz, arama + kaynaklardan cevap."""
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
s.city = "İstanbul"


class UI(ConsoleUI):
    def on_state(self, state):
        pass


e = engine_mod.Engine(s, UI())
e.start()
while e.state is State.INITIALIZING:
    time.sleep(0.2)
for text in sys.argv[1:] or ["Bugün hava nasıl?", "Dolar kaç lira?", "Python 3.14 sürümünde neler yeni?",
                             "Türkiye'nin gündemindeki son haberler neler?"]:
    e.post(ev.WakeDetected(manual=True))
    time.sleep(0.6)
    e.post(ev.AckDone(e.controller.session))
    e.post(ev.SpeechStarted())
    e.post(ev.SpeechEnded(np.zeros(1600, dtype="float32")))
    time.sleep(0.2)
    e.post(ev.TranscriptReady(e.controller.session, text, "tr"))
    t0 = time.monotonic()
    time.sleep(1)
    while e.state is not State.LISTENING and time.monotonic() - t0 < 90:
        time.sleep(0.2)
    print(f"  (toplam {time.monotonic() - t0:.1f} sn)")
e.shutdown()
