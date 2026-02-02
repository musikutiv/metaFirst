"""SQLAlchemy models for the discovery index."""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Index, UniqueConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

# Separate Base for discovery module (uses its own DB)
DiscoveryBase = declarative_base()


class Visibility(str, enum.Enum):
    """Visibility levels for discovery index.

    - PRIVATE: Only visible to members of the owning supervisor
    - INSTITUTION: Visible to any authenticated user
    - PUBLIC: Visible to anyone (no auth required)
    """
    PRIVATE = "PRIVATE"
    INSTITUTION = "INSTITUTION"
    PUBLIC = "PUBLIC"


class IndexedSample(DiscoveryBase):
    """Indexed sample metadata for federated discovery."""

    __tablename__ = "indexed_samples"

    id = Column(Integer, primary_key=True, index=True)

    # Origin tracking
    origin = Column(String(255), nullable=False)  # e.g., "supervisor-a.example.com"
    origin_supervisor_id = Column(Integer, nullable=True)  # Supervisor ID for membership checks
    origin_project_id = Column(Integer, nullable=False)
    origin_sample_id = Column(Integer, nullable=False)

    # Versioning
    rdmp_version = Column(Integer, nullable=True)
    release_id = Column(String(255), nullable=True)

    # Visibility for access control
    visibility = Column(String(20), default=Visibility.PUBLIC.value, nullable=False)

    # Full metadata as JSON string
    metadata_json = Column(Text, nullable=True)

    # Flattened text for search (concatenation of searchable fields)
    search_text = Column(Text, nullable=True)

    # Timestamps
    indexed_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("origin", "origin_project_id", "origin_sample_id", name="uq_origin_sample"),
        Index("ix_indexed_samples_visibility", "visibility"),
        Index("ix_indexed_samples_origin", "origin"),
    )
