import os
import time

import pytest

from stark.tools import files
from stark.tools.files import FileCommand, parse


@pytest.mark.parametrize("text, cmd", [
    ("Masaüstündeki ödev dosyasını aç.", FileCommand("file", "ödev", "desktop", "dosyasını")),
    ("Veri yapıları ödevimi aç", FileCommand("file", "Veri yapıları", "", "ödevimi")),
    ("Belgelerdeki staj raporu dosyasını aç", FileCommand("file", "staj raporu", "documents", "dosyasını")),
    ("Bütçe tablosunu aç", FileCommand("file", "Bütçe", "", "tablosunu")),
    ("Tatil fotoğrafını aç", FileCommand("file", "Tatil", "", "fotoğrafını")),
    ("Son indirdiğim dosyayı aç.", FileCommand("latest_download", where="downloads")),
    ("En son indirilen dosyayı aç", FileCommand("latest_download", where="downloads")),
    ("İndirilenler klasörünü aç", FileCommand("folder", where="downloads")),
    ("Belgelerimi aç", FileCommand("folder", where="documents")),
    ("Proje adlı dosyayı aç", FileCommand("file", "Proje", "", "dosyayı")),
])
def test_parse(text, cmd):
    assert parse(text) == cmd


@pytest.mark.parametrize("text", ["Chrome'u aç", "YouTube'da Tarkan Kuzu Kuzu'yu aç", "Dosya nasıl açılır?",
                                  "Bu dosyayı aç", "Fotosentez nedir?"])
def test_not_file_commands(text):
    assert parse(text) is None


def _touch(path, age=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    t = time.time() - age
    os.utime(path, (t, t))
    return path


def test_find_prefers_full_match_then_newest(tmp_path):
    _touch(tmp_path / "Ödevler" / "veri_yapilari_odev_1.docx", age=500)
    new = _touch(tmp_path / "Ödevler" / "veri_yapilari_odev_2.docx", age=10)
    _touch(tmp_path / "alakasız.txt")
    assert files.find("veri yapıları ödev", roots=[tmp_path]) == new
    assert files.find("staj raporu", roots=[tmp_path]) is None


def test_find_kind_filters_extension(tmp_path):
    _touch(tmp_path / "bütçe.xlsx", age=100)
    _touch(tmp_path / "bütçe notları.txt")
    assert files.find("bütçe", kind="tablosunu", roots=[tmp_path]).suffix == ".xlsx"


def test_programs_are_never_run(tmp_path, monkeypatch):
    exe = _touch(tmp_path / "setup.exe")
    doc = _touch(tmp_path / "rapor.pdf")
    started, opened = [], []
    monkeypatch.setattr(files.subprocess, "Popen", lambda args: started.append(args))
    assert files.open_safely(exe, opener=opened.append) is False
    assert opened == [] and started and "/select," in started[0]
    assert files.open_safely(doc, opener=opened.append) is True and opened == [str(doc)]


def test_known_folders_exist():
    for key in ("desktop", "documents", "downloads", "pictures"):
        assert files.known_folder(key).exists()
