"""Sohbet bağlamı: sistem talimatı + sınırlı geçmiş. (Kalıcı hafıza sonraki aşamada eklenecek.)"""
import re
from datetime import datetime

from ..config import ADDRESS_RULE, SYSTEM_PROMPT, Settings
from ..memory.database import KNOWLEDGE, PERSONAL, PREFERENCE
from ..tools import places

LIVE_INFO = re.compile(
    r"hava (durumu|nasıl)|yağmur|sıcaklık|derece|dolar|euro|avro|sterlin|döviz|kur(u|lar)|altın|borsa|bitcoin|"
    r"haber|gündem|son dakika|maç|skor|puan durumu|seçim|fiyat|kaç (lira|tl)|"
    r"weather|forecast|exchange rate|stock|price|news|score", re.I)
LIVE_INFO_NOTE = (
    "This question needs live/current information. You have NO internet access and NO tool result. Do NOT "
    "invent numbers, prices, temperatures or events and do not claim you can go online. Just say briefly "
    "that you can't access this right now; optionally suggest where to check.")
STYLE_NOTE = (
    "Spoken reply: at most 2-3 short sentences unless detail is requested. No lists, numbering, Markdown or "
    "emoji. The message may be misheard: if it contains an unknown or meaningless word, don't invent, ask.")
# Konuşanı açıkça belirtmek, modelin "annem/ben" kelimelerini kendine mal etmesini azaltıyor
# (ölçüm: "Annemin adını biliyor musun?" → etiketsiz "Annemin adı Ayşe", etiketli "bilmiyorum").
SPEAKER = "User: "
LANG_HINT = {
    "tr": "Reply in natural, grammatical Turkish using the formal 'siz' forms, never 'sen'.",
    "en": "The user is speaking English: reply in English.",
}


