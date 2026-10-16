"""Hafıza komutlarını kod ile tanır (dil modeli hafızaya yazamaz). Konuşma tanımadan gelen metne uygulanır."""
import re
from dataclasses import dataclass

_R = re.IGNORECASE
_TRIGGER = r"(?:hatırla|aklında\s+tut|unutma|hafızana\s+kaydet)"  # "not al" artık notlara gider
# Notlar: "Not al: süt al", "Şunu not et: ...", "..., bunu not al"; okuma, son notu silme, masaüstüne aktarma
NOTE_ADD = [
    re.compile(r"^(?:lütfen\s+)?(?:bir\s+)?(?:bunu\s+|şunu\s+)?not\s+(?:al|et|düş)\w*\s*[:,.]?\s+(?P<x>.+)$", _R),
    re.compile(r"^(?P<x>.+?)[,.]?\s+(?:bunu\s+|şunu\s+)?not\s+(?:al|et|düş)\w*\s*[.!]?$", _R),
    re.compile(r"^(?:take\s+a\s+note|note\s+down|make\s+a\s+note)\s*[:,.]?\s+(?P<x>.+)$", _R),
]
NOTE_LIST = re.compile(r"notlar[ıi]m[ıi]?\s+(?:oku|söyle|neler)|notlarımda\s+ne(ler)?\s+var|not(lar)?umu\s+oku|"
                       r"read\s+(?:me\s+)?my\s+notes|what\s+are\s+my\s+notes", _R)
NOTE_DELETE_LAST = re.compile(r"(?:son|en\s+son)\s+not(?:u|umu)?\s+sil\w*|delete\s+(?:the\s+)?last\s+note", _R)
NOTE_EXPORT = re.compile(r"notlar[ıi]m[ıi]?\s+masaüstüne\s+(?:aktar|kaydet|yaz)\w*|export\s+my\s+notes", _R)
REMEMBER = [
    re.compile(rf"^(?:lütfen\s+)?(?:bunu|şunu|şu\s+bilgiyi)?\s*{_TRIGGER}(?:\s+ki)?\s*[:,.]?\s+(?P<x>.+)$", _R),
    re.compile(rf"^(?P<x>.+?)[,.]?\s+(?:bunu\s+|şunu\s+)?{_TRIGGER}\s*[.!]?$", _R),
    re.compile(r"^(?:please\s+)?remember(?:\s+that)?\s*[:,.]?\s+(?P<x>.+)$", _R),
    re.compile(r"^(?P<x>.+?)[,.]?\s+(?:please\s+)?remember\s+(?:that|this)\s*[.!]?$", _R),
]
# Genel bilgi öğretme / düzeltme ("Şunu öğren: Bornova İzmir'in bir ilçesidir", "Hayır, doğrusu şu: ...")
LEARN = [
    re.compile(r"^(?:lütfen\s+)?(?:bunu\s+|şunu\s+)?(?:öğren|bil|aklına\s+yaz)\b(?:\s+ki)?\s*[:,.]?\s+(?P<x>.+)$", _R),
    re.compile(r"^(?P<x>.+?)[,.]?\s+(?:bunu\s+|şunu\s+)?(?:öğren|bil)\s*[.!]?$", _R),
    re.compile(r"^(?:hayır|yanlış|yok)?[\s,.!]*(?:doğrusu|aslında\s+doğrusu)\s*(?:şu|şöyle)?\s*[:,.]?\s+(?P<x>.+)$", _R),
    re.compile(r"^(?:please\s+)?learn(?:\s+that)?\s*[:,.]?\s+(?P<x>.+)$", _R),
    re.compile(r"^(?:no[,.]?\s+)?the\s+correct\s+(?:answer|one)\s+is\s*[:,]?\s+(?P<x>.+)$", _R),
]
LIST_LEARNED = re.compile(r"neler(i)?\s+öğrendin|ne\s+öğrendin|öğrettiklerim|what\s+have\s+you\s+learn", _R)
FORGET = [
    re.compile(r"^(?:lütfen\s+)?(?:bunu\s+|şunu\s+)?(?:hafızandan\s+)?unut\b\s*[:,.]?\s*(?P<x>.*)$", _R),
    re.compile(r"^(?P<x>.+?)[,.]?\s+(?:bilgisini\s+|bunu\s+)?(?:hafızandan\s+(?:sil|çıkar)|unut)\s*[.!]?$", _R),
    re.compile(r"^(?:please\s+)?forget(?:\s+that|\s+about)?\s*[:,.]?\s*(?P<x>.*)$", _R),
]
LIST = re.compile(
    r"(neler(i)?|ne)\s+hatırlıyorsun|hakkımda\s+ne(ler)?\s+biliyorsun|hafızanda\s+ne(ler)?\s+var|"
    r"neler(i)?\s+kaydettin|what\s+do\s+you\s+remember|what\s+do\s+you\s+know\s+about\s+me", _R)
