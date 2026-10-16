"""Whisper güven ölçüleri: doğru ve anlamsız transkriptlerde avg_logprob değerlerini karşılaştırır."""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from stark.audio.transcription import _add_cuda_dll_paths  # noqa: E402

_add_cuda_dll_paths()
from faster_whisper import WhisperModel  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
rec = np.load(Path(tempfile.gettempdir()) / "stark_wake_test.npy")
parts = [(9.6, 11.8), (18.8, 20.6), (25.1, 27.1), (32.4, 33.6), (37.7, 38.9), (45.0, 46.9), (46.8, 48.2),
         (16.5, 17.2), (2.0, 4.0), (55.0, 57.0)]  # son üçü: kısa/belirsiz ses ve sessizlik
m = WhisperModel("medium", device="cuda", compute_type="int8_float16")
for prompt in ("Stark.", "Kullanıcı ile Stark arasında Türkçe bir sohbet. Stark."):
    print(f"\nprompt: {prompt}")
    for a, b in parts:
        segs, _ = m.transcribe(rec[int(a * 16000):int(b * 16000)], language="tr", beam_size=5,
                               without_timestamps=True, condition_on_previous_text=False, initial_prompt=prompt)
        segs = list(segs)
        text = " ".join(s.text.strip() for s in segs)
        lp = min((s.avg_logprob for s in segs), default=0)
        ns = max((s.no_speech_prob for s in segs), default=1)
        print(f"  {a:5.1f} logprob={lp:6.2f} no_speech={ns:.2f}  {text}")
