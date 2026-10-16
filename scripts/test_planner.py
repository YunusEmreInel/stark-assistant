"""Arama kararı doğruluğu ve hızı (bilgi doğrulama modu açık/kapalı)."""
import sys
import time
from datetime import date

from stark.ai import search_planner
from stark.ai.ollama_client import OllamaClient
from stark.config import Settings

sys.stdout.reconfigure(encoding="utf-8")
s = Settings.load()
llm = OllamaClient(s)
PREV_EVENT = [("Dün İzmir Bornova'da bir evde tüp patladı mı?", "Bu konuda bilgiye erişemiyorum patron.")]
CASES = [  # (mesaj, önceki, arama bekleniyor mu)
    ("Dün İzmir Bornova'da bir olay oldu. Onu benim için bulur musun?", [], True),
    ("İnternetten araştıracaksın işte bu söyleyeceğimi.", PREV_EVENT, True),
    ("Fenerbahçe'nin son maçı kaç kaç bitti?", [], True),
    ("Türkiye'nin kaç coğrafi bölgesi var?", [], True),
    ("Bana Türkiye'nin coğrafi bölgelerini anlatır mısın?", [], True),
    ("Türkiye'nin en yüksek dağı hangisi?", [], True),
    ("İstanbul'un fethi hangi yıl oldu?", [], True),
    ("Güneş sisteminde kaç gezegen var?", [], True),
    ("Fotosentez nedir?", [], False),
    ("Yapay zeka nasıl çalışır?", [], False),
    ("Bana bir fıkra anlat.", [], False),
    ("Python'da liste nasıl ters çevrilir?", [], False),
    ("Canım sıkılıyor.", [], False),
    ("Sınava nasıl daha iyi çalışabilirim?", [], False),
]
for fc in (False, True):
    ok, times = 0, []
    print(f"\n=== bilgi doğrulama {'AÇIK' if fc else 'KAPALI'} ===")
    for text, prev, expected in CASES:
        t = time.monotonic()
        reply = llm.complete(search_planner.build_messages(text, prev, date.today().isoformat(), fact_check=fc),
                             num_predict=24)
        times.append(time.monotonic() - t)
        got = search_planner.parse(reply) is not None
        good = got == expected
        ok += good
        print(f"{'✓' if good else '✗'} {times[-1]:.2f}s  {text[:52]:52} → {reply}")
    print(f"{ok}/{len(CASES)} doğru | ortalama {sum(times[1:]) / (len(times) - 1):.2f} sn")
