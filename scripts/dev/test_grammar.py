"""Türkçe ben/sen bakış açısı ve doğallık testi. Kullanım: python scripts/test_grammar.py [model]"""
import sys

import httpx

from stark.ai.conversation import Conversation
from stark.config import Settings

sys.stdout.reconfigure(encoding="utf-8")
s = Settings.load()
if len(sys.argv) > 1:
    s.llm_model = sys.argv[1]
QUESTIONS = ["Benimle konuşmaya hazır mısın?", "Beni dinliyor musun?", "Bana yardım eder misin?",
             "Seninle biraz sohbet edelim mi?", "Canım sıkılıyor.", "Kendini tanıtır mısın?"]
for q in QUESTIONS:
    body = {"model": s.llm_model, "stream": False, "messages": Conversation(s).build(q, "tr"),
            "options": {"num_gpu": 99, "num_ctx": 4096, "temperature": s.llm_temperature}}
    if s.llm_model.startswith("qwen3"):
        body["think"] = False
    a = httpx.post(f"{s.ollama_url}/api/chat", json=body, timeout=120).json()["message"]["content"]
    print(f"S: {q}\nC: {a.strip()}\n")