# kullanıcının kişisel bilgisini soran sorular: hafızada karşılığı yoksa model uydurmasın diye kodla cevaplanır
# Yalnızca birinci tekil iyelikli biçimler ("annem", "doğum günüm"): "Atatürk kaç yaşında öldü?" eşleşmez
_PERSONAL_TR = (r"\b(annem|babam|kardeşim|ablam|abim|ağabeyim|eşim|sevgilim|kız\s+arkadaşım|erkek\s+arkadaşım|"
                r"en\s+yakın\s+arkadaşım|dedem|ninem|anneannem|babaannem|teyzem|halam|amcam|dayım|çocuğum|"
                r"oğlum|kızım|köpeğim|kedim|doğum\s+günüm|yaşım|kaç\s+yaşındayım|adresim|telefon\s+numaram|"
                r"okulum|bölümüm|sınıfım|mesleğim|memleketim|nereliyim|en\s+sevdiğim|favori\s+\w+(ım|im|um|üm)|"
                r"benim\s+adım|adım\s+ne|soyadım|boyum|kilom|hobim|hobilerim)\w*")
# Bilgi soran kelimeler ("Annem için hediye önerir misin?" bilgi sormaz, modele gider)
_QUESTION_TR = r"\b(ne|neydi|nedir|kim|kimdi|kimdir|nerede|nerede|kaç|hangi|biliyor|hatırlıyor)\w*"
PERSONAL_Q = [
    re.compile(_PERSONAL_TR + r".*" + _QUESTION_TR, _R),
    re.compile(r"\b(kaç\s+yaşındayım|nereliyim|benim\s+adım\s+ne|adım\s+ne)\b", _R),
    re.compile(r"\b(my\s+(mom|mother|dad|father|brother|sister|wife|husband|girlfriend|boyfriend|son|daughter|"
               r"dog|cat|birthday|age|address|phone|school|major|job|hometown|favou?rite|name|hobby|hobbies)|"
               r"how\s+old\s+am\s+i|where\s+am\s+i\s+from)\b.*(\?|\b(what|who|when|where|do|does|is)\b)", _R),
]


def is_personal_question(text: str) -> bool:
    return any(rx.search(text) for rx in PERSONAL_Q)


# "Bunu unut" gibi nesnesiz komutlar son kaydı hedefler
_THIS = {"", "bunu", "şunu", "onu", "that", "this", "it"}


@dataclass(frozen=True)
class MemoryCommand:
    # remember | learn | forget | forget_last | list | list_learned | note | note_list | note_delete_last | note_export
    action: str
    payload: str = ""


def _clean(x: str) -> str:
    return x.strip().strip(" .,:;!\"'“”").strip()


def parse(text: str) -> MemoryCommand | None:
    t = text.strip()
    if not t:
        return None
    if NOTE_EXPORT.search(t):
        return MemoryCommand("note_export")
    if NOTE_LIST.search(t):
        return MemoryCommand("note_list")
    if NOTE_DELETE_LAST.search(t):
        return MemoryCommand("note_delete_last")
    for rx in NOTE_ADD:
        m = rx.match(t)
        if m:
            x = _clean(m.group("x"))
            if x and x.lower() not in _THIS and len(x) >= 2:
                return MemoryCommand("note", x)
    if LIST_LEARNED.search(t):
        return MemoryCommand("list_learned")
    if LIST.search(t):
        return MemoryCommand("list")
    for rx in LEARN:
        m = rx.match(t)
        if m:
            x = _clean(m.group("x"))
            if x and not x.endswith("?") and x.lower() not in _THIS and len(x) >= 3:
                return MemoryCommand("learn", x)
    for rx in FORGET:
        m = rx.match(t)
        if m:
            x = _clean(m.group("x"))
            return MemoryCommand("forget_last") if x.lower() in _THIS else MemoryCommand("forget", x)
    for rx in REMEMBER:
        m = rx.match(t)
        if m:
            x = _clean(m.group("x"))
            # Soru cümlesi ("Hatırla, dün ne yaptık?") veya boş içerik kaydedilmez
            if x and not x.endswith("?") and x.lower() not in _THIS and len(x) >= 3:
                return MemoryCommand("remember", x)
    return None
