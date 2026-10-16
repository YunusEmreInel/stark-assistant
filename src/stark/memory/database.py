"""Yerel SQLite deposu: sohbet geçmişi ve açıkça kaydedilen kişisel hafıza (ayrı tablolar).

Silme gerçek silmedir: kayıt başka tabloda/özette tutulmaz; secure_delete ile dosyadaki içerik de ezilir.
Birden fazla thread'den (motor, LLM işçisi, arayüz) kullanılır; tüm erişim tek kilitle sıralanır.
"""
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY,
    started_at  TEXT NOT NULL,
    title       TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'personal',   -- personal | knowledge | preference
    source      TEXT NOT NULL DEFAULT 'user',       -- user (açıkça söylendi) | auto (konuşmadan) | web
    expires_at  TEXT                                -- güncel bilgiler (haber) bir süre sonra kullanılmaz
);
"""

TITLE_LEN = 60
PERSONAL, KNOWLEDGE, PREFERENCE = "personal", "knowledge", "preference"
_SENTENCE_STARTERS = set("""ben benim bizim biz sen senin o onun bu şu bunlar şunlar bir her hiç en çok yarın bugün
dün annem annemin babam babamın kardeşim kardeşimin eşim eşimin arkadaşım arkadaşımın sevdiğim doğum okulum
işim evim the my i we our this that""".split())
# Eşleşmede sayılmayan soru/yardımcı kelime kökleri (ilk 4 harf)
STOP_STEMS = {
    "bili", "musu", "mısı", "misi", "hatı", "söyl", "neyd", "nedi", "nere", "nası", "beni", "bana", "bend",
    "kimd", "hang", "acab", "lütf", "şimd", "peki", "what", "know", "reme", "your", "does", "tell", "abou",
    "who", "whe", "how", "the", "and", "you", "var", "yok", "mı", "bir",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def tr_lower(text: str) -> str:
    """Türkçe büyük/küçük harf: I→ı, İ→i (str.lower() 'İ'yi 'i̇' yapar)."""
    return text.replace("I", "ı").replace("İ", "i").lower()


def _stems(text: str) -> set[str]:
    words = "".join(ch if ch.isalnum() else " " for ch in tr_lower(text)).split()
    return {w[:4] for w in words if len(w) >= 3} - STOP_STEMS


class Repository:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA foreign_keys = ON")
            self._db.execute("PRAGMA secure_delete = ON")
            self._db.execute("PRAGMA journal_mode = WAL")
            self._db.executescript(SCHEMA)
            cols = {row[1] for row in self._db.execute("PRAGMA table_info(memories)")}
            # Eski veritabanları: sonradan eklenen sütunlar
            if "kind" not in cols:
                self._db.execute("ALTER TABLE memories ADD COLUMN kind TEXT NOT NULL DEFAULT 'personal'")
            if "source" not in cols:
                self._db.execute("ALTER TABLE memories ADD COLUMN source TEXT NOT NULL DEFAULT 'user'")
            if "expires_at" not in cols:
                self._db.execute("ALTER TABLE memories ADD COLUMN expires_at TEXT")
            self._db.commit()

    def _exec(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._db.execute(sql, args)
            self._db.commit()
            return cur

    def _all(self, sql: str, args: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ---- sohbetler ----
    def new_conversation(self) -> int:
        return self._exec("INSERT INTO conversations (started_at) VALUES (?)", (_now(),)).lastrowid

    def add_message(self, conversation_id: int, role: str, content: str) -> None:
        self._exec("INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                   (conversation_id, role, content, _now()))
        if role == "user":
            title = content if len(content) <= TITLE_LEN else content[:TITLE_LEN - 1].rstrip() + "…"
            self._exec("UPDATE conversations SET title = ? WHERE id = ? AND title IS NULL", (title, conversation_id))

    def list_conversations(self, limit: int = 500) -> list[tuple[int, str, str, int]]:
        """(id, başlangıç, başlık, mesaj sayısı) — en yeni önce, boş sohbetler hariç."""
        return self._all(
            "SELECT c.id, c.started_at, COALESCE(c.title, ''), COUNT(m.id) FROM conversations c "
            "JOIN messages m ON m.conversation_id = c.id GROUP BY c.id ORDER BY c.id DESC LIMIT ?", (limit,))

    def messages(self, conversation_id: int) -> list[tuple[str, str, str]]:
        return self._all("SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
                         (conversation_id,))

    def delete_conversation(self, conversation_id: int) -> None:
        self._exec("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    def delete_all_conversations(self) -> None:
        self._exec("DELETE FROM conversations")

    # ---- notlar (hafızadan ayrı: modele verilmez, kullanıcının kendi notları) ----
    def add_note(self, content: str) -> int:
        return self._exec("INSERT INTO notes (content, created_at) VALUES (?, ?)", (content.strip(), _now())).lastrowid

    def list_notes(self) -> list[tuple[int, str, str]]:
        return self._all("SELECT id, content, created_at FROM notes ORDER BY id")

    def delete_note(self, note_id: int) -> None:
        self._exec("DELETE FROM notes WHERE id = ?", (note_id,))

    def delete_all_notes(self) -> None:
        self._exec("DELETE FROM notes")

    # ---- hafıza ----
    def add_memory(self, content: str, kind: str = PERSONAL, source: str = "user",
                   expires_at: str | None = None) -> int:
        """kind: personal (kullanıcı hakkında) | knowledge (genel bilgi) | preference (davranış tercihi)."""
        return self._exec("INSERT INTO memories (content, created_at, kind, source, expires_at) VALUES (?, ?, ?, ?, ?)",
                          (content.strip(), _now(), kind, source, expires_at)).lastrowid

    _ACTIVE = "(expires_at IS NULL OR expires_at > ?)"

    def list_memories(self, kind: str | None = None, include_expired: bool = False) -> list[tuple[int, str, str]]:
        where, args = [], []
        if kind:
            where.append("kind = ?")
            args.append(kind)
        if not include_expired:
            where.append(self._ACTIVE)
            args.append(_now())
        sql = "SELECT id, content, created_at FROM memories"
        if where:
            sql += " WHERE " + " AND ".join(where)
        return self._all(sql + " ORDER BY id", tuple(args))

    def kinds(self) -> dict[int, str]:
        return dict(self._all("SELECT id, kind FROM memories"))

    def sources(self) -> dict[int, str]:
        return dict(self._all("SELECT id, source FROM memories"))

    def is_duplicate(self, content: str, threshold: float = 0.8) -> bool:
        """Aynı bilgi zaten kayıtlı mı? (kelime köklerinin çoğu ortaksa)"""
        new = _stems(content)
        if not new:
            return True
        for _, existing, _ in self.list_memories():
            old = _stems(existing)
            if old and len(new & old) / len(new) >= threshold:
                return True
        return False

    def learned_names(self, limit: int = 40) -> list[str]:
        """Kayıtlardaki özel adlar (cümle başı olmayan büyük harfli kelimeler, ekleri atılmış).
        Konuşma tanımaya ipucu olarak ve yazım düzeltmede kullanılır: öğretilen "Bornova" doğru yazılsın."""
        names: list[str] = []
        for _, content, _ in reversed(self.list_memories()):
            for i, word in enumerate(re.findall(r"[\wçğıöşüÇĞİÖŞÜ'’]+", content)):
                base = re.split(r"['’]", word)[0]
                # Cümle başındaki büyük harf her zaman özel ad değildir ("Bu", "Annemin"); yaygınları atla
                if i == 0 and tr_lower(base) in _SENTENCE_STARTERS:
                    continue
                if len(base) >= 3 and base[0].isupper() and base not in names:
                    names.append(base)
        return names[:limit]

    def delete_memory(self, memory_id: int) -> None:
        self._exec("DELETE FROM memories WHERE id = ?", (memory_id,))

    def delete_all_memories(self) -> None:
        self._exec("DELETE FROM memories")

    def _scored(self, query: str) -> tuple[set[str], list[tuple[int, int, str]]]:
        """Türkçe ekler için kelimelerin ilk 4 harfi (kök yaklaşımı) aranır; soru kalıpları sayılmaz."""
        words = "".join(ch if ch.isalnum() else " " for ch in tr_lower(query)).split()
        stems = {w[:4] for w in words if len(w) >= 3} - STOP_STEMS
        scored = []
        for mid, content, _ in self.list_memories():
            text = tr_lower(content)
            score = sum(1 for s in stems if s in text)
            if score:
                scored.append((score, mid, content))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return stems, scored

    def find_memory(self, query: str) -> tuple[int, str] | None:
        """Silme komutu için en iyi eşleşme; kelimelerin en az yarısı eşleşmeli."""
        stems, scored = self._scored(query)
        if not scored or scored[0][0] < max(1, (len(stems) + 1) // 2):
            return None
        return scored[0][1], scored[0][2]

    def relevant_memories(self, query: str, limit: int = 5) -> list[str]:
        """Soruyla ortak anlamlı kelimesi olan kayıtlar (modele yalnızca bunlar verilir)."""
        return [content for _, _, content in self._scored(query)[1][:limit]]

    def relevant_entries(self, query: str, limit: int = 6) -> list[tuple[str, str]]:
        """(içerik, tür) — kişisel bilgiler ve öğretilen bilgiler modele farklı çerçeveyle verilir."""
        kinds = self.kinds()
        return [(content, kinds.get(mid, PERSONAL)) for _, mid, content in self._scored(query)[1][:limit]]
