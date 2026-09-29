import json
import sqlite3
from pathlib import Path

OBJECT_DIR = Path("data/objects")
DB_PATH = Path("data/familyos.db")


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS artifacts (
        artifact_id TEXT PRIMARY KEY, family_id TEXT, source_type TEXT,
        source_system TEXT, submitted_by TEXT, created_at TEXT, status TEXT,
        content_hash TEXT, object_path TEXT, size_bytes INTEGER,
        consent_scope TEXT, title TEXT, doc_type TEXT, tags TEXT, language TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, artifact_id TEXT,
        event TEXT, detail TEXT)""")
    return conn


def save_object(content_hash: str, ext: str, data: bytes) -> str:
    """Object storage: content-addressed file on disk."""
    folder = OBJECT_DIR / content_hash[:2]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{content_hash}{ext}"
    if not path.exists():
        path.write_bytes(data)
    return str(path)


def find_by_hash(family_id: str, content_hash: str):
    with _conn() as c:
        row = c.execute(
            "SELECT artifact_id FROM artifacts WHERE family_id=? AND content_hash=?",
            (family_id, content_hash)).fetchone()
    return row[0] if row else None


def insert_artifact(a) -> None:
    d = a.model_dump()
    d["tags"] = json.dumps(d["tags"])
    with _conn() as c:
        c.execute(f"INSERT INTO artifacts VALUES ({','.join('?'*len(d))})",
                  list(d.values()))


def audit(ts: str, artifact_id: str, event: str, detail: str = "") -> None:
    with _conn() as c:
        c.execute("INSERT INTO audit_log(ts,artifact_id,event,detail) VALUES (?,?,?,?)",
                  (ts, artifact_id, event, detail))
