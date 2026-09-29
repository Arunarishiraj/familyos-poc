import json
import threading

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from . import auth, intake, stage4, storage
from .gmail_connector import router as gmail_router
from .sms_categorizer import router as sms_router

app = FastAPI()
app.include_router(gmail_router)
app.include_router(sms_router)
_lock = threading.Lock()


class Reg(BaseModel):
    name: str = ""
    email: str
    password: str
    invite: str = ""


class Log(BaseModel):
    email: str
    password: str


class Item(BaseModel):
    ref: str | None = None
    name: str = "item"
    kind: str = "txt"          # "txt" or "ics"
    content: str


class Items(BaseModel):
    source_system: str = "Mobile App"
    items: list[Item]


@app.post("/auth/register")
def register(b: Reg):
    return auth.register(b.name, b.email, b.password, b.invite)


@app.post("/auth/login")
def login(b: Log):
    return auth.login(b.email, b.password)


@app.get("/api/sync/known")
def known(source: str, user=Depends(auth.current_user)):
    return auth.known_refs(user["sub"], source)


@app.post("/api/ingest")
async def api_ingest(source_system: str = Form("Mobile App"),
                     message: str = Form(""),
                     refs: str = Form("[]"),
                     files: list[UploadFile] = File(default=[]),
                     user=Depends(auth.current_user)):
    ref_list = json.loads(refs)
    out = []
    for i, f in enumerate(files):
        name = intake.safe(f.filename or "file")
        dest = intake.save(await f.read(), name)
        ref = ref_list[i] if i < len(ref_list) else None
        r = await run_in_threadpool(intake.run, dest, user, source_system, ref)
        out.append({"file": name, **r})
    if message.strip():
        dest = intake.save(message.encode("utf-8"), "message.txt")
        r = await run_in_threadpool(intake.run, dest, user, source_system)
        out.append({"file": "message.txt", **r})
    return {"results": out}


@app.post("/api/ingest_text")
async def ingest_text(b: Items, user=Depends(auth.current_user)):
    out = []
    for it in b.items:
        if not it.content.strip():
            continue
        ext = "ics" if it.kind == "ics" else "txt"
        dest = intake.save(it.content.encode("utf-8"), f"{it.name}.{ext}")
        r = await run_in_threadpool(intake.run, dest, user, b.source_system, it.ref)
        out.append({"file": it.name, **r})
    return {"results": out}


def _stage4_job():
    if _lock.acquire(blocking=False):      # only one Stage 4 run at a time
        try:
            stage4.run()
        finally:
            _lock.release()


@app.post("/api/process")
def process(bg: BackgroundTasks, user=Depends(auth.current_user)):
    bg.add_task(_stage4_job)
    return {"started": True}


@app.get("/api/artifacts")
def artifacts(user=Depends(auth.current_user)):
    with storage._conn() as c:
        rows = c.execute(
            "SELECT artifact_id, source_system, source_type, doc_type, title, "
            "status FROM artifacts WHERE family_id=? "
            "ORDER BY created_at DESC LIMIT 30", (user["fam"],)).fetchall()
    keys = ["id", "source", "type", "doc_type", "title", "status"]
    return [dict(zip(keys, r)) for r in rows]
