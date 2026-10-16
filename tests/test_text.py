from stark.ai.sentence_stream import SentenceStream
from stark.ai.text_for_speech import to_speech


def run(pieces, **kw):
    s = SentenceStream(**kw)
    out = []
    for p in pieces:
        out += s.feed(p)
    return out + s.flush()


def chars(text):
    return list(text)  # token token akışı taklidi


def test_splits_sentences_from_char_stream():
    text = "Fotosentez bitkilerin besin üretmesidir. Güneş ışığı ve su kullanılır! Sonuçta oksijen çıkar."
    assert run(chars(text)) == [
        "Fotosentez bitkilerin besin üretmesidir.",
        "Güneş ışığı ve su kullanılır!",
        "Sonuçta oksijen çıkar.",
    ]


def test_decimal_and_abbreviation_not_split():
    text = "Pi sayısı yaklaşık 3.14 olarak bilinir. Dr. Ali bunu bize anlattı, sağ olsun."
    assert run(chars(text)) == ["Pi sayısı yaklaşık 3.14 olarak bilinir.", "Dr. Ali bunu bize anlattı, sağ olsun."]


def test_short_first_sentence_merged():
    assert run(chars("Evet. Bu konuda sana yardımcı olabilirim.")) == ["Evet. Bu konuda sana yardımcı olabilirim."]


def test_code_block_kept_separate():
    text = "Şöyle yapabilirsin kolayca:\n```python\nx = [1, 2]\nx.reverse()\n```\nBu kadar basit aslında."
    out = run(chars(text))
    assert out[0] == "Şöyle yapabilirsin kolayca:"
    assert out[1].startswith("```") and "x.reverse()" in out[1]
    assert out[2] == "Bu kadar basit aslında."


def test_long_text_without_punctuation_is_cut():
    out = run(chars("kelime " * 100), max_chars=100)
    assert len(out) > 1 and all(len(o) <= 100 for o in out)


def test_math_spoken():
    assert to_speech("345 × 27 = 9.315.") == "345 çarpı 27 eşittir 9315."
    assert to_speech("12 + 30 - 7 = 35.") == "12 artı 30 eksi 7 eşittir 35."
    assert to_speech("15 × 4 = 60.", "en") == "15 times 4 equals 60."
    assert to_speech("1250 ÷ 4 = 312,5.") == "1250 bölü 4 eşittir 312,5."


def test_humanize_dates():
    from stark.ai.text_for_speech import humanize_dates
    assert humanize_dates("Olay 2026-10-15 tarihinde oldu.") == "Olay 15 Ekim 2026 tarihinde oldu."
    assert humanize_dates("on 2026-10-05", "en") == "on October 5, 2026"
    assert humanize_dates("Skor 2026-13-40") == "Skor 2026-13-40"


def test_strip_emoji_keeps_text_and_lines():
    from stark.ai.text_for_speech import strip_emoji
    assert strip_emoji("Evet, doğru. 😊\nNe yapalım? 🚀") == "Evet, doğru.\nNe yapalım?"


def test_to_speech_cleans_markdown_and_emoji():
    assert to_speech("**Tabii!** 😊 Şunu dene: `list.reverse()` 🚀") == "Tabii! Şunu dene: list.reverse()"
    assert to_speech("- Çay iç\n- Müzik dinle") == "Çay iç Müzik dinle"
    assert to_speech("Bkz. https://www.example.com/a/b?c=1") == "Bkz. example.com"
    assert to_speech("```python\nprint(1)\n```") == "Kodu ekrana yazdım."
    assert to_speech("```x```", "en") == "I put the code on the screen."
