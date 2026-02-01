"""Operational database module for per-supervisor isolation.

This module provides:
- Separate SQLAlchemy Base for operational tables
- Per-supervisor database routing
- Models for runs, heartbeats, and operational state

Operational state is stored in a supervisor-specific database,
separate from the central metadata database.
"""

from supervisor.operational.base import OperationalBase
from supervisor.operational.models import IngestRun, Heartbeat
from supervisor.operational.database import (
    get_operational_session,
    get_operational_engine,
    init_operational_db,
    operational_session_scope,
    clear_engine_cache,
    OperationalDBError,
    MissingDSNError,
)

__all__ = [
    "OperationalBase",
    "IngestRun",
    "Heartbeat",
    "get_operational_session",
    "get_operational_engine",
    "init_operational_db",
    "operational_session_scope",
    "clear_engine_cache",
    "OperationalDBError",
    "MissingDSNError",
]
