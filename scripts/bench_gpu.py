"""Modelin tüm katmanlarını GPU'ya zorlayınca hız ve bellek ölçümü."""
import sys
import time

import httpx

model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:4b-instruct"
for ctx in (4096, 2048):
    body = {"model": model, "stream": False, "keep_alive": "5m",
            "options": {"num_ctx": ctx, "num_gpu": 99, "num_predict": 150},
            "messages": [{"role": "user", "content": "Fotosentezi iki cümleyle anlat."}]}
    for _ in range(2):
        t = time.monotonic()
        d = httpx.post("http://127.0.0.1:11434/api/chat", json=body, timeout=300).json()
        if "error" in d:
            print(ctx, "HATA", d["error"])
            break
        print(ctx, f"{d['eval_count'] / (d['eval_duration'] / 1e9):.0f} tok/sn, toplam {time.monotonic() - t:.1f} sn")
    for m in httpx.get("http://127.0.0.1:11434/api/ps").json().get("models", []):
        print("  GPU", round(m["size_vram"] / 1e9, 2), "/", round(m["size"] / 1e9, 2), "GB")
    httpx.post("http://127.0.0.1:11434/api/generate", json={"model": model, "keep_alive": 0}, timeout=60)
