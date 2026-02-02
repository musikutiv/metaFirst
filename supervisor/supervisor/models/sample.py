"""Sample and field value models - dynamic metadata storage."""

from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index, Enum
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from supervisor.database import Base


class MetadataVisibility(str, PyEnum):
    """Visibility level for metadata in discovery.

    - PRIVATE: Only visible to members of the owning supervisor
    - INSTITUTION: Visible to any authenticated user
    - PUBLIC: Visible to anyone (no auth required)
    """
    PRIVATE = "PRIVATE"
    INSTITUTION = "INSTITUTION"
    PUBLIC = "PUBLIC"


class Sample(Base):
    """Sample in a project."""

    __tablename__ = "samples"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    sample_identifier = Column(String(255), nullable=False)  # User-facing ID
    visibility = Column(
        Enum(MetadataVisibility, values_callable=lambda x: [e.value for e in x]),
        default=MetadataVisibility.PRIVATE,
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="samples")
    creator = relationship("User")
    field_values = relationship("SampleFieldValue", back_populates="sample", cascade="all, delete-orphan")
    raw_data_items = relationship("RawDataItem", back_populates="sample")

    __table_args__ = (
        UniqueConstraint("project_id", "sample_identifier", name="uq_project_sample"),
        Index("ix_sample_project", "project_id"),
    )

    def __repr__(self):
        return f"<Sample(id={self.id}, identifier='{self.sample_identifier}')>"


class SampleFieldValue(Base):
    """Dynamic metadata field value for a sample (EAV pattern)."""

    __tablename__ = "sample_field_values"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(Integer, ForeignKey("samples.id", ondelete="CASCADE"), nullable=False)
    field_key = Column(String(255), nullable=False)  # Must match RDMP field key
    value_json = Column(JSON, nullable=True)  # Structured value
    value_text = Column(Text, nullable=True)  # Searchable text representation
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    sample = relationship("Sample", back_populates="field_values")
    updater = relationship("User")

    __table_args__ = (
        UniqueConstraint("sample_id", "field_key", name="uq_sample_field"),
        Index("ix_field_values_sample", "sample_id"),  # For eager loading
        Index("ix_field_values_search", "field_key", "value_text"),
    )

    def __repr__(self):
        return f"<SampleFieldValue(sample_id={self.sample_id}, key='{self.field_key}')>"
