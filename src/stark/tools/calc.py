"""Kesin hesaplama ve birim çevirme: küçük dil modeli aritmetikte hata yapıyor; hesabı kod yapar.

"345 çarpı 27", "1250 bölü 4", "2 üzeri 10", "144'ün karekökü", "200'ün yüzde 18'i", "1000 liraya yüzde 20 KDV ekle",
"5 mil kaç kilometre", "30 derece kaç Fahrenheit". Değerlendirme AST ile güvenli: yalnızca sayılar ve dört işlem/üs.
"""
import ast
import math
import operator
import re
from dataclasses import dataclass

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Mod: operator.mod}
NUM = r"-?\d+(?:[.,]\d+)?"
WORD_OPS = [  # Türkçe/İngilizce işlem sözcükleri → işaret
    (r"\b(?:çarpı|kere|defa|times|multiplied\s+by)\b|(?<=\d)\s*[x×]\s*(?=\d)", "*"),
    (r"\b(?:bölü|divided\s+by|over)\b|÷", "/"),
    (r"\b(?:artı|plus|ekle)\b", "+"),
    (r"\b(?:eksi|minus)\b", "-"),
    (r"\b(?:üzeri|üssü|to\s+the\s+power\s+of)\b|\^", "**"),
    (r"\b(?:mod|modu)\b", "%"),
]
FILLER = re.compile(r"\b(?:kaç(?:\s+eder|tır|dır)?|eder|nedir|ne\s+eder|sonuç|hesapla|kaçtır|what\s+is|how\s+much\s+is|"
                    r"calculate|equals?|eşittir|stark|patron|lütfen)\b|[?=!]", re.I)

UNITS = {  # (eşleşme, çarpan, temel birim, okunur ad)
    "km": (r"kilometre|km", 1000.0, "m", "kilometre"), "m": (r"metre|\bm\b", 1.0, "m", "metre"),
    "cm": (r"santim(?:etre)?|cm", 0.01, "m", "santimetre"), "mm": (r"milimetre|mm", 0.001, "m", "milimetre"),
    "mi": (r"mil\b|mile|miles", 1609.344, "m", "mil"), "ft": (r"feet|fit|foot", 0.3048, "m", "feet"),
    "in": (r"inç|inch|inches", 0.0254, "m", "inç"),
    "kg": (r"kilogram|kilo|kg", 1.0, "kg", "kilogram"), "g": (r"gram|\bg\b", 0.001, "kg", "gram"),
    "lb": (r"pound|libre|lb", 0.45359237, "kg", "pound"),
    "l": (r"litre|lt|\bl\b", 1.0, "l", "litre"), "gal": (r"galon|gallon", 3.785411784, "l", "galon"),
}
TEMP = {"c": r"santigrat|celsius|derece(?!\s*fahrenheit)|°c", "f": r"fahrenheit|°f"}


@dataclass(frozen=True)
class CalcResult:
    spoken: str


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def fmt(x: float) -> str:
    """Türkçe sayı yazımı: binlik ayırıcı nokta, ondalık virgül, gereksiz sıfır yok."""
    if math.isfinite(x) and abs(x - round(x)) < 1e-9:
        s = f"{round(x):,}".replace(",", ".")
        return s
    s = f"{x:,.4f}".rstrip("0").rstrip(".")
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _safe_eval(expr: str) -> float:
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("üs çok büyük")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("desteklenmeyen ifade")
    return float(ev(ast.parse(expr, mode="eval")))


