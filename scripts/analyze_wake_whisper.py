"""İki aşamalı uyandırma denemesi: Silero VAD → kısa bölüm → Whisper (tiny/base) → 'stark' eşleşmesi."""
import os
import re
import tempfile
import time
from pathlib import Path

import numpy as np
import sherpa_onnx
from faster_whisper import WhisperModel

M = Path.home() / ".stark/models"
rec = np.load(Path(tempfile.gettempdir()) / "stark_wake_test.npy")

cfg = sherpa_onnx.VadModelConfig()
cfg.silero_vad.model = str(M / "silero_vad.onnx")
cfg.silero_vad.threshold = 0.5
cfg.silero_vad.min_silence_duration = 0.25
cfg.silero_vad.min_speech_duration = 0.15
cfg.silero_vad.max_speech_duration = 8
cfg.sample_rate = 16000
vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=30)

segments = []
for i in range(0, len(rec), 512):
    vad.accept_waveform(rec[i:i + 512])
    while not vad.empty():
        segments.append((vad.front.start / 16000, np.array(vad.front.samples, dtype=np.float32)))
        vad.pop()
vad.flush()
while not vad.empty():
    segments.append((vad.front.start / 16000, np.array(vad.front.samples, dtype=np.float32)))
    vad.pop()

WAKE = re.compile(r"\b(i?s[dt]?[aâe]r[kcgq]|stark|start|sark|şark|istark)\b", re.I)
for size in ("tiny", "base", "small"):
    m = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=4)
    m.transcribe(np.zeros(16000, dtype=np.float32), language="tr")  # ısınma
    hits, times = [], []
    for start, x in segments:
        head = x[: int(1.6 * 16000)]  # uyandırma kelimesi baştadır
        t = time.monotonic()
        out, _ = m.transcribe(head, language="tr", beam_size=1, without_timestamps=True,
                              condition_on_previous_text=False, initial_prompt="Stark.")
        text = " ".join(o.text.strip() for o in out)
        times.append(time.monotonic() - t)
        if WAKE.search(text):
            hits.append(f"{start:.1f}")
        print(f"  {size:5} {start:5.1f} sn ({len(x) / 16000:.1f} sn): {text}")
    print(f"{size}: {len(hits)} uyanma {hits} | bölüm başı ort. {np.mean(times):.2f} sn, en çok {max(times):.2f} sn\n")
