"""Operational database routing and session management.

Provides per-supervisor database connections with engine caching.
"""

import threading
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from supervisor.operational.base import OperationalBase


class OperationalDBError(Exception):
    """Base exception for operational database errors."""
    pass


class MissingDSNError(OperationalDBError):
    """Raised when a supervisor has no operational database configured."""

    def __init__(self, supervisor_id: int, supervisor_name: str | None = None):
        self.supervisor_id = supervisor_id
        self.supervisor_name = supervisor_name
        name_part = f" ({supervisor_name})" if supervisor_name else ""
        super().__init__(
            f"Supervisor {supervisor_id}{name_part} has no operational database configured. "
            f"Set supervisor_db_dsn via API or run: mf supervisor-db init --supervisor {supervisor_id}"
        )


class SchemaNotInitializedError(OperationalDBError):
    """Raised when the operational database schema is not initialized."""

    def __init__(self, supervisor_id: int, dsn: str):
        self.supervisor_id = supervisor_id
        self.dsn = dsn
        super().__init__(
            f"Operational database for supervisor {supervisor_id} is not initialized. "
            f"Run: mf supervisor-db init --supervisor {supervisor_id}"
        )


class UnreachableDSNError(OperationalDBError):
    """Raised when the operational database cannot be reached."""

    def __init__(self, supervisor_id: int, dsn: str, original_error: Exception):
        self.supervisor_id = supervisor_id
        self.dsn = dsn
        self.original_error = original_error
        # Mask password in DSN for error message
        safe_dsn = _mask_password(dsn)
        super().__init__(
            f"Cannot connect to operational database for supervisor {supervisor_id}: {safe_dsn}. "
            f"Error: {original_error}"
        )


def _mask_password(dsn: str) -> str:
    """Mask password in DSN for safe logging."""
    # Simple masking for common DSN formats
    import re
    # Match patterns like postgresql://user:password@host or user:password@
    return re.sub(r'(://[^:]+:)[^@]+(@)', r'\1***\2', dsn)


# Thread-safe cache for engines by DSN
_engine_cache: dict[str, tuple] = {}  # dsn -> (engine, sessionmaker)
_cache_lock = threading.Lock()


def get_operational_engine(dsn: str):
    """Get or create an engine for the given DSN.

    Engines are cached by DSN with small connection pools.

    Args:
        dsn: Database connection string

    Returns:
        SQLAlchemy engine
    """
    with _cache_lock:
        if dsn in _engine_cache:
            return _engine_cache[dsn][0]

        # Create engine with appropriate settings
        if dsn.startswith("sqlite"):
            # SQLite: use StaticPool for thread safety with in-memory or file DBs
            engine = create_engine(
                dsn,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            # PostgreSQL/other: use small pool
            engine = create_engine(
                dsn,
                pool_size=2,
                max_overflow=3,
                pool_pre_ping=True,
            )

        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        _engine_cache[dsn] = (engine, session_factory)
        return engine


def _get_session_factory(dsn: str):
    """Get or create a session factory for the given DSN."""
    with _cache_lock:
        if dsn in _engine_cache:
            return _engine_cache[dsn][1]

    # Create engine first (this also creates the session factory)
    get_operational_engine(dsn)
    return _engine_cache[dsn][1]


def get_operational_session(
    supervisor_id: int,
    central_db_session: Session,
) -> Session:
    """Get a database session for a supervisor's operational database.

    Args:
        supervisor_id: The supervisor ID
        central_db_session: A session to the central database (to look up DSN)

    Returns:
        SQLAlchemy session for the supervisor's operational database

    Raises:
        MissingDSNError: If supervisor has no operational database configured
        UnreachableDSNError: If the database cannot be reached
    """
    # Import here to avoid circular imports
    from supervisor.models.supervisor import Supervisor

    supervisor = central_db_session.query(Supervisor).filter(
        Supervisor.id == supervisor_id
    ).first()

    if not supervisor:
        raise OperationalDBError(f"Supervisor {supervisor_id} not found")

    if not supervisor.supervisor_db_dsn:
        raise MissingDSNError(supervisor_id, supervisor.name)

    dsn = supervisor.supervisor_db_dsn

    try:
        session_factory = _get_session_factory(dsn)
        return session_factory()
    except Exception as e:
        raise UnreachableDSNError(supervisor_id, dsn, e) from e


@contextmanager
def operational_session_scope(
    supervisor_id: int,
    central_db_session: Session,
) -> Generator[Session, None, None]:
    """Context manager for operational database sessions.

    Usage:
        with operational_session_scope(supervisor_id, central_session) as ops_session:
            ops_session.add(IngestRun(...))
            ops_session.commit()

    Args:
        supervisor_id: The supervisor ID
        central_db_session: A session to the central database

    Yields:
        SQLAlchemy session for the supervisor's operational database
    """
    session = get_operational_session(supervisor_id, central_db_session)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_operational_db(dsn: str) -> None:
    """Initialize the operational database schema.

    Creates all tables defined in OperationalBase.

    Args:
        dsn: Database connection string
    """
    engine = get_operational_engine(dsn)
    OperationalBase.metadata.create_all(bind=engine)


def clear_engine_cache() -> None:
    """Clear the engine cache. Useful for testing."""
    global _engine_cache
    with _cache_lock:
        for engine, _ in _engine_cache.values():
            engine.dispose()
        _engine_cache = {}
