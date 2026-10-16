"""Konuşmalardan kendiliğinden öğrenme (model eğitimi değil: kalıcı notlar).

Her turdan sonra arka planda, kullanıcının SÖYLEDİKLERİNDEN kalıcı bilgiler çıkarılır: kendisi hakkında bilgiler,
düzeltmeleri ve konuşma tercihleri. Modelin kendi tahminleri kaydedilmez; çıkarılan her bilgi kullanıcının
cümlesiyle kodla karşılaştırılır (kelimelerinin çoğu cümlede geçmeli). İnternette araştırılıp doğrulanan
cevaplar da kaynağı ve tarihiyle, son kullanma tarihli olarak saklanır.
"""
import re
from datetime import datetime, timedelta

from .database import KNOWLEDGE, PERSONAL, PREFERENCE, Repository, _stems

PROMPT = """Extract durable facts worth remembering long-term from the user's LATEST message to their assistant.
Kinds:
- personal: facts about the user or their life (family, studies, job, plans with dates, likes, possessions, routines)
- preference: how the user wants the assistant to behave or talk (length, tone, address, topics)
- knowledge: general facts or corrections the user states as true
Rules:
- Only what the user explicitly STATES in the latest message. The assistant's previous reply is context only.
- Skip questions, greetings, thanks, requests to search/do something, temporary moods ("canım sıkkın"),
  small talk, hypotheticals and anything uncertain.
- COPY the relevant part of his message word for word, in his language. Do not translate, rephrase or
  shorten names; you may only drop filler such as "hayır", "bana", "artık", "sen yanlış söyledin".
  Keep the subject (e.g. "Bornova İzmir'in bir ilçesi", "Daha kısa cevap ver").
  (Today is {today}.)
Reply with ONLY lines like "personal: ...", "preference: ...", "knowledge: ...", or the single word NONE."""

LINE = re.compile(r"^\s*[-*]?\s*(personal|preference|knowledge)\s*:\s*(.+)$", re.I)
KINDS = {"personal": PERSONAL, "preference": PREFERENCE, "knowledge": KNOWLEDGE}
# Çıkarılan bilginin kelime köklerinin en az %75'i kullanıcının cümlesinde geçmeli (model kopyalamalı, yazmamalı)
MIN_GROUNDING = 0.75
MAX_FACTS_PER_TURN = 3
# Öğrenmeye değmeyecek kısa/sosyal cümleler: model çağrısı hiç yapılmaz
TRIVIAL = re.compile(r"^\W*(merhaba|selam|teşekkür|sağ\s*ol|tamam|evet|hayır|olur|peki|iyi\s+geceler|"
                     r"görüşürüz|thanks|ok|okay|yes|no)\W*$", re.I)


def build_messages(user_text: str, previous_reply: str = "", today: str | None = None) -> list[dict]:
    today = today or datetime.now().strftime("%Y-%m-%d")
    context = f"Assistant's previous reply (context only): {previous_reply[:300]}\n\n" if previous_reply else ""
    return [{"role": "system", "content": PROMPT.format(today=today)},
            {"role": "user", "content": f"{context}LATEST message from User: {user_text}"}]


def worth_checking(user_text: str) -> bool:
    words = user_text.split()
    return len(words) >= 3 and not TRIVIAL.match(user_text)


def parse(reply: str) -> list[tuple[str, str]]:
    out = []
    for line in reply.splitlines():
        m = LINE.match(line)
        if m:
            fact = m.group(2).strip(" \"'")
            if len(fact) >= 5:
                out.append((KINDS[m.group(1).lower()], fact))
    return out[:MAX_FACTS_PER_TURN]


def grounded(fact: str, user_text: str) -> bool:
    """Modelin uydurduğu bilgiyi eler: bilginin kelimeleri kullanıcının cümlesinden gelmeli."""
    f, u = _stems(fact), _stems(user_text)
    return bool(f) and len(f & u) / len(f) >= MIN_GROUNDING


_FILLER = re.compile(r"^(?:hayır|yok|yanlış|bak|şimdi|bana|artık)[\s,.!]+|"
                     r"[\s,.!]*(?:sen\s+yanlış\s+(?:söyledin|biliyorsun)|yanlış\s+biliyorsun|unutma)[\s.!]*$", re.I)
# "Yarın sınavım var" bir hafta sonra yanlış olur: söylendiği gün yanına yazılır
RELATIVE = re.compile(r"\b(yarın|bugün|dün|bu\s+(?:akşam|sabah|hafta|ay)|haftaya|gelecek\s+(?:hafta|ay)|"
                      r"önümüzdeki|geçen\s+(?:hafta|ay)|tomorrow|today|yesterday|next\s+week)\b", re.I)


def clean(fact: str) -> str:
    previous = None
    while previous != fact:
        previous, fact = fact, _FILLER.sub("", fact).strip()
    fact = fact.rstrip(" ,")
    return fact[:1].upper() + fact[1:] if fact else fact


def store(repo: Repository, facts: list[tuple[str, str]], user_text: str) -> list[str]:
    """Doğrulanan ve yeni olan bilgileri kaydeder; kaydedilenleri döner."""
    saved = []
    for kind, fact in facts:
        fact = clean(fact)
        if len(fact) < 5 or not grounded(fact, user_text) or repo.is_duplicate(fact):
            continue
        if RELATIVE.search(fact):
            fact += f" (söylendiği gün: {datetime.now():%d.%m.%Y})"
        repo.add_memory(fact, kind, source="auto")
        saved.append(fact)
    return saved


def remember_research(repo: Repository, question: str, answer: str, sites: list[str], news: bool) -> bool:
    """Doğrulanmış arama cevabını kaynağıyla saklar. Haberler 7 gün, diğerleri 90 gün geçerli."""
    short = " ".join(re.split(r"(?<=[.!?])\s+", answer.strip())[:2])[:300]
    content = f"{question.strip()} — {short} (kaynak: {', '.join(sites[:2])}; {datetime.now():%d.%m.%Y})"
    if repo.is_duplicate(content, threshold=0.9):
        return False
    expires = (datetime.now() + timedelta(days=7 if news else 90)).isoformat(timespec="seconds")
    repo.add_memory(content, KNOWLEDGE, source="web", expires_at=expires)
    return True
