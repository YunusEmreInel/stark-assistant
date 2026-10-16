"""Kılavuz güncel mi? Kodun tanıdığı her komut türü kılavuzda anlatılmalı."""
import re

from stark.memory import commands as memory_commands
from stark.tools import desktop, screen
from stark.ui import help_text


def _desktop_actions() -> set[str]:
    return {action for action, _ in desktop.PATTERNS}


def _memory_actions() -> set[str]:
    src = open(memory_commands.__file__, encoding="utf-8").read()
    return set(re.findall(r'MemoryCommand\("(\w+)"', src))


def test_every_command_kind_is_documented():
    covered = set(help_text.COVERAGE)
    from stark.tools import files
    missing = ({f"desktop:{a}" for a in _desktop_actions()} | {f"memory:{a}" for a in _memory_actions()}
               | {f"files:{a}" for a, _ in files.PATTERNS} | {f"screen:{a}" for a, _ in screen.PATTERNS}
               | {"screen:clipboard"})
    missing -= covered
    assert not missing, f"Kılavuzda anlatılmayan yeni komut türleri: {sorted(missing)} — help_text.py'ı güncelleyin"


def test_coverage_phrases_appear_in_guide():
    text = help_text.all_text()
    absent = [k for k, phrase in help_text.COVERAGE.items() if phrase not in text]
    assert not absent, absent


def test_examples_in_guide_are_really_recognized():
    """Kılavuzdaki bilgisayar ve not örnekleri gerçekten tanınmalı (yanlış örnek yazılmasın)."""
    for example in ["Chrome'da Python dersleri ara", "YouTube'da Tarkan Kuzu Kuzu'yu aç", "Ekran görüntüsü al",
                    "Masaüstünde alışveriş adında bir dosya oluştur, içine süt yaz", "Ekranı kilitle"]:
        assert desktop.parse(example) is not None, example
    for example in ["Not al: Cuma kitap iade et", "Notlarımı oku", "Son notu sil", "Notlarımı masaüstüne aktar",
                    "Bunu hatırla: en sevdiğim renk mavi", "Şunu öğren: Bornova, İzmir'in bir ilçesidir"]:
        assert memory_commands.parse(example) is not None, example
    for example in ["Ekranda ne yazıyor?", "Bunu özetle", "Bu sayfayı kısaca özetle", "Ekrandakini açıkla",
                    "Bunu İngilizceye çevir", "Bu yazıyı Türkçeye çevir", "Kopyaladığımı özetle",
                    "Panodakini İngilizceye çevir"]:
        assert screen.parse(example) is not None, example
    from stark.tools import dictionary
    for example in ["According kelimesinin Türkçesi ne?", "Serendipity ne demek?", "What does eventually mean?",
                    "Went'in Türkçesi ne?", "Kitap kelimesinin İngilizcesi ne?"]:
        assert dictionary.parse(example) is not None, example
