"""LLM GPU'dayken Whisper modellerini CUDA'da karşılaştırır: kayıttaki tüm konuşma bölümleri, süre, VRAM."""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from stark.audio.transcription import _add_cuda_dll_paths  # noqa: E402

_add_cuda_dll_paths()
from faster_whisper import WhisperModel  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
rec = np.load(Path(tempfile.gettempdir()) / "stark_wake_test.npy")
# analyze_wake_whisper.py'deki VAD bölümleri (sn)
parts = [(9.6, 11.8), (18.8, 20.6), (25.1, 27.1), (32.4, 33.6), (37.7, 38.9), (45.0, 46.9), (46.8, 48.2)]
segs = [rec[int(a * 16000):int(b * 16000)] for a, b in parts]


def vram():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return int(out.strip())


def llm_on_gpu():
    m = httpx.get("http://127.0.0.1:11434/api/ps").json()["models"]
    return [(x["name"], round(x["size_vram"] / x["size"] * 100)) for x in m]


models = sys.argv[1:] or ["small", "medium", "large-v3-turbo"]
for size in models:
    httpx.post("http://127.0.0.1:11434/api/generate", json={"model": "gemma3:4b", "keep_alive": 0}, timeout=60)
    time.sleep(1)
    m = WhisperModel(size, device="cuda", compute_type="int8_float16")
    list(m.transcribe(segs[0], language="tr")[0])  # ısınma
    # Gerçek kullanımdaki sıra: Whisper yüklü, sonra LLM yüklenir
    httpx.post("http://127.0.0.1:11434/api/generate", timeout=300,
               json={"model": "gemma3:4b", "keep_alive": "5m", "options": {"num_gpu": 99, "num_ctx": 4096}})
    r = httpx.post("http://127.0.0.1:11434/api/chat", timeout=300, json={
        "model": "gemma3:4b", "stream": False, "options": {"num_gpu": 99, "num_ctx": 4096, "num_predict": 60},
        "messages": [{"role": "user", "content": "Fotosentezi iki cümleyle anlat."}]}).json()
    tps = r["eval_count"] / (r["eval_duration"] / 1e9)
    times, texts = [], []
    for s in segs:
        t = time.monotonic()
        out, _ = m.transcribe(s, language="tr", beam_size=3, without_timestamps=True,
                              condition_on_previous_text=False, initial_prompt="Stark.")
        texts.append(" ".join(o.text.strip() for o in out))
        times.append(time.monotonic() - t)
    print(f"\n== {size}: ort {np.mean(times):.2f} sn, en çok {max(times):.2f} sn | VRAM {vram()} MiB | "
          f"LLM GPU % {llm_on_gpu()} | LLM {tps:.0f} tok/sn")
    for t in texts:
        print("   ", t)
    del m
