"""Model hafızadaki bilgiyi kullanıyor mu, hafızada olmayanı uyduruyor mu? (geçici veritabanı)"""
import sys

import httpx

from stark.ai.conversation import Conversation
from stark.config import Settings
from stark.memory.database import Repository

sys.stdout.reconfigure(encoding="utf-8")
s = Settings.load()
repo = Repository(":memory:")
repo.add_memory("En sevdiğim renk mavi")
repo.add_memory("Kardeşimin adı Elif")
repo.add_memory("Bilgisayar mühendisliği okuyorum")
for q in ["En sevdiğim renk ne?", "Kardeşimin adı neydi?", "Ben ne okuyorum?",
          "Doğum günüm ne zaman?", "Annemin adını biliyor musun?", "Bana bir bölüm önerisi yapar mısın?"]:
    body = {"model": s.llm_model, "stream": False, "think": False,
            "messages": Conversation(s, repo).build(q, "tr"),
            "options": {"num_gpu": 99, "num_ctx": 4096, "temperature": s.llm_temperature}}
    a = httpx.post(f"{s.ollama_url}/api/chat", json=body, timeout=120).json()["message"]["content"]
    print(f"S: {q}\nC: {a.strip()}\n")
