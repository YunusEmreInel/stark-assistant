"""Kaydedilmiş uyandırma testini farklı eşik/boost/varyantlarla yeniden çalıştırır (çevrimdışı ayar)."""
import os
import tempfile
from pathlib import Path

import numpy as np
import sherpa_onnx

D = Path.home() / ".stark/models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"
audio = np.load(Path(tempfile.gettempdir()) / "stark_wake_test.npy")

# Kayıttaki konuşma bölümleri (basit enerji tabanlı) — referans için
frame = 1600
rms = np.sqrt((audio[: len(audio) // frame * frame].reshape(-1, frame) ** 2).mean(1))
loud = np.where(rms > max(0.01, rms.mean() * 3))[0]
segs = []
for i in loud:
    if segs and i - segs[-1][1] <= 3:
        segs[-1][1] = i
    else:
        segs.append([i, i])
print("konuşma bölümleri (sn):", [f"{a / 10:.1f}-{(b + 1) / 10:.1f}" for a, b in segs])

VARIANT_SETS = {
    "temel": ["▁ST AR K"],
    "geniş": ["▁ST AR K", "▁ST AR CK", "▁ST AR ▁K", "▁ST OR K", "▁ST IR K", "▁ST ER K", "▁ST AR T"],
}


def run(variants, thr, boost):
    kw = Path(tempfile.gettempdir()) / "stark_kw_an.txt"
    kw.write_text("\n".join(f"{v} :{boost} #{thr} @STARK" for v in variants) + "\n", encoding="utf-8")
    kws = sherpa_onnx.KeywordSpotter(
        tokens=str(D / "tokens.txt"),
        encoder=str(D / "encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx"),
        decoder=str(D / "decoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx"),
        joiner=str(D / "joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx"),
        keywords_file=str(kw), num_threads=2, keywords_score=boost, keywords_threshold=thr, max_active_paths=4)
    s = kws.create_stream()
    hits = []
    for i in range(0, len(audio), frame):
        s.accept_waveform(16000, audio[i:i + frame])
        while kws.is_ready(s):
            kws.decode_stream(s)
            if kws.get_result(s):
                hits.append(round(i / 16000, 1))
                kws.reset_stream(s)
    return hits


for name, variants in VARIANT_SETS.items():
    for thr in (0.25, 0.1, 0.05, 0.02):
        for boost in (1.0, 3.0, 6.0):
            h = run(variants, thr, boost)
            print(f"{name:6} eşik={thr:<5} boost={boost:<4} → {len(h):2} algılama {h}")

# Whisper bu bölümlerde ne duyuyor?
from faster_whisper import WhisperModel  # noqa: E402

m = WhisperModel("small", device="cpu", compute_type="int8")
for a, b in segs:
    x = audio[max(0, (a - 3) * frame):(b + 4) * frame]
    out, _ = m.transcribe(x, language="tr", beam_size=1)
    print(f"{a / 10:5.1f} sn whisper(tr): {' '.join(o.text.strip() for o in out)}")
