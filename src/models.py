from typing import Literal
from pydantic import BaseModel, Field


class InputArtifact(BaseModel):
    artifact_id: str
    family_id: str
    source_type: str          # TEXT / PDF / IMAGE / AUDIO / EMAIL ...
    source_system: str        # e.g. "Mobile App"
    submitted_by: str         # member id
    created_at: str
    status: str = "RECEIVED"
    content_hash: str
    object_path: str
    size_bytes: int
    consent_scope: str = "family"
    title: str | None = None
    doc_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    language: str | None = None


class QwenTags(BaseModel):
    """What we ask Qwen to return (forced JSON schema)."""
    doc_type: Literal["bill", "medical", "school", "travel",
                      "appointment", "shopping", "other"]
    title: str
    tags: list[str]
    language: str
    suspicious: bool
    reason: str
    confidence: float
