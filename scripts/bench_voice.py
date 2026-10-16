"""Piper TTS (Türkçe/İngilizce) hızını ölçer, sesi çalar; üretilen sesle Whisper ASR hızını ölçer."""
import os
import time
from pathlib import Path

import numpy as np
import sherpa_onnx

MODELS = Path.home() / ".stark" / "models"


def tts(name):
    d = MODELS / name
    onnx = next(d.glob("*.onnx"))
    cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
        vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=str(onnx), tokens=str(d / "tokens.txt"),
                                                   data_dir=str(d / "espeak-ng-data")),
        num_threads=4))
    return sherpa_onnx.OfflineTts(cfg)


def resample16k(x, sr):
    n = int(len(x) * 16000 / sr)
    return np.interp(np.linspace(0, len(x), n, endpoint=False), np.arange(len(x)), x).astype(np.float32)


def main():
    import sounddevice as sd
    from faster_whisper import WhisperModel

    tests = [("vits-piper-tr_TR-dfki-medium", "Merhaba, ben Stark. Sesim bu şekilde duyulacak. Bugün sana nasıl yardımcı olabilirim?", "tr"),
             ("vits-piper-en_US-lessac-medium", "Hello, I am Stark. This is my English voice.", "en")]
    asr = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
    for model, text, lang in tests:
        engine = tts(model)
        t = time.monotonic()
        audio = engine.generate(text, sid=0, speed=1.0)
        gen = time.monotonic() - t
        samples = np.array(audio.samples, dtype=np.float32)
        dur = len(samples) / audio.sample_rate
        print(f"[{lang}] TTS üretim {gen:.2f} sn, ses süresi {dur:.1f} sn (RTF {gen / dur:.2f})")
        sd.play(samples, audio.sample_rate)
        sd.wait()
        t = time.monotonic()
        segs, info = asr.transcribe(resample16k(samples, audio.sample_rate), beam_size=1)
        print(f"  ASR: {time.monotonic() - t:.2f} sn, dil={info.language} → {' '.join(s.text.strip() for s in segs)}")


if __name__ == "__main__":
    main()
