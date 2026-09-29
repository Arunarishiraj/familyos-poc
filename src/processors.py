import io
import email
import email.policy
from dataclasses import dataclass
from pathlib import Path

import ollama
import pymupdf
from PIL import Image

VL_MODEL = "qwen2.5vl:3b"
MAX_SIDE = 1280

OCR_PROMPT = (
    "Extract all the text visible in this image exactly as written. "
    "Keep the line breaks. Output only the extracted text, with no commentary."
)


@dataclass
class Result:
    text: str
    method: str
    model: str | None = None


def _shrink(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def read_image(image_bytes: bytes) -> str:
    resp = ollama.chat(
        model=VL_MODEL,
        messages=[{"role": "user", "content": OCR_PROMPT,
                   "images": [_shrink(image_bytes)]}],
        options={"temperature": 0},
    )
    return resp.message.content.strip()


def process_text(path: Path) -> Result:
    return Result(path.read_text(encoding="utf-8", errors="ignore"), "text_passthrough")


def process_email(path: Path) -> Result:
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    body_part = msg.get_body(preferencelist=("plain", "html"))
    body = body_part.get_content() if body_part else ""
    attachments = [p.get_filename() for p in msg.iter_attachments() if p.get_filename()]
    lines = [f"From: {msg['From']}", f"To: {msg['To']}",
             f"Subject: {msg['Subject']}", f"Date: {msg['Date']}"]
    if attachments:
        lines.append("Attachments: " + ", ".join(attachments))
    lines += ["", body.strip()]
    return Result("\n".join(lines), "email_parser")


def process_ics(path: Path) -> Result:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = raw.replace("\r\n ", "").replace("\n ", "")
    events, cur = [], None
    for line in raw.splitlines():
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key, val = line.split(":", 1)
            cur[key.split(";")[0]] = val
    out = []
    for e in events:
        out.append(f"EVENT: {e.get('SUMMARY', '')} | start {e.get('DTSTART', '')} "
                   f"| end {e.get('DTEND', '')} | location {e.get('LOCATION', '')} "
                   f"| notes {e.get('DESCRIPTION', '')}")
    return Result("\n".join(out), "ics_parser")


def process_image(path: Path) -> Result:
    return Result(read_image(path.read_bytes()), "qwen_vl_ocr", VL_MODEL)


def process_pdf(path: Path) -> Result:
    doc = pymupdf.open(path)
    pages, methods = [], set()
    for page in doc:
        text = page.get_text().strip()
        if len(text) >= 20:
            methods.add("pdf_text")
        else:
            text = read_image(page.get_pixmap(dpi=150).tobytes("png"))
            methods.add("pdf_qwen_vl_ocr")
        pages.append(text)
    model = VL_MODEL if "pdf_qwen_vl_ocr" in methods else None
    return Result("\n\n".join(pages), "+".join(sorted(methods)), model)


def process(source_type: str, path: Path) -> Result:
    handlers = {"TEXT": process_text, "EMAIL": process_email,
                "CALENDAR": process_ics, "IMAGE": process_image,
                "PDF": process_pdf}
    if source_type not in handlers:
        raise NotImplementedError(f"no processor yet for {source_type}")
    return handlers[source_type](path)
