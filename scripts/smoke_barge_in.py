"""Söz kesme yankı testi: Stark hoparlörden uzun (ve içinde kendi adı geçen) cevaplar okurken kendini kesiyor mu?"""
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
s.auto_learn = False


class UI(ConsoleUI):
    def on_state(self, state):
        pass


e = engine_mod.Engine(s, UI())
heard = []
real = e._wake_heard


def spy(audio, text):
    echo = e.controller.state is State.SPEAKING and engine_mod.is_own_echo(text, e.speaker.current_text)
    heard.append((text, echo))
    print(f"  [uyandırma duyuldu: {text!r} → {'YANKI, yok sayıldı' if echo else 'KABUL EDİLDİ'}]", flush=True)
    real(audio, text)


e.transcriber.on_wake = spy
e.start()
while e.state is State.INITIALIZING:
    time.sleep(0.2)
for text in ["Bana Türkiye'nin coğrafi bölgelerini ayrıntılı anlatır mısın?", "Kendini tanıtır mısın?"]:
    e.post(ev.WakeDetected(manual=True))
    time.sleep(2)
    e.post(ev.AckDone(e.controller.session))
    e.post(ev.SpeechStarted())
    e.post(ev.SpeechEnded(np.zeros(1600, dtype="float32")))
    time.sleep(0.2)
    e.post(ev.TranscriptReady(e.controller.session, text, "tr"))
    t0, session = time.monotonic(), e.controller.session
    time.sleep(1)
    while e.state is not State.LISTENING and time.monotonic() - t0 < 90:
        time.sleep(0.2)
    print(f"  → cevap {'KESİLMEDEN bitti' if e.controller.session == session else 'KESİLDİ'} "
          f"({time.monotonic() - t0:.0f} sn)\n", flush=True)
e.shutdown()
accepted = [t for t, echo in heard if not echo]
print("yanlış söz kesme:", len(accepted), accepted)