class Conversation:
    """Bu oturumun bağlamı. repo verilirse turlar kalıcı geçmişe yazılır ve hafıza modele eklenir."""

    def __init__(self, settings: Settings, repo=None):
        self.s = settings
        self.repo = repo
        self.turns: list[tuple[str, str]] = []   # (kullanıcı, asistan)
        self._pending_user: str | None = None
        self._conversation_id: int | None = None  # ilk mesajda oluşturulur (boş sohbet kaydı olmasın)

    def _memory_block(self, user_text: str) -> str:
        """Yalnızca soruyla ilgili kayıtlar verilir: hepsi birden verilince küçük model bilgileri
        birbirine karıştırıyordu (ör. kardeşin adını annenin adı sandı)."""
        entries = self.repo.relevant_entries(user_text) if self.repo else []
        personal = [c for c, kind in entries if kind == PERSONAL]
        taught = [c for c, kind in entries if kind == KNOWLEDGE]
        block = ""
        prefs = [c for _, c, _ in self.repo.list_memories(PREFERENCE)][-10:] if self.repo else []
        if prefs:
            # Konuşma tercihleri her turda geçerli (ör. "daha kısa konuş")
            block += "\nThe user's standing preferences for how you behave (always follow):\n" + \
                     "\n".join(f"- {p}" for p in prefs)
        if taught:
            # kullanıcının sesle öğrettiği genel bilgiler: modelin kendi (eski) bilgisinden önce gelir
            block += ("\nFacts the user taught you (treat them as true; they override your own knowledge):\n"
                      + "\n".join(f"- {c}" for c in taught))
        if personal:
            block += ("\nSaved facts that may be relevant (the user's own words; 'ben/benim/-im/I/my' inside a quote "
                      "means the user, not you). Use one only if it directly answers the question, say it about them "
                      "in second person, and never add details. Anything about the user not stated here is unknown:\n"
                      + "\n".join(f'- The user said: "{c}"' for c in personal))
        else:
            block += ("\nNo saved fact about the user matches this message. If it asks about their personal details "
                      "(family, birthday, preferences, plans...), say you don't know; do not guess.")
        return block

    def build(self, user_text: str, language: str, web_note: str | None = None) -> list[dict]:
        """web_note: arama sonuçları bloğu; verilirse "internetin yok" hatırlatması yerine o eklenir."""
        self._pending_user = user_text
        now = datetime.now()
        rule = ADDRESS_RULE.format(tr=self.s.address_tr, en=self.s.address_en,
                                   tr_cap=self.s.address_tr[:1].upper() + self.s.address_tr[1:])
        system = SYSTEM_PROMPT.format(address_rule=rule) + f"\nCurrent local time: {now:%A, %d %B %Y, %H:%M}."
        if self.s.user_name:
            system += f"\nThe user's name is {self.s.user_name}."
        # Kendini tanıtırken "internete gitmem" gibi yanlış şeyler söylemesin: güncel yetenekler
        web = ("When a question needs current information, the app automatically searches the web, checks "
               "weather (Open-Meteo) and exchange rates for you, and gives you the results."
               if self.s.internet_enabled else "Internet access is turned off in settings.")
        system += ("\nYour capabilities: voice conversation in Turkish and English, running locally on the user's PC; "
                   "remembering facts when he says 'bunu hatırla' and forgetting them with 'unut'; "
                   f"{web} When the user gives a direct command, the app itself opens allowed apps (Chrome, Word, "
                   "Not Defteri...), searches in Chrome or YouTube, plays a YouTube video by name, takes a "
                   "screenshot, reads/summarizes/translates the text on the screen or clipboard, looks up English words in a dictionary,creates a file or folder on the desktop, changes volume, controls media and locks "
                   "the screen; you never run anything yourself and cannot delete files or control the phone. "
                   "If asked to do one of these, tell them the command to say. Speak to the user directly in second "
                   "person; do not refer to him by name in third person.")
        learned = self.repo.learned_names() if self.repo else []
        if places.is_local(user_text, self.s.city, learned):
            system += "\n" + places.context(self.s.city)
        # Geçmiş hakkında uydurmasın diye elindeki kaydı açıkça söyle
        n = len(self.turns)
        system += ("\nYou have no record of any conversation with the user before this session; if asked about "
                   "earlier days or weeks, say you don't remember. ")
        system += (f"This session has {n} previous exchanges, shown below; that is all you know."
                   if n else "This is the first message of the session.")
        system += self._memory_block(user_text)
        msgs = [{"role": "system", "content": system}]
        for u, a in self.turns[-self.s.history_turns:]:
            msgs += [{"role": "user", "content": SPEAKER + u}, {"role": "assistant", "content": a}]
        # Küçük modeller genel talimatı unutuyor; soruya en yakın yerde açıkça hatırlat
        if web_note:
            note = web_note
        else:
            note = LIVE_INFO_NOTE if LIVE_INFO.search(user_text) else STYLE_NOTE
        if language in LANG_HINT:
            note += " " + LANG_HINT[language]
        msgs.append({"role": "system", "content": note})
        msgs.append({"role": "user", "content": SPEAKER + user_text})
        return msgs

    def build_agent(self, user_text: str, language: str) -> list[dict]:
        """Ajan için kısa istem: kimlik, hitap, ilgili hafıza ve son 4 tur. Tam sohbet istemi (yetenek listesi,
        "internetin yok" kuralları) hem gereksiz hem uzundu: Groq'un dakikalık token sınırı hemen doluyordu."""
        self._pending_user = user_text
        rule = ADDRESS_RULE.format(tr=self.s.address_tr, en=self.s.address_en,
                                   tr_cap=self.s.address_tr[:1].upper() + self.s.address_tr[1:])
        system = ("You are Stark, the user's voice assistant on their Windows PC. Your reply is spoken aloud.\n"
                  + rule)
        if self.s.user_name:
            system += f"\nThe user's name is {self.s.user_name}."
        if self.s.city:
            system += f"\nThe user lives in {self.s.city}, Türkiye (use it for local questions like weather)."
        system += self._memory_block(user_text)
        msgs = [{"role": "system", "content": system}]
        for u, a in self.turns[-4:]:
            msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a[:400]}]
        if language in LANG_HINT:
            msgs[0]["content"] += "\n" + LANG_HINT[language]
        msgs.append({"role": "user", "content": user_text})
        return msgs

    def build_research(self, user_text: str, language: str, note: str) -> list[dict]:
        """Araştırma cevabı için kısa istem. Ekran kartı istemi ~150 token/sn okuyor: tam sohbet istemi
        (yetenekler, hafıza, 8 tur geçmiş) + kaynaklar 2000 token = 14 sn bekleme demekti."""
        self._pending_user = user_text
        rule = ADDRESS_RULE.format(tr=self.s.address_tr, en=self.s.address_en,
                                   tr_cap=self.s.address_tr[:1].upper() + self.s.address_tr[1:])
        system = ("You are Stark, the user's voice assistant. Your reply is spoken aloud: plain short sentences, no "
                  "lists, Markdown or emoji, no advice to check other websites, no closing remarks.\n" + rule +
                  f"\nToday is {datetime.now():%A, %d %B %Y}.")
        msgs = [{"role": "system", "content": system}]
        for u, a in self.turns[-2:]:  # "o maç", "peki dün?" gibi devam soruları için son iki tur
            msgs += [{"role": "user", "content": SPEAKER + u}, {"role": "assistant", "content": a[:300]}]
        if language in LANG_HINT:
            note += " " + LANG_HINT[language]
        msgs.append({"role": "system", "content": note})
        msgs.append({"role": "user", "content": SPEAKER + user_text})
        return msgs

    def complete(self, assistant_text: str) -> None:
        if self._pending_user is not None and assistant_text.strip():
            self.record(self._pending_user, assistant_text.strip())
        self._pending_user = None

    def record(self, user_text: str, assistant_text: str) -> None:
        """Bir turu bağlama ve (varsa) kalıcı geçmişe ekler."""
        self.turns.append((user_text, assistant_text))
        if self.repo:
            if self._conversation_id is None:
                self._conversation_id = self.repo.new_conversation()
            self.repo.add_message(self._conversation_id, "user", user_text)
            self.repo.add_message(self._conversation_id, "assistant", assistant_text)

    def reset(self) -> None:
        """Yeni sohbet: geçici bağlam temizlenir; kalıcı geçmiş ve hafıza silinmez."""
        self.turns.clear()
        self._pending_user = None
        self._conversation_id = None
