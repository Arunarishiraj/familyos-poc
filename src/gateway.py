import hashlib
from pathlib import Path

MAX_SIZE = 5 * 1024 * 1024  # 5 MB for the POC
ALLOWED = {
    ".txt": "TEXT", ".eml": "EMAIL", ".pdf": "PDF",
    ".jpg": "IMAGE", ".jpeg": "IMAGE", ".png": "IMAGE",
    ".mp3": "AUDIO", ".wav": "AUDIO", ".ics": "CALENDAR",
    ".json": "API",
}
BLOCKED = {".exe", ".bat", ".sh", ".js", ".dll"}
FAKE_MALWARE_MARKERS = [b"X-FAKE-MALWARE-TEST-STRING"]  # stand-in for antivirus

# Simple member registry (in reality: a DB)
MEMBERS = {
    "F001": {"M001": "Mom", "M002": "Dad", "M003": "Meera"},
}


class Rejected(Exception):
    pass


def validate(path: Path, data: bytes) -> str:
    ext = path.suffix.lower()
    if ext in BLOCKED:
        raise Rejected(f"blocked file type {ext}")
    if ext not in ALLOWED:
        raise Rejected(f"unsupported file type {ext}")
    if len(data) == 0:
        raise Rejected("empty file")
    if len(data) > MAX_SIZE:
        raise Rejected("file too large")
    return ALLOWED[ext]  # source_type


def scan(data: bytes) -> None:
    for marker in FAKE_MALWARE_MARKERS:
        if marker in data:
            raise Rejected("threat signature detected")


def check_consent(family_id: str, member_id: str) -> None:
    if member_id in MEMBERS.get(family_id, {}):
        return
    import sqlite3
    from . import storage
    ok = None
    try:
        with storage._conn() as c:
            ok = c.execute("SELECT 1 FROM users WHERE member_id=? AND family_id=?",
                           (member_id, family_id)).fetchone()
    except sqlite3.OperationalError:
        pass
    if not ok:
        raise Rejected(f"{member_id} is not a member of {family_id}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
