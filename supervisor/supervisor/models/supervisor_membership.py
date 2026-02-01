"""Supervisor membership model - links users to supervisors with roles."""

from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from supervisor.database import Base


class SupervisorRole(str, PyEnum):
    """Supervisor-scoped roles.

    - PI: Principal Investigator, highest authority. Can approve RDMPs, manage stewards.
    - STEWARD: Data steward, manages operational aspects. Can configure DSN, manage researchers.
    - RESEARCHER: Can create projects, ingest data, manage samples within their projects.
    """
    PI = "PI"
    STEWARD = "STEWARD"
    RESEARCHER = "RESEARCHER"


class SupervisorMembership(Base):
    """Supervisor membership with role assignment.

    Links users to supervisors with a specific role. This is separate from
    project-level memberships which are defined by RDMPs.
    """

    __tablename__ = "supervisor_memberships"

    id = Column(Integer, primary_key=True, index=True)
    supervisor_id = Column(Integer, ForeignKey("supervisors.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(
        Enum(SupervisorRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for system-created

    # Relationships
    supervisor = relationship("Supervisor", back_populates="memberships")
    user = relationship("User", back_populates="supervisor_memberships", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("supervisor_id", "user_id", name="uq_supervisor_user"),
        Index("ix_supervisor_membership_supervisor_user", "supervisor_id", "user_id"),
    )

    def __repr__(self):
        return f"<SupervisorMembership(supervisor_id={self.supervisor_id}, user_id={self.user_id}, role='{self.role}')>"
