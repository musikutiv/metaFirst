"""Sample and field value schemas."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class SampleBase(BaseModel):
    """Base sample schema."""

    sample_identifier: str = Field(..., min_length=1, max_length=255)


class SampleCreate(SampleBase):
    """Sample creation schema."""

    pass


class Sample(SampleBase):
    """Sample response schema."""

    id: int
    project_id: int
    visibility: str = "PRIVATE"
    created_at: datetime
    created_by: int

    class Config:
        from_attributes = True


class SampleWithFields(Sample):
    """Sample with field values."""

    fields: dict[str, Any] = {}
    completeness: dict[str, Any] = {}


class FieldValueSet(BaseModel):
    """Field value update."""

    value: Any


class SampleFieldValue(BaseModel):
    """Field value response."""

    id: int
    sample_id: int
    field_key: str
    value_json: Any
    value_text: str | None
    updated_at: datetime
    updated_by: int

    class Config:
        from_attributes = True
