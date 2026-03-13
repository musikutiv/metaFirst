"""Pydantic schemas for FileAnnotation API."""

import json
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator, model_validator

# ── Validation constants ────────────────────────────────────────────────────
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_KEY_MAX_LEN = 64
_INDEX_JSON_MAX_BYTES = 64 * 1024   # 64 KiB
_VALUE_JSON_MAX_BYTES = 64 * 1024   # 64 KiB
_VALUE_TEXT_MAX_BYTES = 32 * 1024   # 32 KiB


# ── Request schemas ─────────────────────────────────────────────────────────

class AnnotationCreateItem(BaseModel):
    """A single annotation to create within a batch request."""

    key: str
    sample_id: int | None = None
    index: Any = None          # Stored as index_json on the model
    value_json: Any = None
    value_text: str | None = None

    @field_validator("key")
    @classmethod
    def _validate_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("key must not be empty")
        if len(v) > _KEY_MAX_LEN:
            raise ValueError(f"key must be at most {_KEY_MAX_LEN} characters")
        if not _KEY_PATTERN.match(v):
            raise ValueError(
                "key may only contain letters (A-Z, a-z), digits (0-9), "
                "period (.), underscore (_), or hyphen (-)"
            )
        return v

    @field_validator("index", mode="before")
    @classmethod
    def _validate_index_size(cls, v: Any) -> Any:
        if v is not None and len(json.dumps(v).encode()) > _INDEX_JSON_MAX_BYTES:
            raise ValueError(
                f"index exceeds maximum serialised size of {_INDEX_JSON_MAX_BYTES} bytes"
            )
        return v

    @field_validator("value_json", mode="before")
    @classmethod
    def _validate_value_json_size(cls, v: Any) -> Any:
        if v is not None and len(json.dumps(v).encode()) > _VALUE_JSON_MAX_BYTES:
            raise ValueError(
                f"value_json exceeds maximum serialised size of {_VALUE_JSON_MAX_BYTES} bytes"
            )
        return v

    @field_validator("value_text")
    @classmethod
    def _validate_value_text_size(cls, v: str | None) -> str | None:
        if v is not None and len(v.encode()) > _VALUE_TEXT_MAX_BYTES:
            raise ValueError(
                f"value_text exceeds maximum size of {_VALUE_TEXT_MAX_BYTES} bytes"
            )
        return v

    @model_validator(mode="after")
    def _require_at_least_one_value(self) -> "AnnotationCreateItem":
        if self.value_json is None and self.value_text is None:
            raise ValueError(
                "at least one of value_json or value_text must be provided"
            )
        return self


class AnnotationsBatchCreate(BaseModel):
    """Batch of annotations to create atomically against a single RawDataItem."""

    annotations: list[AnnotationCreateItem]

    @field_validator("annotations")
    @classmethod
    def _non_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("annotations list must not be empty")
        return v


class AnnotationPatch(BaseModel):
    """Partial update for an existing annotation.

    Only fields present in the JSON body are applied; absent fields are not
    modified.  Send ``null`` explicitly to clear a nullable field.
    """

    sample_id: int | None = None
    index: Any = None
    value_json: Any = None
    value_text: str | None = None


# ── Response schema ─────────────────────────────────────────────────────────

class AnnotationResponse(BaseModel):
    """Serialised representation of a FileAnnotation row."""

    id: int
    raw_data_item_id: int
    key: str
    sample_id: int | None
    index: Any           # Sourced from model.index_json
    value_json: Any
    value_text: str | None
    created_at: datetime | None
    created_by: int
