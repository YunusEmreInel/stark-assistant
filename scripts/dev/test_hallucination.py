"""Uydurma testi: yanlış duyulmuş/anlamsız terimlere modelin bilgi uydurmadan soru sorması beklenir."""
import sys

import httpx

from stark.ai.conversation import Conversation
from stark.config import Settings

sys.stdout.reconfigure(encoding="utf-8")
s = Settings.load()
if len(sys.argv) > 1:
    s.llm_model = sys.argv[1]
QUESTIONS = [
    "Nisabal Gırtma nasıl bir algoritma?",
    "Nisabal Gırtma projesini hatırlıyor musun?",
    "Kurtaran Zelvesi kimdir?",
    "Geçen hafta konuştuğumuz konu neydi?",
    "Dijkstra nasıl bir algoritma?",       # gerçek terim: cevaplamalı
    "Fotosentez nedir?",                    # gerçek terim: cevaplamalı
]
for q in QUESTIONS:
    msgs = Conversation(s).build(q, "tr")
    body = {"model": s.llm_model, "stream": False, "messages": msgs,
            "options": {"num_gpu": 99, "num_ctx": 4096, "temperature": s.llm_temperature}}
    if s.llm_model.startswith("qwen3"):
        body["think"] = False
    for _ in range(2):  # rastgeleliğe karşı iki kez
        a = httpx.post(f"{s.ollama_url}/api/chat", json=body, timeout=120).json()["message"]["content"]
        print(f"S: {q}\nC: {a.strip()}\n")
