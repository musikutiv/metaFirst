"""Project model."""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from supervisor.database import Base


class Project(Base):
    """Research project model."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    supervisor_id = Column(Integer, ForeignKey("supervisors.id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    supervisor = relationship("Supervisor", back_populates="projects")
    creator = relationship("User", back_populates="created_projects", foreign_keys=[created_by])
    memberships = relationship("Membership", back_populates="project", cascade="all, delete-orphan")
    storage_roots = relationship("StorageRoot", back_populates="project", cascade="all, delete-orphan")
    rdmp_versions = relationship("RDMPVersion", back_populates="project", cascade="all, delete-orphan")
    samples = relationship("Sample", back_populates="project", cascade="all, delete-orphan")
    raw_data_items = relationship("RawDataItem", back_populates="project", cascade="all, delete-orphan")
    releases = relationship("Release", back_populates="project", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}')>"
