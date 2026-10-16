"""Ollama modellerini Türkçe sorularla karşılaştırır: ilk token süresi, hız, cevap."""
import json
import sys
import time

import httpx

MODELS = sys.argv[1:] or ["qwen3:4b-instruct", "qwen3:4b", "gemma3:4b", "qwen3:1.7b"]
SYSTEM = ("Sen Stark'sın; kullanıcının kişisel asistanısın. Cevapların sesli okunacak: kısa, doğal, "
          "konuşma diliyle cevap ver; liste, Markdown ve emoji kullanma.")
QUESTIONS = [
    "Fotosentez nedir, kısaca anlatır mısın?",
    "Bugün canım sıkkın, ne yapabilirim?",
    "Python'da bir listeyi ters çevirmenin en kolay yolu ne?",
    "Ankara'dan İstanbul'a arabayla gitmek yaklaşık kaç saat sürer?",
]


def ask(model, question):
    body = {"model": model, "stream": True, "keep_alive": "5m", "think": False,
            "options": {"num_ctx": 4096, "num_predict": 200},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]}
    t0 = time.monotonic()
    ttft, text, stats = None, "", {}
    with httpx.stream("POST", "http://127.0.0.1:11434/api/chat", json=body, timeout=120) as r:
        if r.status_code != 200:
            body.pop("think")  # model desteklemiyorsa
            return ask_plain(model, body)
        for line in r.iter_lines():
            data = json.loads(line)
            piece = data.get("message", {}).get("content", "")
            if piece and ttft is None:
                ttft = time.monotonic() - t0
            text += piece
            if data.get("done"):
                stats = data
    tps = stats.get("eval_count", 0) / max(stats.get("eval_duration", 1) / 1e9, 1e-6)
    return ttft or 0, time.monotonic() - t0, tps, text.strip()


def ask_plain(model, body):
    t0 = time.monotonic()
    r = httpx.post("http://127.0.0.1:11434/api/chat", json={**body, "stream": False}, timeout=120)
    d = r.json()
    tps = d.get("eval_count", 0) / max(d.get("eval_duration", 1) / 1e9, 1e-6)
    return 0, time.monotonic() - t0, tps, d.get("message", {}).get("content", "").strip()


for model in MODELS:
    print(f"\n===== {model} =====")
    t0 = time.monotonic()
    httpx.post("http://127.0.0.1:11434/api/generate", json={"model": model, "keep_alive": "5m"}, timeout=300)
    print(f"yükleme: {time.monotonic() - t0:.1f} sn")
    for q in QUESTIONS:
        ttft, total, tps, text = ask(model, q)
        print(f"[ilk token {ttft:.2f} sn | toplam {total:.1f} sn | {tps:.0f} tok/sn] {q}\n  → {text[:300]}")
    ps = httpx.get("http://127.0.0.1:11434/api/ps").json()
    for m in ps.get("models", []):
        if m["name"] == model:
            print(f"bellek: toplam {m['size']/1e9:.2f} GB, GPU'da {m['size_vram']/1e9:.2f} GB")
    httpx.post("http://127.0.0.1:11434/api/generate", json={"model": model, "keep_alive": 0}, timeout=60)
