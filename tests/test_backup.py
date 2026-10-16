import sqlite3
from datetime import date, timedelta

from stark.memory import backup
from stark.memory.database import Repository


def test_daily_backup_once_per_day_and_keeps_seven(tmp_path):
    db = tmp_path / "stark.db"
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    repo = Repository(db)
    repo.add_memory("En sevdiğim renk mavi")
    out = tmp_path / "yedekler"
    start = date(2026, 10, 1)
    for i in range(10):
        assert backup.daily_backup(db, settings, out, today=start + timedelta(days=i)) is not None
    assert backup.daily_backup(db, settings, out, today=start + timedelta(days=9)) is None  # aynı gün ikinci kez yok
    files = backup.list_backups(out)
    assert len(files) == 7 and files[-1].name == "stark-2026-10-10.db"
    assert len(list(out.glob("settings-*.json"))) == 7
    # yedek gerçekten okunabilir ve veriyi içeriyor
    con = sqlite3.connect(files[-1])
    rows = con.execute("SELECT content FROM memories").fetchall()
    con.close()
    assert rows == [("En sevdiğim renk mavi",)]
    repo.close()
    assert backup.delete_all(out) == 14 and backup.list_backups(out) == []
