"""Supervisor model.

A supervisor represents a tenant in the multi-tenant architecture.
Each supervisor owns projects and has an isolated operational database.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from supervisor.database import Base


class Supervisor(Base):
    """Supervisor (tenant) model.

    Supervisors are the top-level organizational unit. Each supervisor:
    - Owns one or more projects
    - Has supervisor-scoped roles (steward, researcher, PI)
    - Maintains an isolated operational database (runs, heartbeats, logs)
    - Can share metadata via the discovery index
    """

    __tablename__ = "supervisors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True, nullable=False)

    # Operational database DSN (per-supervisor isolation)
    # If null, operational features are disabled for this supervisor.
    # Example SQLite: "sqlite:///./supervisor_1_ops.db"
    # Example Postgres: "postgresql://user:pass@host/metafirst_sup_1"
    supervisor_db_dsn = Column(Text, nullable=True)

    # Primary steward - the designated steward with ultimate responsibility
    # Nullable until assigned. Only one primary steward per supervisor.
    primary_steward_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Automation settings
    # If False, the execute endpoint for remediation tasks returns 403
    enable_automated_execution = Column(Boolean, default=False, nullable=False)

    # Relationships
    projects = relationship("Project", back_populates="supervisor", cascade="all, delete-orphan")
    memberships = relationship("SupervisorMembership", back_populates="supervisor", cascade="all, delete-orphan")
    primary_steward = relationship("User", foreign_keys=[primary_steward_user_id])
    activity_logs = relationship("LabActivityLog", back_populates="lab", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Supervisor(id={self.id}, name='{self.name}')>"
