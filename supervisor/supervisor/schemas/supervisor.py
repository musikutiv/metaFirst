"""Supervisor schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


class SupervisorBase(BaseModel):
    """Base supervisor schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class SupervisorCreate(SupervisorBase):
    """Supervisor creation schema."""

    supervisor_db_dsn: str | None = Field(
        None,
        description="DSN for the supervisor's operational database. "
        "Example: sqlite:///./supervisor_1_ops.db"
    )


class SupervisorUpdate(BaseModel):
    """Supervisor update schema."""

    name: str | None = None
    description: str | None = None
    supervisor_db_dsn: str | None = Field(
        None,
        description="DSN for the supervisor's operational database"
    )


class Supervisor(SupervisorBase):
    """Supervisor response schema."""

    id: int
    created_at: datetime
    is_active: bool
    supervisor_db_dsn: str | None = None

    class Config:
        from_attributes = True
