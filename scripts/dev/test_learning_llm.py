"""Otomatik öğrenme: model gerçek cümlelerden ne çıkarıyor, doğrulama neyi eliyor?"""
import sys
import time

from stark.ai.ollama_client import OllamaClient
from stark.config import Settings
from stark.memory import learner

sys.stdout.reconfigure(encoding="utf-8")
llm = OllamaClient(Settings.load())
CASES = [
    ("Bu dönem bilgisayar mühendisliği ikinci sınıftayım, yarın veri yapıları sınavım var.", ""),
    ("Bana artık daha kısa cevap ver, uzun konuşma.", "Fotosentez bitkilerin ... (uzun açıklama)"),
    ("Hayır, Bornova İzmir'in bir ilçesi, sen yanlış söyledin.", "Bornova, Manisa'nın bir ilçesidir."),
    ("Kız kardeşimin adı Elif, o da lisede okuyor.", ""),
    ("Fotosentez nedir?", ""),
    ("Canım çok sıkkın bugün.", ""),
    ("Fenerbahçe'nin son maçı kaç kaç bitti?", ""),
    ("Sabahları kahvemi şekersiz içerim, her gün yedide kalkarım.", ""),
]
for text, prev in CASES:
    t = time.monotonic()
    reply = llm.complete(learner.build_messages(text, prev), num_predict=90, timeout=30)
    facts = learner.parse(reply)
    kept = [f for k, f in facts if learner.grounded(f, text)]
    dropped = [f for k, f in facts if not learner.grounded(f, text)]
    print(f"{time.monotonic() - t:4.1f}s  {text}\n      kayıt: {[(k, f) for k, f in facts if f in kept]}"
          + (f"\n      ELENDİ: {dropped}" if dropped else ""))
