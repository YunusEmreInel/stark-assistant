"""Arama turunun içini gösterir: kaynaklar, modelin ham cevabı, doğrulamada reddedilen sayılar."""
import sys
import tempfile
import threading
from pathlib import Path

from stark.config import Settings
from stark.core import engine as engine_mod
from stark.tools import router, web

sys.stdout.reconfigure(encoding="utf-8")
engine_mod.DB_FILE = Path(tempfile.mkdtemp()) / "debug.db"


class Silent:
    def __getattr__(self, name):
        return lambda *a, **k: None


s = Settings.load()
s.internet_enabled = True
e = engine_mod.Engine(s, Silent())
real_chat = e.llm.chat
real_check = web.unsupported_numbers
for text in sys.argv[1:]:
    kind = "news" if router.NEWS.search(text) else "search"
    q = router.news_keywords(text) if kind == "news" else router.keywords(text)
    sources, provider, kind = e._gather(text, "tr", router.Route(kind, q))
    print(f"\n### {text}  [{kind} | {provider} | sorgu: {q}]")
    for i, src in enumerate(sources, 1):
        print(f"  [{i}] {src.date} {src.site}: {src.title[:80]} | metin {len(src.text)}")
    got, finished = {}, threading.Event()

    def chat(sess, msgs, piece, done, err, **kw):
        real_chat(sess, msgs, piece, lambda full: (got.__setitem__("raw", full), done(full)), err, **kw)

    def check(answer, srcs):
        got["bad"] = real_check(answer, srcs)
        return got["bad"]

    e.llm.chat, web.unsupported_numbers = chat, check
    e._finish_tool_turn = lambda session, t, reply, links="": (got.__setitem__("reply", reply), finished.set())
    e._answer_from_sources(e.controller.session, text, "tr", sources, provider, kind)
    finished.wait(120)
    print("  HAM CEVAP:", got.get("raw", "").strip())
    print("  REDDEDİLEN:", got.get("bad"))
