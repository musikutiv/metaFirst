"""Operational database models.

These models are stored in per-supervisor databases for operational isolation.
They track runtime state: ingest runs, heartbeats, etc.

IMPORTANT: These models do NOT have foreign keys to central DB tables.
Project IDs are stored as plain integers for reference only.
"""

from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, BigInteger
from sqlalchemy.sql import func
from supervisor.operational.base import OperationalBase


class RunStatus(str, PyEnum):
    """Status of an ingest run."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class IngestRun(OperationalBase):
    """Record of an ingest operation.

    Tracks file ingestion batches for a project. This is operational state
    that lives in the supervisor's operational database.
    """

    __tablename__ = "ingest_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Reference to project (no FK - just an integer reference)
    project_id = Column(Integer, nullable=False, index=True)

    # Run timing
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # Status
    status = Column(
        Enum(RunStatus, values_callable=lambda x: [e.value for e in x]),
        default=RunStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Summary statistics
    file_count = Column(Integer, default=0, nullable=False)
    total_bytes = Column(BigInteger, default=0, nullable=False)
    error_count = Column(Integer, default=0, nullable=False)

    # Messages
    message = Column(Text, nullable=True)  # Summary or error message
    log_pointer = Column(Text, nullable=True)  # Path or URI to detailed logs

    # Metadata
    triggered_by = Column(String(255), nullable=True)  # "watcher", "manual", "api"
    ingestor_id = Column(String(255), nullable=True)  # Identifier of the ingestor instance

    def __repr__(self):
        return f"<IngestRun(id={self.id}, project_id={self.project_id}, status={self.status})>"


class HeartbeatStatus(str, PyEnum):
    """Status of an ingestor heartbeat."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class Heartbeat(OperationalBase):
    """Ingestor heartbeat record.

    Tracks the health and last-seen time of ingestor instances.
    Each ingestor registers itself with a unique ID.
    """

    __tablename__ = "heartbeats"

    id = Column(Integer, primary_key=True, index=True)

    # Ingestor identification
    ingestor_id = Column(String(255), nullable=False, unique=True, index=True)
    hostname = Column(String(255), nullable=True)

    # Health status
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(
        Enum(HeartbeatStatus, values_callable=lambda x: [e.value for e in x]),
        default=HeartbeatStatus.HEALTHY,
        nullable=False,
    )

    # Additional info
    message = Column(Text, nullable=True)
    watched_paths = Column(Text, nullable=True)  # JSON list of watched paths
    version = Column(String(50), nullable=True)  # Ingestor version

    def __repr__(self):
        return f"<Heartbeat(ingestor_id={self.ingestor_id}, status={self.status})>"
