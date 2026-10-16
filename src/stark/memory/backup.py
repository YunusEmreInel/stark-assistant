"""Günlük yedek: hafıza veritabanı ve ayarlar ~/.stark/yedekler altına, son 7 gün tutulur.

Silinen bilgiler en fazla 7 gün yedeklerde kalabilir; kullanıcı bunu bilir ve Ayarlar'dan yedekleri silebilir.
"""
import shutil
import sqlite3
from datetime import date
from pathlib import Path

KEEP_DAYS = 7


def daily_backup(db_path: Path, settings_path: Path, backup_dir: Path, today: date | None = None,
                 keep: int = KEEP_DAYS) -> Path | None:
    """Bugün yedek yoksa alır (SQLite çevrimiçi yedekleme API'si: çalışırken de tutarlı); eskileri temizler."""
    today = today or date.today()
    target = backup_dir / f"stark-{today:%Y-%m-%d}.db"
    if target.exists() or not db_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    src, dst = sqlite3.connect(db_path), sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    if settings_path.exists():
        shutil.copy2(settings_path, backup_dir / f"settings-{today:%Y-%m-%d}.json")
    prune(backup_dir, keep)
    return target


def prune(backup_dir: Path, keep: int = KEEP_DAYS) -> None:
    for pattern in ("stark-*.db", "settings-*.json"):
        for old in sorted(backup_dir.glob(pattern))[:-keep]:
            old.unlink()


def list_backups(backup_dir: Path) -> list[Path]:
    return sorted(backup_dir.glob("stark-*.db")) if backup_dir.exists() else []


def delete_all(backup_dir: Path) -> int:
    count = 0
    for pattern in ("stark-*.db", "settings-*.json"):
        for f in backup_dir.glob(pattern):
            f.unlink()
            count += 1
    return count
