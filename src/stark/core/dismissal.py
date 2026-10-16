"""Kapanış cümleleri ("teşekkürler", "sağ ol", "bu kadar"…): Stark kısa cevap verip hemen beklemeye döner.

Yalnızca cümlenin tamamı kapanış ifadesiyse geçerlidir; "Teşekkürler, bir de şunu sorayım" sohbeti sürdürür.
"""
import re

_FILLER = r"(?:tamam(?:dır)?|peki|ok(?:ey)?|oldu|güzel|harika|süper|çok|stark|patron|boss|great|ok(?:ay)?|cool|alright)"
_TR = (r"(?:teşekkürler|teşekkür\s+ederim|çok\s+teşekkürler|sağ\s*ol(?:un)?|sağol(?:un)?|eyvallah|"
       r"(?:şimdilik\s+)?bu\s+kadar|bu\s+kadar\s+yeter|yeter|hepsi\s+bu|görüşürüz|hoşça\s+kal|iyi\s+geceler|"
       r"kendine\s+iyi\s+bak|uyu(?:yabilirsin)?|sonra\s+konuşuruz)")
_EN = (r"(?:thanks(?:\s+a\s+lot)?|thank\s+you(?:\s+very\s+much)?|that'?s\s+all|that\s+will\s+be\s+all|"
       r"good\s*bye|bye|see\s+you|good\s+night|go\s+to\s+sleep)")
_SEP = r"[\s,.!]*"


def _full(phrase: str) -> re.Pattern:
    return re.compile(rf"^{_SEP}(?:{_FILLER}{_SEP})*{phrase}(?:{_SEP}(?:{_FILLER}|{phrase}))*{_SEP}$", re.I)


TR, EN = _full(_TR), _full(_EN)

REPLIES = {
    "tr": {"night": "İyi geceler patron.", "bye": "Görüşürüz patron.", "default": "Rica ederim patron."},
    "en": {"night": "Good night, boss.", "bye": "See you, boss.", "default": "You're welcome, boss."},
}


# Söz kesme komutu: "dur", "sus", "yeter", "kes", "tamam dur" (cümlenin tamamı) → sessizce dinlemeye dön
_STOP = r"(?:dur|sus|kes|bekle|stop|wait|be\s+quiet|shut\s+up)"  # "yeter" kapanış sayılır (uykuya geçer)
STOP = re.compile(rf"^{_SEP}(?:{_FILLER}{_SEP})*{_STOP}(?:{_SEP}(?:{_FILLER}|{_STOP}))*{_SEP}$", re.I)


def is_stop(text: str) -> bool:
    return bool(STOP.match(text.strip()))


def reply_for(text: str) -> str | None:
    """Kapanış cümlesiyse Stark'ın kısa cevabını, değilse None döner."""
    t = text.strip()
    lang = "tr" if TR.match(t) else "en" if EN.match(t) else None
    if lang is None:
        return None
    low = t.lower()
    if "gece" in low or "night" in low:
        key = "night"
    elif any(w in low for w in ("görüşürüz", "hoşça", "sonra konuşuruz", "bye", "see you")):
        key = "bye"
    else:
        key = "default"
    return REPLIES[lang][key]
