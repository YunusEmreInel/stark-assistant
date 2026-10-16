"""KWS kurulumunu modelin kendi örnek wav'ları ile doğrular."""
import os
import tempfile
import wave
from pathlib import Path

import numpy as np
import sherpa_onnx

D = Path.home() / ".stark/models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"


def load(p):
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768, w.getframerate()


def spot(kw_text, x, sr, int8=True, **kw):
    f = Path(tempfile.gettempdir()) / "kws_sanity.txt"
    f.write_text(kw_text, encoding="utf-8")
    sfx = ".int8.onnx" if int8 else ".onnx"
    k = sherpa_onnx.KeywordSpotter(
        tokens=str(D / "tokens.txt"),
        encoder=str(D / f"encoder-epoch-12-avg-2-chunk-16-left-64{sfx}"),
        decoder=str(D / f"decoder-epoch-12-avg-2-chunk-16-left-64{sfx}"),
        joiner=str(D / f"joiner-epoch-12-avg-2-chunk-16-left-64{sfx}"),
        keywords_file=str(f), num_threads=2, **kw)
    s = k.create_stream()
    s.accept_waveform(sr, x)
    s.accept_waveform(sr, np.zeros(int(sr * 0.66), dtype=np.float32))
    s.input_finished()
    hits = []
    while k.is_ready(s):
        k.decode_stream(s)
        r = k.get_result(s)
        if r:
            hits.append(r)
            k.reset_stream(s)
    return hits


x, sr = load(D / "test_wavs/0.wav")
print("örnek wav, kendi anahtar dosyası:", spot((D / "test_wavs/test_keywords.txt").read_text(encoding="utf-8"), x, sr))
print("örnek wav, @etiketli:", spot("▁ L IGHT ▁UP @LIGHT_UP\n", x, sr))

rec = np.load(Path(tempfile.gettempdir()) / "stark_wake_test.npy")
seg = rec[int(5.8 * 16000):int(7.0 * 16000)]
for int8 in (True, False):
    for thr in (0.25, 0.1):
        print(f"kayıt 6.2 sn int8={int8} eşik={thr}:",
              spot("▁ST AR K @STARK\n", seg, 16000, int8=int8, keywords_threshold=thr, keywords_score=2.0),
              spot("▁ST AR K @STARK\n", rec, 16000, int8=int8, keywords_threshold=thr, keywords_score=2.0))
