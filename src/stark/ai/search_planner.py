"""Arama kararı: "bu soru internet gerektiriyor mu, gerekiyorsa ne aranmalı?"

Kelime listeleri her soru kalıbını yakalayamıyor ("Dün Bornova'da bir olay oldu, bulur musun?") ve
"internetten araştır" gibi takip cümlelerinde önceki soruyu bilmiyor. Bu yüzden karar, önceki konuşma da
verilerek kısa ve deterministik bir dil modeli çağrısıyla verilir (~0.3 sn).
"""
import re

PROMPT = """You decide whether a voice assistant must search the web before answering the user's LATEST message.
Today is {today}. The assistant's own knowledge is old and it has no live data.

Search is needed for: news and events (accidents, fires, explosions, crimes, earthquakes, politics), anything
that happened recently or on a specific recent day ("dün", "bugün", "geçen hafta", "yesterday"), sports results
and fixtures, prices, schedules, releases, current facts about people, companies or places, and whenever the user
asks to search, look up, find or research something ("ara", "araştır", "bul", "bak", "internetten").
No search for: chit-chat, greetings, opinions, advice, general timeless knowledge, math, coding, definitions,
translations, or questions about the user themselves.
If the message mentions a name, place or term you don't recognize, choose a search (look it up) instead of NONE.

If the latest message only says to search ("internetten araştır", "evet ara", "bak bakalım") or refers back to
something ("bunu", "onu"), build the query from the previous messages.

Reply with ONLY one line:
- NONE  (no search needed), or
- NEWS: <query>  (recent events/news/sports), or
- WEB: <query>   (other web lookups)
The query: 2-6 keywords in the user's language with names and places, no dates, no filler words."""

LINE = re.compile(r"^\s*(NONE|NEWS|WEB)\s*:?\s*(.*)$", re.I)


FACT_CHECK = """
Fact-check mode is ON: the assistant's own knowledge is unreliable for precise facts (it said Türkiye has 3 geographic
regions; it has 7). Also choose WEB for questions whose answer is a specific fact: how many, which ones, list of,
who, when, where exactly, first/biggest/highest, dates, populations, distances, records, names of members/parts.
Still NONE for explaining concepts ("X nedir", "nasıl çalışır", "neden"), advice, opinions, chit-chat, jokes,
math, coding and translation."""


def build_messages(text: str, previous: list[tuple[str, str]], today: str, location: str = "",
                   fact_check: bool = False) -> list[dict]:
    context = "\n".join(f"User: {u}\nAssistant: {a[:200]}" for u, a in previous[-2:]) or "(none)"
    system = PROMPT.format(today=today) + (FACT_CHECK if fact_check else "")
    if location:
        system += ("\n" + location + " For local events include the district AND the province in the query "
                   "(e.g. 'İzmir Bornova').")
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"Previous messages:\n{context}\n\nLATEST message from User: {text}"}]


def parse(reply: str) -> tuple[str, str] | None:
    """("news"|"search", sorgu) ya da arama gerekmiyorsa None."""
    for line in reply.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        kind, query = m.group(1).upper(), m.group(2).strip(" \"'`.")
        if kind == "NONE" or not query:
            return None
        return ("news" if kind == "NEWS" else "search"), query
    return None
