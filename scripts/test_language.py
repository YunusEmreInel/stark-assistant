"""Otomatik dil seçimi testi: kayıttaki Türkçe cümleler + Piper ile üretilmiş İngilizce/Türkçe cümleler."""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_voice import resample16k, tts  # noqa: E402

from stark.audio.transcription import Transcriber, _add_cuda_dll_paths  # noqa: E402
from stark.config import Settings  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
_add_cuda_dll_paths()
s = Settings.load()
s.language = "auto"
t = Transcriber(s, lambda a: None, lambda *a: None, print)
t.load()

samples = []
rec = np.load(Path(tempfile.gettempdir()) / "stark_wake_test.npy")
for a, b in [(9.6, 11.8), (18.8, 20.6), (32.4, 33.6), (37.7, 38.9), (46.8, 48.2)]:
    samples.append(("tr (kullanıcı)", rec[int(a * 16000):int(b * 16000)]))
en = tts("vits-piper-en_US-lessac-medium")
for text in ["What is photosynthesis?", "Hello Stark, how are you?", "Tell me a joke.", "Yes.",
             "Can you explain how Dijkstra's algorithm works?"]:
    a = en.generate(text, sid=0, speed=1.0)
    samples.append(("en (sentez)", resample16k(np.asarray(a.samples, dtype=np.float32), a.sample_rate)))

for label, audio in samples:
    lang = t._pick_language(audio)
    text, _, conf = t._run_model(t.main, audio, lang, prompt=None)
    print(f"{label:12} → {lang}  ({conf:5.2f})  {text}")
