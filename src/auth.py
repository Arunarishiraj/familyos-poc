import hashlib
import os
import secrets
import sqlite3
import time

import jwt
from fastapi import Header, HTTPException

from . import storage

SECRET = os.environ.get("FAMILYOS_JWT_SECRET", "")
INVITE = os.environ.get("FAMILYOS_INVITE", "")
FAMILY = "F001"


def _c():
    c = storage._conn()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        member_id TEXT PRIMARY KEY, family_id TEXT, name TEXT,
        email TEXT UNIQUE, pw_salt BLOB, pw_hash BLOB)""")
    c.execute("""CREATE TABLE IF NOT EXISTS synced_refs (
        member_id TEXT, source TEXT, ref TEXT,
        PRIMARY KEY (member_id, source, ref))""")
    c.execute("""CREATE TABLE IF NOT EXISTS gmail_tokens (
        member_id TEXT PRIMARY KEY, token BLOB)""")
    return c


_c().close()


def _hash(pw: str, salt: bytes) -> bytes:
    return hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)


def _token(member_id: str, family_id: str) -> str:
    return jwt.encode({"sub": member_id, "fam": family_id,
                       "exp": int(time.time()) + 30 * 86400},
                      SECRET, algorithm="HS256")


def register(name, email, password, invite):
    if not SECRET:
        raise HTTPException(500, "server secret not set")
    if not INVITE or not secrets.compare_digest(invite, INVITE):
        raise HTTPException(403, "bad invite code")
    if len(password) < 8:
        raise HTTPException(400, "password must be 8+ characters")
    member_id = "M" + secrets.token_hex(3).upper()
    salt = os.urandom(16)
    try:
        with _c() as c:
            c.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",
                      (member_id, FAMILY, name, email.lower(), salt,
                       _hash(password, salt)))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "email already registered")
    return {"token": _token(member_id, FAMILY), "member_id": member_id,
            "name": name}


def login(email, password):
    with _c() as c:
        row = c.execute("SELECT member_id, family_id, name, pw_salt, pw_hash "
                        "FROM users WHERE email=?", (email.lower(),)).fetchone()
    if not row or not secrets.compare_digest(_hash(password, row[3]), row[4]):
        raise HTTPException(401, "wrong email or password")
    return {"token": _token(row[0], row[1]), "member_id": row[0], "name": row[2]}


def decode(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])


def current_user(authorization: str = Header("")) -> dict:
    try:
        return decode(authorization.removeprefix("Bearer "))
    except Exception:
        raise HTTPException(401, "invalid or expired token")


def known_refs(member_id: str, source: str) -> list:
    with _c() as c:
        rows = c.execute("SELECT ref FROM synced_refs WHERE member_id=? "
                         "AND source=?", (member_id, source)).fetchall()
    return [r[0] for r in rows]


def mark_synced(member_id: str, source: str, ref: str) -> None:
    with _c() as c:
        c.execute("INSERT OR IGNORE INTO synced_refs VALUES (?,?,?)",
                  (member_id, source, ref))


def save_gmail_token(member_id: str, blob: bytes) -> None:
    with _c() as c:
        c.execute("INSERT OR REPLACE INTO gmail_tokens VALUES (?,?)",
                  (member_id, blob))


def get_gmail_token(member_id: str):
    with _c() as c:
        row = c.execute("SELECT token FROM gmail_tokens WHERE member_id=?",
                        (member_id,)).fetchone()
    return row[0] if row else None
