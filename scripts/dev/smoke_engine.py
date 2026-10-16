"""Uçtan uca duman testi: kayıttaki "Stark, bugün hava nasıl?" bölümünü uyandırma komutu olarak verir,
cevabı seslendirir, LISTENING'e ve 10 sn sonra IDLE'a dönüşü doğrular."""
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from stark.cli import ConsoleUI
from stark.config import Settings
from stark.core import events as ev
from stark.core.engine import Engine
from stark.core.states import State

sys.stdout.reconfigure(encoding="utf-8")
rec = np.load(Path(tempfile.gettempdir()) / "stark_wake_test.npy")
command = rec[int(9.6 * 16000):int(11.8 * 16000)]

states = []


class UI(ConsoleUI):
    def on_state(self, state):
        states.append((round(time.monotonic(), 1), state))
        super().on_state(state)


engine = Engine(Settings.load(), UI())
t0 = time.monotonic()
engine.start()
while engine.state is State.INITIALIZING and time.monotonic() - t0 < 180:
    time.sleep(0.2)
print(f"hazırlık: {time.monotonic() - t0:.1f} sn")
engine.post(ev.WakeDetected(command_audio=command))
deadline = time.monotonic() + 90
while time.monotonic() < deadline and not any(s is State.LISTENING for _, s in states):
    time.sleep(0.2)
t_listen = time.monotonic()
while time.monotonic() < t_listen + 12 and engine.state is not State.IDLE:
    time.sleep(0.2)
print(f"LISTENING → IDLE: {time.monotonic() - t_listen:.1f} sn (beklenen ~10)")
engine.shutdown()
