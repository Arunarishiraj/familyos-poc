import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import gateway, storage
from .models import InputArtifact
from .qwen_client import classify

TEXT_TYPES = {"TEXT", "EMAIL", "CALENDAR", "API"}  # Qwen text model can read these


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ingest(file: str, family_id="F001", submitted_by="M002",
           source_system="Mobile App") -> None:
    path = Path(file)
    print(f"\n=== {path.name} ===")
    data = path.read_bytes()
    artifact_id = "A" + uuid.uuid4().hex[:6].upper()

    try:
        # Stage 2: Ingestion Gateway
        gateway.check_consent(family_id, submitted_by)
        source_type = gateway.validate(path, data)
        gateway.scan(data)
        content_hash = gateway.sha256(data)

        existing = storage.find_by_hash(family_id, content_hash)
        if existing:
            storage.audit(now(), artifact_id, "DUPLICATE", f"same as {existing}")
            print(f"DUPLICATE of {existing}: skipped")
            return

        # Qwen: classify + tag (text-like inputs only for now)
        tags = None
        if source_type in TEXT_TYPES:
            tags = classify(data.decode("utf-8", errors="ignore"))
            if tags.suspicious:
                raise gateway.Rejected(f"Qwen flagged as suspicious: {tags.reason}")
            print(f"Qwen -> {tags.doc_type} | {tags.title} | {tags.tags} "
                  f"| conf={tags.confidence}")
        else:
            print(f"{source_type}: needs Stage 4 processing (OCR/ASR), no tags yet")

        # Stage 3: create InputArtifact and store
        object_path = storage.save_object(content_hash, path.suffix.lower(), data)
        artifact = InputArtifact(
            artifact_id=artifact_id, family_id=family_id, source_type=source_type,
            source_system=source_system, submitted_by=submitted_by,
            created_at=now(), status="RECEIVED", content_hash=content_hash,
            object_path=object_path, size_bytes=len(data),
            title=tags.title if tags else None,
            doc_type=tags.doc_type if tags else None,
            tags=tags.tags if tags else [],
            language=tags.language if tags else None,
        )
        storage.insert_artifact(artifact)
        storage.audit(now(), artifact_id, "RECEIVED", path.name)
        print(f"STORED as {artifact_id}")

    except gateway.Rejected as e:
        storage.audit(now(), artifact_id, "REJECTED", f"{path.name}: {e}")
        print(f"REJECTED: {e}")


if __name__ == "__main__":
    files = sys.argv[1:] or sorted(str(p) for p in Path("sample_inputs").iterdir())
    for f in files:
        ingest(f)
