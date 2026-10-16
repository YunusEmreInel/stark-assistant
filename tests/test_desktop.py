import pytest

from stark.tools import desktop
from stark.tools.desktop import DesktopCommand, parse


@pytest.mark.parametrize("text, cmd", [
    ("Chrome'u aç.", DesktopCommand("open_app", "Chrome")),
    ("Word'ü başlat", DesktopCommand("open_app", "Word")),
    ("Not defterini aç", DesktopCommand("open_app", "Not defteri")),
    ("Hesap makinesini aç.", DesktopCommand("open_app", "Hesap makinesi")),
    ("YouTube'u aç.", DesktopCommand("open_app", "YouTube")),
    ("Open notepad", DesktopCommand("open_app", "notepad")),
    ("Chrome'da Python dersleri ara.", DesktopCommand("web_search", "Python dersleri")),
    ("Google'da İzmir nöbetçi eczane diye ara", DesktopCommand("web_search", "İzmir nöbetçi eczane")),
    ("Chrome'u aç ve yapay zeka haberleri ara", DesktopCommand("web_search", "yapay zeka haberleri")),
    ("YouTube'da Barış Manço şarkıları ara", DesktopCommand("youtube_search", "Barış Manço şarkıları")),
    ("YouTube'da Tarkan Kuzu Kuzu'yu aç.", DesktopCommand("youtube_play", "Tarkan Kuzu Kuzu")),
    ("YouTube'da Barış Manço Gülpembe videosunu oynat", DesktopCommand("youtube_play", "Barış Manço Gülpembe")),
    ("Sezen Aksu Gidiyorum şarkısını aç", DesktopCommand("youtube_play", "Sezen Aksu Gidiyorum")),
    ("Ekran görüntüsü al.", DesktopCommand("screenshot")),
    ("Ekranın fotoğrafını çek", DesktopCommand("screenshot")),
    ("Masaüstünde alışveriş adında bir dosya oluştur.", DesktopCommand("create", "alışveriş", "dosya")),
    ("Masaüstünde Ödevler adında bir klasör oluştur", DesktopCommand("create", "Ödevler", "klasör")),
    ("Masaüstünde alışveriş adında bir dosya oluştur, içine süt ve ekmek yaz.",
     DesktopCommand("create", "alışveriş", "dosya", "süt ve ekmek")),
    ("Sesi aç.", DesktopCommand("volume_up")),
    ("Sesi biraz kıs", DesktopCommand("volume_down")),
    ("Sesi kapat", DesktopCommand("mute")),
    ("Müziği durdur.", DesktopCommand("media_pause")),
    ("Sonraki şarkıya geç", DesktopCommand("media_next")),
    ("Ekranı kilitle.", DesktopCommand("lock")),
])
def test_parse(text, cmd):
    assert parse(text) == cmd


@pytest.mark.parametrize("text", [
    "Fotosentez nedir?", "İnternette yapay zeka haberlerini ara",  # Stark'ın kendi araması (sayfa açmaz)
    "Chrome nedir?", "Sesin güzelmiş", "Masaüstü nedir?", "Dosya nasıl silinir?",
    "Bunu hatırla: Chrome'u severim",
])
def test_not_desktop_commands(text):
    assert parse(text) is None


def test_create_never_overwrites(tmp_path):
    a = desktop.create_on_desktop("alışveriş", "dosya", "süt", desktop=tmp_path)
    b = desktop.create_on_desktop("alışveriş", "dosya", "ekmek", desktop=tmp_path)
    assert a.name == "alışveriş.txt" and b.name == "alışveriş (2).txt"
    assert a.read_text(encoding="utf-8").strip() == "süt"
    folder = desktop.create_on_desktop("Ödevler", "klasör", desktop=tmp_path)
    assert folder.is_dir()


def test_create_strips_unsafe_characters(tmp_path):
    p = desktop.create_on_desktop('..\\..\\Windows/<x>', "dosya", desktop=tmp_path)
    assert p.parent == tmp_path and "\\" not in p.name and "/" not in p.name


def test_execute_open_app_uses_allowlist():
    opened = []
    reply, _ = desktop.execute(DesktopCommand("open_app", "Not defteri"), opener=opened.append)
    assert opened == ["notepad.exe"] and "Not Defteri" in reply
    reply, _ = desktop.execute(DesktopCommand("youtube_search", "lofi müzik"), opener=opened.append)
    assert opened[-1].startswith("https://www.youtube.com/results?search_query=lofi")
