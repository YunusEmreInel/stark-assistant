"""Stark için gerekli yerel ses modellerini %USERPROFILE%\\.stark\\models altına indirir."""
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from stark.config import MODELS_DIR  # noqa: E402  (%USERPROFILE%\.stark\models)
BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"

DOWNLOADS = [
    # (url, arşivden sonra beklenen yol)
    (f"{BASE}/asr-models/silero_vad.onnx", "silero_vad.onnx"),
    (f"{BASE}/kws-models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2",
     "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"),
    (f"{BASE}/tts-models/vits-piper-tr_TR-dfki-medium.tar.bz2", "vits-piper-tr_TR-dfki-medium"),
    (f"{BASE}/tts-models/vits-piper-tr_TR-fahrettin-medium.tar.bz2", "vits-piper-tr_TR-fahrettin-medium"),
    (f"{BASE}/tts-models/vits-piper-tr_TR-fettah-medium.tar.bz2", "vits-piper-tr_TR-fettah-medium"),
    (f"{BASE}/tts-models/vits-piper-en_US-lessac-medium.tar.bz2", "vits-piper-en_US-lessac-medium"),
]


def _progress(name):
    def hook(blocks, block_size, total):
        if total > 0:
            pct = min(100, blocks * block_size * 100 // total)
            sys.stdout.write(f"\r  {name}: %{pct}")
            sys.stdout.flush()
    return hook


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for url, target in DOWNLOADS:
        if (MODELS_DIR / target).exists():
            print(f"✓ {target} (zaten var)")
            continue
        file_name = url.rsplit("/", 1)[1]
        dest = MODELS_DIR / file_name
        print(f"↓ {file_name}")
        urllib.request.urlretrieve(url, dest, _progress(file_name))
        print()
        if file_name.endswith(".tar.bz2"):
            with tarfile.open(dest, "r:bz2") as tar:
                tar.extractall(MODELS_DIR, filter="data")
            dest.unlink()
    print("Whisper modeli ilk kullanımda faster-whisper tarafından indirilir.")
    print(f"Modeller: {MODELS_DIR}")


if __name__ == "__main__":
    main()
