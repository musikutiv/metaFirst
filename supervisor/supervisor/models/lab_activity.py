"""Lab activity log model for tracking governance and operational events."""

from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from supervisor.database import Base


class ActivityEventType(str, PyEnum):
    """Types of activity events tracked at the lab level.

    EXTENSION RULE: Values are stored as strings in the database (not DB enums).
    New event types can be added append-only without migrations. Never rename
    or remove existing values as historical logs reference them.
    """
    # Role changes
    MEMBER_ADDED = "MEMBER_ADDED"
    MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED"
    MEMBER_REMOVED = "MEMBER_REMOVED"

    # RDMP transitions
    RDMP_CREATED = "RDMP_CREATED"
    RDMP_ACTIVATED = "RDMP_ACTIVATED"
    RDMP_SUPERSEDED = "RDMP_SUPERSEDED"

    # Project operational state
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_OPERATIONAL = "PROJECT_OPERATIONAL"
    PROJECT_DISABLED = "PROJECT_DISABLED"

    # Metadata visibility
    VISIBILITY_CHANGED = "VISIBILITY_CHANGED"

    # Storage/Ingestor
    STORAGE_ROOT_CREATED = "STORAGE_ROOT_CREATED"
    STORAGE_ROOT_UPDATED = "STORAGE_ROOT_UPDATED"
    STORAGE_ROOT_DISABLED = "STORAGE_ROOT_DISABLED"


class EntityType(str, PyEnum):
    """Types of entities that can be the subject of an activity."""
    MEMBER = "MEMBER"
    PROJECT = "PROJECT"
    RDMP = "RDMP"
    SAMPLE = "SAMPLE"
    STORAGE_ROOT = "STORAGE_ROOT"


class LabActivityLog(Base):
    """Lab-scoped activity log for governance and operational events.

    This table captures key events that affect lab governance, including:
    - Member role changes
    - RDMP lifecycle transitions
    - Project operational state changes
    - Metadata visibility changes
    - Storage root configuration changes

    Each event includes who performed the action (actor), when it happened,
    what was affected, and optionally why (reason). For state changes,
    before/after snapshots are captured when available.
    """

    __tablename__ = "lab_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    lab_id = Column(Integer, ForeignKey("supervisors.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Event classification
    event_type = Column(String(50), nullable=False)  # ActivityEventType value
    entity_type = Column(String(50), nullable=False)  # EntityType value
    entity_id = Column(Integer, nullable=False)

    # Human-readable summary
    summary_text = Column(String(500), nullable=False)

    # Optional reason (required for sensitive actions)
    reason_text = Column(Text, nullable=True)

    # State snapshots (JSON serialized)
    before_json = Column(JSON, nullable=True)
    after_json = Column(JSON, nullable=True)

    # Relationships
    lab = relationship("Supervisor", back_populates="activity_logs")
    actor = relationship("User", back_populates="activity_logs", foreign_keys=[actor_user_id])

    __table_args__ = (
        Index("ix_lab_activity_lab_time", "lab_id", "created_at"),
        Index("ix_lab_activity_entity", "entity_type", "entity_id"),
        Index("ix_lab_activity_event_type", "event_type"),
    )

    def __repr__(self):
        return f"<LabActivityLog(id={self.id}, event='{self.event_type}', entity='{self.entity_type}:{self.entity_id}')>"
