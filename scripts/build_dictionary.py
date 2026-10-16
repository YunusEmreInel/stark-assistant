"""İngilizce → Türkçe sözlüğü oluşturur: ~/.stark/models/sozluk.db (bir kez çalıştırılır, ~10-20 dk).

Kaynak: Vikisözlük (CC BY-SA), kaikki.org'un Wiktextract çıktıları:
- Türkçe Vikisözlük: İngilizce sözcüklerin Türkçe açıklamaları (anlam anlam).
- İngilizce Wiktionary: sözcüklerin anlamlarına göre Türkçe çeviri tabloları ve çekimli biçimler (went → go).
Dosyalar diske indirilmez; akış hâlinde okunup yalnızca gereken kısımlar saklanır.

Kullanım: .venv\\Scripts\\python.exe scripts\\build_dictionary.py
"""
import gzip
import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from stark.config import MODELS_DIR  # noqa: E402

TR_URL = "https://kaikki.org/trwiktionary/raw-wiktextract-data.jsonl.gz"
EN_URL = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl.gz"
SKIP_POS = {"name", "abbrev", "symbol", "character", "proverb"}


def stream(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Stark-dictionary-builder"})
    with urllib.request.urlopen(req, timeout=60) as resp, gzip.GzipFile(fileobj=resp) as gz:
        yield from gz


def build(path: Path) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript("""
        CREATE TABLE senses(word TEXT, pos TEXT, source TEXT, gloss TEXT, turkish TEXT, example TEXT, ord INT);
        CREATE TABLE forms(form TEXT, base TEXT, PRIMARY KEY(form, base)) WITHOUT ROWID;
        CREATE TABLE turkish(word TEXT PRIMARY KEY) WITHOUT ROWID;
    """)
    t0 = time.time()
    n = 0
    # 1) Türkçe Vikisözlük
    for line in stream(TR_URL):
        d = json.loads(line)
        lang, word, pos = d.get("lang_code"), d.get("word", ""), d.get("pos", "")
        if lang == "tr" and pos not in SKIP_POS:
            db.execute("INSERT OR IGNORE INTO turkish VALUES (?)", (word.lower(),))
        if lang != "en" or pos in SKIP_POS or not word:
            continue
        for i, s in enumerate(d.get("senses", [])):
            for f in s.get("form_of", []) or []:
                if f.get("word"):
                    db.execute("INSERT OR IGNORE INTO forms VALUES (?, ?)", (word.lower(), f["word"]))
            gloss = "; ".join(s.get("glosses", []))
            if gloss and not s.get("form_of"):
                ex = next((e.get("text", "") for e in s.get("examples", []) if e.get("text")), "")
                db.execute("INSERT INTO senses VALUES (?,?,?,?,?,?,?)", (word, pos, "tr", "", gloss, ex, i))
                n += 1
    db.commit()
    print(f"Türkçe Vikisözlük: {n} anlam ({time.time() - t0:.0f} sn)", flush=True)

    # 2) İngilizce Wiktionary: Türkçe çeviriler + çekimli biçimler
    n = 0
    for k, line in enumerate(stream(EN_URL)):
        if k % 200000 == 0:
            print(f"  {k} satır, {n} çeviri anlamı ({time.time() - t0:.0f} sn)", flush=True)
        has_tr = b'"lang_code": "tr"' in line
        if b'"pos": "name"' in line[:400]:
            continue
        d = json.loads(line)
        word, pos = d.get("word", ""), d.get("pos", "")
        if pos in SKIP_POS or not word or word[:1].isupper() or len(word) > 40:
            continue
        own = 0
        for s in d.get("senses", []):
            for f in s.get("form_of", []) or []:
                if f.get("word") and f["word"] != word:
                    db.execute("INSERT OR IGNORE INTO forms VALUES (?, ?)", (word.lower(), f["word"]))
            tags = set(s.get("tags", []))
            gloss = "; ".join(s.get("glosses", []))
            # Türkçe karşılığı olmayan sözcükler için İngilizce tanım (dil modeli yalnızca bunu çevirir)
            if (not has_tr and gloss and own < 3 and not s.get("form_of") and not s.get("alt_of")
                    and not tags & {"obsolete", "archaic", "misspelling", "rare", "dialectal"}):
                db.execute("INSERT INTO senses VALUES (?,?,?,?,?,?,?)", (word, pos, "def", gloss[:200], "", "", own))
                own += 1
        if not has_tr:
            continue
        groups: dict[str, list[str]] = {}
        trs = list(d.get("translations", []))
        for s in d.get("senses", []):
            for t in s.get("translations", []) or []:
                trs.append({**t, "sense": t.get("sense") or "; ".join(s.get("glosses", []))})
        for t in trs:
            if t.get("lang_code") == "tr" and t.get("word"):
                lst = groups.setdefault(t.get("sense", "") or "", [])
                if t["word"] not in lst:
                    lst.append(t["word"])
        for i, (sense, words) in enumerate(groups.items()):
            db.execute("INSERT INTO senses VALUES (?,?,?,?,?,?,?)", (word, pos, "en", sense, ", ".join(words), "", i))
            n += 1
    db.execute("CREATE INDEX senses_word ON senses(word COLLATE NOCASE)")
    db.execute("DELETE FROM senses WHERE source='def' AND lower(word) IN "
               "(SELECT lower(word) FROM senses WHERE source IN ('tr', 'en'))")
    db.execute("DELETE FROM forms WHERE base NOT IN (SELECT word FROM senses)")
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(path)
    print(f"Bitti: {path} ({path.stat().st_size / 1e6:.0f} MB, {time.time() - t0:.0f} sn)")


if __name__ == "__main__":
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    build(MODELS_DIR / "sozluk.db")
