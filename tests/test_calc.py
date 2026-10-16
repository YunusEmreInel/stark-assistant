import pytest

from stark.tools.calc import fmt, solve


@pytest.mark.parametrize("text, expected", [
    ("345 çarpı 27 kaç?", "345 × 27 = 9.315."),
    ("1250 bölü 4 kaç eder?", "1250 ÷ 4 = 312,5."),
    ("12 artı 30 eksi 7", "12 + 30 - 7 = 35."),
    ("2 üzeri 10 kaç?", "2 ^ 10 = 1.024."),
    ("3,5 kere 4", "3,5 × 4 = 14."),
    ("What is 15 times 4?", "15 × 4 = 60."),
    ("10 bölü 3", "10 ÷ 3 = 3,3333."),
])
def test_arithmetic(text, expected):
    assert solve(text).spoken == expected


@pytest.mark.parametrize("text, part", [
    ("200'ün yüzde 18'i kaç?", "36"),
    ("1000 liraya yüzde 20 KDV ekle", "1.200"),
    ("yüzde 20 KDV dahil 1200 lira", "KDV hariç tutar 1.000, KDV 200"),
    ("500 liraya yüzde 10 indirim", "450"),
    ("144'ün karekökü", "12"),
    ("5 mil kaç kilometre?", "8,0467 kilometre"),
    ("30 derece kaç Fahrenheit?", "86 derece Fahrenheit"),
    ("100 Fahrenheit kaç santigrat?", "37,78 derece santigrat"),
    ("10 kilo kaç pound?", "22,0462 pound"),
])
def test_percent_root_units(text, part):
    assert part in solve(text).spoken


@pytest.mark.parametrize("text", [
    "Fotosentez nedir?", "Dolar kaç lira?", "Kaç yaşındayım?", "2026 yılında ne oldu?",
    "Türkiye'nin 81 ili var mı?", "Saat kaç?", "Fenerbahçe 3 0 kazandı mı?",
])
def test_not_math(text):
    assert solve(text) is None


def test_dangerous_input_rejected():
    assert solve("__import__('os').system('dir')") is None
    assert solve("9 üzeri 999999") is None


def test_fmt():
    assert fmt(1234567) == "1.234.567" and fmt(3.5) == "3,5" and fmt(-2.25) == "-2,25"
