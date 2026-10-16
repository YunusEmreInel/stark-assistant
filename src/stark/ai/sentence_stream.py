"""LLM'den parça parça gelen metni seslendirilebilir cümlelere böler."""
import re

_ABBREV = {"dr", "prof", "vb", "vs", "örn", "bkz", "sn", "no", "mr", "mrs", "ms", "st", "etc"}
# Cümle sonu: . ! ? … (+ kapanış tırnak/parantez) ardından boşluk veya tamponun sonu
_END = re.compile(r"[.!?…]+[\"')\]]*(?=(\s|$))")


class SentenceStream:
    def __init__(self, min_chars: int = 20, max_chars: int = 300):
        self.buf = ""
        self.min_chars = min_chars   # çok kısa cümleler bir sonrakiyle birleşir
        self.max_chars = max_chars   # noktalama gelmezse boşlukta böl
        self._in_code = False

    def feed(self, piece: str) -> list[str]:
        self.buf += piece
        out = []
        while (s := self._next()) is not None:
            out.append(s)
        return out

    def flush(self) -> list[str]:
        rest, self.buf = self.buf.strip(), ""
        if self._in_code:
            self._in_code = False
            return ["```" + rest + "```"] if rest else []
        return [rest] if rest else []

    def _next(self) -> str | None:
        if self._in_code:
            fence = self.buf.find("```")
            if fence == -1:
                return None
            block, self.buf = self.buf[:fence], self.buf[fence + 3:]
            self._in_code = False
            return "```" + block + "```"

        fence = self.buf.find("```")
        text = self.buf if fence == -1 else self.buf[:fence]
        for m in _END.finditer(text):
            if m.end() == len(self.buf):
                return None  # devamı gelebilir: "3." → "3.5", "Dr." → "Dr. Ali"
            cand = self.buf[:m.end()].strip()
            if self._is_abbrev(cand) or len(cand) < self.min_chars:
                continue
            self.buf = self.buf[m.end():]
            return cand
        if fence != -1:
            before, self.buf = self.buf[:fence].strip(), self.buf[fence + 3:]
            self._in_code = True
            return before or self._next()
        if "\n\n" in self.buf:
            para, rest = self.buf.split("\n\n", 1)
            if len(para.strip()) >= self.min_chars:
                self.buf = rest
                return para.strip()
        if len(self.buf) > self.max_chars:
            cut = self.buf.rfind(" ", 0, self.max_chars)
            cut = cut if cut > 0 else self.max_chars
            part, self.buf = self.buf[:cut], self.buf[cut:]
            return part.strip()
        return None

    @staticmethod
    def _is_abbrev(cand: str) -> bool:
        if not cand.endswith("."):
            return False
        last = cand[:-1].split()[-1].lower() if cand[:-1].split() else ""
        return last in _ABBREV or (len(last) == 1 and last.isalpha())
