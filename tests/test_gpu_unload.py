"""Uykuda konuşma tanıma modeli ekran kartından çıkar, uyanınca ya da ilk tanımada geri yüklenir."""
import time

import numpy as np

from stark.audio.transcription import Transcriber
from stark.config import Settings


class FakeCt2:
    def __init__(self):
        self.model_is_loaded = True
        self.loads = 0

    def unload_model(self):
        self.model_is_loaded = False

    def load_model(self):
        time.sleep(0.05)
        self.loads += 1
        self.model_is_loaded = True


class FakeWhisper:
    def __init__(self):
        self.model = FakeCt2()


def make(on_gpu=True):
    t = Transcriber(Settings(language="tr"), lambda *a: None, lambda *a: None, lambda *a: None)
    t.main, t.main_on_gpu = FakeWhisper(), on_gpu
    return t


def test_unload_and_preload():
    t = make()
    assert t.unload_main() is True and not t.main.model.model_is_loaded
    assert t.unload_main() is False  # zaten boş
    t.preload_main()
    for _ in range(50):
        if t.main.model.model_is_loaded:
            break
        time.sleep(0.02)
    assert t.main.model.model_is_loaded and t.main.model.loads == 1


def test_cpu_model_is_never_unloaded():
    t = make(on_gpu=False)
    assert t.unload_main() is False and t.main.model.model_is_loaded


def test_transcription_reloads_unloaded_model(monkeypatch):
    t = make()
    t.unload_main()
    seen = []
    monkeypatch.setattr(t, "_run_model", lambda model, audio, lang, prompt=None:
                        (seen.append(model.model.model_is_loaded), ("merhaba", "tr", -0.1))[1])
    got = []
    t.on_transcript = lambda *a: got.append(a)
    t._q.put((0, 0, "main", 7, np.zeros(16000, dtype=np.float32)))
    import threading
    threading.Thread(target=t._run, daemon=True).start()
    for _ in range(100):
        if got:
            break
        time.sleep(0.02)
    assert seen == [True] and got[0][:2] == (7, "merhaba")
