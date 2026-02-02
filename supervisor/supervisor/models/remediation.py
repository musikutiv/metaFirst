"""Remediation task models for RDMP soft enforcement."""

from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from supervisor.database import Base


class IssueType(str, PyEnum):
    """Types of issues that can trigger remediation tasks."""
    RETENTION_EXCEEDED = "retention_exceeded"  # Data past retention period
    EMBARGO_ACTIVE = "embargo_active"  # Data still under embargo


class TaskStatus(str, PyEnum):
    """Status of a remediation task."""
    PENDING = "PENDING"      # Newly created, awaiting acknowledgment
    ACKED = "ACKED"          # Acknowledged by a member
    APPROVED = "APPROVED"    # Approved for execution by steward/PI
    DISMISSED = "DISMISSED"  # Dismissed (no action needed)
    EXECUTED = "EXECUTED"    # Action has been executed


class RemediationTask(Base):
    """Remediation task for RDMP policy enforcement.

    Tasks are created when automated checks detect policy violations
    (e.g., data past retention period). They follow a workflow:
    PENDING -> ACKED -> APPROVED -> EXECUTED
              or     -> DISMISSED
    """

    __tablename__ = "remediation_tasks"

    id = Column(Integer, primary_key=True, index=True)
    supervisor_id = Column(Integer, ForeignKey("supervisors.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    sample_id = Column(Integer, ForeignKey("samples.id", ondelete="CASCADE"), nullable=True)

    issue_type = Column(String(50), nullable=False)
    status = Column(
        String(20),
        default=TaskStatus.PENDING.value,
        nullable=False,
    )
    description = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON string with additional context

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Workflow tracking
    acked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acked_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    supervisor = relationship("Supervisor")
    project = relationship("Project")
    sample = relationship("Sample")
    acker = relationship("User", foreign_keys=[acked_by])
    approver = relationship("User", foreign_keys=[approved_by])
    dismisser = relationship("User", foreign_keys=[dismissed_by])

    __table_args__ = (
        Index("ix_remediation_tasks_supervisor", "supervisor_id"),
        Index("ix_remediation_tasks_project", "project_id"),
        Index("ix_remediation_tasks_status", "status"),
    )

    def __repr__(self):
        return f"<RemediationTask(id={self.id}, type={self.issue_type}, status={self.status})>"
