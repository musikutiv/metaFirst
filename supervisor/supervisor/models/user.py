"""User model."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from supervisor.database import Base


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    memberships = relationship("Membership", back_populates="user", foreign_keys="[Membership.user_id]")
    supervisor_memberships = relationship("SupervisorMembership", back_populates="user", foreign_keys="[SupervisorMembership.user_id]")
    storage_mappings = relationship("StorageRootMapping", back_populates="user")
    created_projects = relationship("Project", back_populates="creator", foreign_keys="[Project.created_by]")
    audit_logs = relationship("AuditLog", back_populates="actor", foreign_keys="[AuditLog.actor_user_id]")
    activity_logs = relationship("LabActivityLog", back_populates="actor", foreign_keys="[LabActivityLog.actor_user_id]")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"
