import time
from pathlib import Path

from . import extractions, storage, processors
from .pipeline import now
from .qwen_client import classify


def run() -> None:
    rows = extractions.pending()
    print(f"{len(rows)} artifact(s) waiting for Stage 4")
    for artifact_id, source_type, object_path, doc_type in rows:
        print(f"\n=== {artifact_id} ({source_type}) ===")
        t0 = time.time()
        try:
            result = processors.process(source_type, Path(object_path))
            if not result.text.strip():
                raise ValueError("no text extracted")
            extractions.save(artifact_id, result, now())
            storage.audit(now(), artifact_id, "PROCESSED",
                          f"{result.method} {result.model or ''}".strip())
            preview = result.text[:150].replace("\n", " | ")
            print(f"{result.method}: {len(result.text)} chars in {time.time()-t0:.1f}s")
            print(f"text: {preview}")

            if doc_type is None:
                tags = classify(result.text)
                if tags.suspicious:
                    extractions.set_status(artifact_id, "QUARANTINED")
                    storage.audit(now(), artifact_id, "QUARANTINED", tags.reason)
                    print(f"QUARANTINED: {tags.reason}")
                    continue
                extractions.set_classification(artifact_id, tags)
                print(f"Qwen -> {tags.doc_type} | {tags.title}")

        except NotImplementedError as e:
            storage.audit(now(), artifact_id, "SKIPPED", str(e))
            print(f"SKIPPED: {e}")
        except Exception as e:
            extractions.set_status(artifact_id, "FAILED")
            storage.audit(now(), artifact_id, "FAILED", str(e))
            print(f"FAILED: {e}")


if __name__ == "__main__":
    run()
