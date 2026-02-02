"""RDMP (Research Data Management Plan) models."""

from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index, Enum
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from supervisor.database import Base


class RDMPStatus(str, PyEnum):
    """Status of an RDMP version."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class RDMPTemplate(Base):
    """RDMP template - reusable RDMP definitions."""

    __tablename__ = "rdmp_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    versions = relationship("RDMPTemplateVersion", back_populates="template", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<RDMPTemplate(id={self.id}, name='{self.name}')>"


class RDMPTemplateVersion(Base):
    """Versioned RDMP template."""

    __tablename__ = "rdmp_template_versions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("rdmp_templates.id", ondelete="CASCADE"), nullable=False)
    version_int = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_json = Column(JSON, nullable=False)  # Full RDMP structure

    # Relationships
    template = relationship("RDMPTemplate", back_populates="versions")
    creator = relationship("User")

    __table_args__ = (
        UniqueConstraint("template_id", "version_int", name="uq_template_version"),
        Index("ix_template_latest", "template_id", "version_int"),
    )

    def __repr__(self):
        return f"<RDMPTemplateVersion(template_id={self.template_id}, version={self.version_int})>"


class RDMPVersion(Base):
    """Project-specific RDMP version with status workflow.

    Lifecycle: DRAFT -> ACTIVE -> SUPERSEDED
    - Only one ACTIVE per project at a time
    - When a new RDMP is activated, the previous ACTIVE becomes SUPERSEDED
    """

    __tablename__ = "rdmp_versions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version_int = Column(Integer, nullable=False)
    status = Column(
        Enum(RDMPStatus, values_callable=lambda x: [e.value for e in x]),
        default=RDMPStatus.DRAFT,
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False, default="Untitled RDMP")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Set when activated
    rdmp_json = Column(JSON, nullable=False)  # Active RDMP for project
    provenance_json = Column(JSON, nullable=True)  # Template reference, changes, parameters

    # Retention and embargo settings
    retention_days = Column(Integer, nullable=True)  # Days to retain data after creation
    embargo_until = Column(DateTime(timezone=True), nullable=True)  # Data under embargo until this date

    # Relationships
    project = relationship("Project", back_populates="rdmp_versions")
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])
    releases = relationship("Release", back_populates="rdmp_version")
    ingest_run_records = relationship("IngestRunRecord", back_populates="rdmp_version")

    __table_args__ = (
        UniqueConstraint("project_id", "version_int", name="uq_project_rdmp_version"),
        Index("ix_project_rdmp_latest", "project_id", "version_int"),
        Index("ix_project_rdmp_status", "project_id", "status"),
    )

    def __repr__(self):
        return f"<RDMPVersion(project_id={self.project_id}, version={self.version_int}, status={self.status})>"


class IngestRunRecord(Base):
    """Central DB record of ingest runs with RDMP provenance.

    This table lives in the central DB and tracks which RDMP was active
    when an ingest run was created. The actual run state lives in the
    per-supervisor operational DB.
    """

    __tablename__ = "ingest_run_records"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    ops_run_id = Column(Integer, nullable=True)  # ID from per-supervisor operational DB
    rdmp_version_id = Column(Integer, ForeignKey("rdmp_versions.id"), nullable=True)  # Active RDMP at time of run
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    project = relationship("Project")
    rdmp_version = relationship("RDMPVersion", back_populates="ingest_run_records")
    creator = relationship("User")

    __table_args__ = (
        Index("ix_ingest_run_record_project", "project_id"),
    )

    def __repr__(self):
        return f"<IngestRunRecord(id={self.id}, project_id={self.project_id}, rdmp_version_id={self.rdmp_version_id})>"
