"""Whisper ayarlarını ısınmış halde karşılaştırır (Piper ile üretilen Türkçe cümle üzerinde)."""
import os
import sys
import time

import numpy as np
from faster_whisper import WhisperModel

sys.path.insert(0, os.path.dirname(__file__))
from bench_voice import resample16k, tts  # noqa: E402  (bench_voice modül olarak içe aktarılınca test çalmaz)

text = "Yarın sabah saat dokuzda toplantım var, bana hatırlatır mısın?"
audio = tts("vits-piper-tr_TR-dfki-medium").generate(text, sid=0, speed=1.0)
pcm = resample16k(np.array(audio.samples, dtype=np.float32), audio.sample_rate)
print(f"ses {len(pcm) / 16000:.1f} sn | işlemci çekirdeği: {os.cpu_count()}")

configs = [(s, d, c, th) for s, d, c, th in [
    ("base", "cpu", "int8", 4), ("small", "cpu", "int8", 4), ("small", "cpu", "int8", 8),
    ("small", "cuda", "int8_float16", 0), ("medium", "cuda", "int8_float16", 0),
    ("large-v3-turbo", "cuda", "int8_float16", 0)]]
for size, dev, ct, th in configs:
    try:
        m = WhisperModel(size, device=dev, compute_type=ct, cpu_threads=th)
        for i in range(2):
            t = time.monotonic()
            segs, _ = m.transcribe(pcm, language="tr", beam_size=1, without_timestamps=True)
            out = " ".join(s.text.strip() for s in segs)
            if i:
                print(f"{size:15} {dev:4} {ct:13} thr={th}: {time.monotonic() - t:.2f} sn → {out}")
        del m
    except Exception as e:  # noqa: BLE001
        print(f"{size:15} {dev:4}: HATA {str(e)[:120]}")
