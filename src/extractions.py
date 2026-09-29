import json
from . import storage


def _conn():
    c = storage._conn()
    c.execute("""CREATE TABLE IF NOT EXISTS extractions (
        artifact_id TEXT PRIMARY KEY, method TEXT, model TEXT,
        text TEXT, char_count INTEGER, created_at TEXT)""")
    return c


def pending():
    with _conn() as c:
        return c.execute(
            "SELECT artifact_id, source_type, object_path, doc_type "
            "FROM artifacts WHERE status='RECEIVED' ORDER BY created_at").fetchall()


def save(artifact_id, result, ts):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO extractions VALUES (?,?,?,?,?,?)",
                  (artifact_id, result.method, result.model,
                   result.text, len(result.text), ts))
        c.execute("UPDATE artifacts SET status='PROCESSED' WHERE artifact_id=?",
                  (artifact_id,))


def set_status(artifact_id, status):
    with _conn() as c:
        c.execute("UPDATE artifacts SET status=? WHERE artifact_id=?",
                  (status, artifact_id))


def set_classification(artifact_id, tags):
    with _conn() as c:
        c.execute("UPDATE artifacts SET title=?, doc_type=?, tags=?, language=? "
                  "WHERE artifact_id=?",
                  (tags.title, tags.doc_type, json.dumps(tags.tags),
                   tags.language, artifact_id))
