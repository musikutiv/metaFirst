"""Project schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class ProjectCreate(ProjectBase):
    """Project creation schema."""

    supervisor_id: int = Field(..., description="ID of the supervisor that owns this project")


class ProjectUpdate(BaseModel):
    """Project update schema."""

    name: str | None = None
    description: str | None = None


class Project(ProjectBase):
    """Project response schema."""

    id: int
    created_at: datetime
    created_by: int
    supervisor_id: int
    is_active: bool

    class Config:
        from_attributes = True


class MembershipBase(BaseModel):
    """Base membership schema."""

    user_id: int
    role_name: str = Field(..., min_length=1, max_length=100)


class MembershipCreate(MembershipBase):
    """Membership creation schema."""

    pass


class MembershipUpdate(BaseModel):
    """Membership update schema."""

    role_name: str


class Membership(MembershipBase):
    """Membership response schema."""

    id: int
    project_id: int
    created_at: datetime
    created_by: int

    class Config:
        from_attributes = True
