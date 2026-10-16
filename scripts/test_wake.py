"""Canlı "Stark" uyandırma testi. Kullanım: python scripts/test_wake.py [saniye] [eşik] [boost]

Mikrofonu dinler, her algılamada zaman damgası yazar. Sonunda toplam algılama sayısını verir.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import sherpa_onnx
import sounddevice as sd

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 60
THRESHOLD = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
BOOST = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
D = Path.home() / ".stark/models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"

# Türkçe "Stark" telaffuzuna yakın İngilizce token varyantları, hepsi aynı etiket
variants = ["▁ST AR K", "▁ST AR CK", "▁ST AR ▁K", "▁ST OR K", "▁ST IR K"]
kw_file = Path(tempfile.gettempdir()) / "stark_keywords.txt"
kw_file.write_text("\n".join(f"{v} :{BOOST} #{THRESHOLD} @STARK" for v in variants) + "\n", encoding="utf-8")

kws = sherpa_onnx.KeywordSpotter(
    tokens=str(D / "tokens.txt"),
    encoder=str(D / "encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx"),
    decoder=str(D / "decoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx"),
    joiner=str(D / "joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx"),
    keywords_file=str(kw_file), num_threads=1, provider="cpu",
    keywords_score=BOOST, keywords_threshold=THRESHOLD, max_active_paths=4)
stream = kws.create_stream()

dev = sd.query_devices(kind="input")
print(f"Mikrofon: {dev['name']} | süre {DURATION:.0f} sn | eşik {THRESHOLD} | boost {BOOST}", flush=True)
print("BAŞLA — 'Stark' de, her seferinde 3-4 saniye ara ver.", flush=True)

hits = []
t0 = time.monotonic()
peak = 0.0
recorded = []  # STARK_RECORD=1 ise ayar denemeleri için geçici kayıt
with sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=1600) as mic:
    while time.monotonic() - t0 < DURATION:
        block, _ = mic.read(1600)
        x = block[:, 0]
        if os.environ.get("STARK_RECORD"):
            recorded.append(x.copy())
        peak = max(peak, float(np.abs(x).max()))
        stream.accept_waveform(16000, x)
        while kws.is_ready(stream):
            kws.decode_stream(stream)
            if kws.get_result(stream):
                t = time.monotonic() - t0
                hits.append(t)
                print(f"  ✓ STARK algılandı  {t:5.1f} sn", flush=True)
                kws.reset_stream(stream)

if recorded:
    out = Path(tempfile.gettempdir()) / "stark_wake_test.npy"
    np.save(out, np.concatenate(recorded))
    print(f"Kayıt: {out}", flush=True)
print(f"BİTTİ — toplam algılama: {len(hits)} | en yüksek ses seviyesi: {peak:.3f}", flush=True)
