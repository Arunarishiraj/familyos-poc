import re
import uuid
from pathlib import Path

from . import auth, storage
from .pipeline import ingest

INBOX = Path("data/inbox")
INBOX.mkdir(parents=True, exist_ok=True)


def safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[-80:] or "file"


def save(data: bytes, name: str) -> Path:
    dest = INBOX / f"{uuid.uuid4().hex[:8]}_{safe(name)}"
    dest.write_bytes(data)
    return dest


def run(path: Path, user: dict, source: str, ref: str | None = None) -> dict:
    """Run one file through Stages 1-3 and report what happened."""
    try:
        ingest(str(path), family_id=user["fam"], submitted_by=user["sub"],
               source_system=source)
    except Exception as e:                      # e.g. Ollama not running
        return {"event": "ERROR", "detail": str(e)[:200]}
    with storage._conn() as c:
        ev = c.execute("SELECT event, detail FROM audit_log "
                       "ORDER BY id DESC LIMIT 1").fetchone()
    if ref:
        auth.mark_synced(user["sub"], source, ref)
    return {"event": ev[0], "detail": ev[1]}