def _percent(t: str) -> CalcResult | None:
    # "1000 liraya yüzde 20 KDV ekle" / "yüzde 20 KDV dahil 1200 lira" / "200'ün yüzde 18'i"
    m = re.search(rf"({NUM})\s*(?:\w*['’]?\w*)?\s+(?:yüzde|%)\s*({NUM})\s*(?:kdv\s+)?(?:ekle|ekleyince|fazlası|zam)", t)
    if m:
        base, p = _num(m.group(1)), _num(m.group(2))
        return CalcResult(f"{fmt(base)} artı yüzde {fmt(p)}: {fmt(base * (1 + p / 100))}.")
    m = re.search(rf"({NUM})\s*(?:\w*['’]?\w*)?\s+(?:yüzde|%)\s*({NUM})\s*(?:indirim|eksiği|düşünce|indir)", t)
    if m:
        base, p = _num(m.group(1)), _num(m.group(2))
        return CalcResult(f"{fmt(base)} eksi yüzde {fmt(p)}: {fmt(base * (1 - p / 100))}.")
    m = re.search(rf"(?:yüzde|%)\s*({NUM})\s*kdv\s+dahil\s+({NUM})", t)
    if m:
        p, total = _num(m.group(1)), _num(m.group(2))
        net = total / (1 + p / 100)
        return CalcResult(f"KDV hariç tutar {fmt(net)}, KDV {fmt(total - net)}.")
    m = re.search(rf"({NUM})\s*['’]?\w*\s+(?:yüzde|%)\s*({NUM})", t) or re.search(rf"(?:yüzde|%)\s*({NUM})\s*['’]?\w*\s+of\s+({NUM})", t)
    if m:
        a, b = _num(m.group(1)), _num(m.group(2))
        base, p = (a, b) if "of" not in m.group(0) else (b, a)
        return CalcResult(f"{fmt(base)}'in yüzde {fmt(p)}'i {fmt(base * p / 100)}.".replace("'in", "'in"))
    return None


def _convert(t: str) -> CalcResult | None:
    m = re.search(rf"({NUM})\s*(\S+(?:\s+\S+)?)\s+(?:kaç|in|to|=)\s+(\S+)", t)
    if not m:
        return None
    value, src, dst = _num(m.group(1)), m.group(2), m.group(3)
    for a, b in (("c", "f"), ("f", "c")):
        if re.search(TEMP[a], src) and re.search(TEMP[b], dst):
            out = value * 9 / 5 + 32 if a == "c" else (value - 32) * 5 / 9
            names = {"c": "santigrat", "f": "Fahrenheit"}
            return CalcResult(f"{fmt(value)} derece {names[a]}, {fmt(round(out, 2))} derece {names[b]}.")
    s = next((k for k, (rx, *_rest) in UNITS.items() if re.search(rf"^(?:{rx})", src)), None)
    d = next((k for k, (rx, *_rest) in UNITS.items() if re.search(rf"^(?:{rx})", dst)), None)
    if not s or not d or UNITS[s][2] != UNITS[d][2]:
        return None
    out = value * UNITS[s][1] / UNITS[d][1]
    return CalcResult(f"{fmt(value)} {UNITS[s][3]}, {fmt(round(out, 4))} {UNITS[d][3]}.")


def _sqrt(t: str) -> CalcResult | None:
    m = re.search(rf"({NUM})\s*['’]?\w*\s+(?:karekökü|kare\s+kökü)|(?:square\s+root\s+of|karekök)\s+({NUM})", t)
    if not m:
        return None
    x = _num(m.group(1) or m.group(2))
    if x < 0:
        return None
    return CalcResult(f"{fmt(x)} sayısının karekökü {fmt(round(math.sqrt(x), 4))}.")


def solve(text: str) -> CalcResult | None:
    """Hesap/çevirme sorusuysa kesin sonucu döner; değilse None (dil modeline gider)."""
    t = text.lower().replace("ı", "ı").strip()
    for fn in (_percent, _convert, _sqrt):
        r = fn(t)
        if r:
            return r
    expr = t
    for rx, sym in WORD_OPS:
        expr = re.sub(rx, f" {sym} ", expr, flags=re.I)
    expr = FILLER.sub(" ", expr)
    expr = re.sub(r"(\d)\.(\d{3})(?!\d)", r"\1\2", expr)        # 1.250 → 1250 (binlik)
    expr = re.sub(r"(\d),(\d)", r"\1.\2", expr)                 # 3,5 → 3.5
    expr = re.sub(r"(\d)['’]\w+", r"\1", expr)                  # 200'ün → 200
    expr = expr.strip()
    # Yalnızca sayı ve işaretlerden oluşuyorsa ve en az bir işlem varsa hesapla
    if not re.fullmatch(r"[\d\s.+\-*/%()]+", expr) or not re.search(r"\d\s*(?:\*\*|[+\-*/%])\s*\(?-?\d", expr):
        return None
    try:
        value = _safe_eval(expr)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
        return None
    shown = re.sub(r"\s+", " ", expr.replace("**", "^").replace("*", "×").replace("/", "÷"))
    shown = re.sub(r"(\d)\.(\d)", r"\1,\2", shown)  # Türkçe ondalık: 3.5 → 3,5
    return CalcResult(f"{shown} = {fmt(round(value, 6))}.")
