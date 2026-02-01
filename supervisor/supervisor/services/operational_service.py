"""Service layer for operational database operations.

Provides high-level functions for managing runs, heartbeats, and other
operational state in per-supervisor databases.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from supervisor.operational import (
    get_operational_session,
    operational_session_scope,
    IngestRun,
    Heartbeat,
    MissingDSNError,
    OperationalDBError,
)
from supervisor.operational.models import RunStatus, HeartbeatStatus


class OperationalService:
    """Service for managing operational state in per-supervisor databases."""

    def __init__(self, central_db: Session):
        """Initialize with a central database session.

        Args:
            central_db: SQLAlchemy session for the central database
        """
        self.central_db = central_db

    # -------------------------------------------------------------------------
    # Ingest Runs
    # -------------------------------------------------------------------------

    def create_ingest_run(
        self,
        supervisor_id: int,
        project_id: int,
        triggered_by: str = "api",
        ingestor_id: Optional[str] = None,
    ) -> IngestRun:
        """Create a new ingest run record.

        Args:
            supervisor_id: The supervisor owning the operational DB
            project_id: The project being ingested
            triggered_by: How the run was triggered (watcher, manual, api)
            ingestor_id: Optional identifier of the ingestor instance

        Returns:
            The created IngestRun record
        """
        with operational_session_scope(supervisor_id, self.central_db) as ops_session:
            run = IngestRun(
                project_id=project_id,
                status=RunStatus.PENDING,
                triggered_by=triggered_by,
                ingestor_id=ingestor_id,
            )
            ops_session.add(run)
            ops_session.flush()
            # Refresh to get the ID
            ops_session.refresh(run)
            run_id = run.id
            run_project_id = run.project_id
            run_status = run.status

        # Return a detached summary (the session is closed)
        return self._make_run_dict(run_id, run_project_id, run_status)

    def update_ingest_run(
        self,
        supervisor_id: int,
        run_id: int,
        status: Optional[RunStatus] = None,
        file_count: Optional[int] = None,
        total_bytes: Optional[int] = None,
        error_count: Optional[int] = None,
        message: Optional[str] = None,
        finished: bool = False,
    ) -> dict:
        """Update an ingest run record.

        Args:
            supervisor_id: The supervisor owning the operational DB
            run_id: The run to update
            status: New status (optional)
            file_count: Updated file count (optional)
            total_bytes: Updated byte count (optional)
            error_count: Updated error count (optional)
            message: Summary or error message (optional)
            finished: Set to True to mark finished_at timestamp

        Returns:
            Updated run info as dict
        """
        with operational_session_scope(supervisor_id, self.central_db) as ops_session:
            run = ops_session.query(IngestRun).filter(IngestRun.id == run_id).first()
            if not run:
                raise OperationalDBError(f"IngestRun {run_id} not found")

            if status is not None:
                run.status = status
            if file_count is not None:
                run.file_count = file_count
            if total_bytes is not None:
                run.total_bytes = total_bytes
            if error_count is not None:
                run.error_count = error_count
            if message is not None:
                run.message = message
            if finished:
                run.finished_at = datetime.now(timezone.utc)

            ops_session.flush()

            return {
                "id": run.id,
                "project_id": run.project_id,
                "status": run.status.value,
                "file_count": run.file_count,
                "total_bytes": run.total_bytes,
                "error_count": run.error_count,
                "message": run.message,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            }

    def get_recent_runs(
        self,
        supervisor_id: int,
        project_id: Optional[int] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent ingest runs.

        Args:
            supervisor_id: The supervisor owning the operational DB
            project_id: Filter by project (optional)
            limit: Maximum number of runs to return

        Returns:
            List of run info dicts
        """
        ops_session = get_operational_session(supervisor_id, self.central_db)
        try:
            query = ops_session.query(IngestRun).order_by(IngestRun.started_at.desc())
            if project_id is not None:
                query = query.filter(IngestRun.project_id == project_id)
            runs = query.limit(limit).all()

            return [
                {
                    "id": run.id,
                    "project_id": run.project_id,
                    "status": run.status.value,
                    "file_count": run.file_count,
                    "total_bytes": run.total_bytes,
                    "error_count": run.error_count,
                    "message": run.message,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                    "triggered_by": run.triggered_by,
                    "ingestor_id": run.ingestor_id,
                }
                for run in runs
            ]
        finally:
            ops_session.close()

    # -------------------------------------------------------------------------
    # Heartbeats
    # -------------------------------------------------------------------------

    def record_heartbeat(
        self,
        supervisor_id: int,
        ingestor_id: str,
        hostname: Optional[str] = None,
        status: HeartbeatStatus = HeartbeatStatus.HEALTHY,
        message: Optional[str] = None,
        watched_paths: Optional[list[str]] = None,
        version: Optional[str] = None,
    ) -> dict:
        """Record or update an ingestor heartbeat.

        Creates a new heartbeat record if the ingestor_id doesn't exist,
        or updates the existing one.

        Args:
            supervisor_id: The supervisor owning the operational DB
            ingestor_id: Unique identifier of the ingestor
            hostname: Optional hostname
            status: Health status
            message: Optional status message
            watched_paths: List of paths being watched
            version: Ingestor version

        Returns:
            Heartbeat info as dict
        """
        import json

        with operational_session_scope(supervisor_id, self.central_db) as ops_session:
            heartbeat = ops_session.query(Heartbeat).filter(
                Heartbeat.ingestor_id == ingestor_id
            ).first()

            if heartbeat:
                # Update existing
                heartbeat.last_seen_at = datetime.now(timezone.utc)
                heartbeat.status = status
                if hostname is not None:
                    heartbeat.hostname = hostname
                if message is not None:
                    heartbeat.message = message
                if watched_paths is not None:
                    heartbeat.watched_paths = json.dumps(watched_paths)
                if version is not None:
                    heartbeat.version = version
            else:
                # Create new
                heartbeat = Heartbeat(
                    ingestor_id=ingestor_id,
                    hostname=hostname,
                    status=status,
                    message=message,
                    watched_paths=json.dumps(watched_paths) if watched_paths else None,
                    version=version,
                )
                ops_session.add(heartbeat)

            ops_session.flush()

            return {
                "ingestor_id": heartbeat.ingestor_id,
                "hostname": heartbeat.hostname,
                "status": heartbeat.status.value,
                "last_seen_at": heartbeat.last_seen_at.isoformat(),
                "message": heartbeat.message,
                "version": heartbeat.version,
            }

    def get_heartbeats(
        self,
        supervisor_id: int,
        include_offline: bool = False,
    ) -> list[dict]:
        """Get all ingestor heartbeats.

        Args:
            supervisor_id: The supervisor owning the operational DB
            include_offline: Include offline ingestors

        Returns:
            List of heartbeat info dicts
        """
        import json

        ops_session = get_operational_session(supervisor_id, self.central_db)
        try:
            query = ops_session.query(Heartbeat).order_by(Heartbeat.last_seen_at.desc())
            if not include_offline:
                query = query.filter(Heartbeat.status != HeartbeatStatus.OFFLINE)
            heartbeats = query.all()

            return [
                {
                    "ingestor_id": hb.ingestor_id,
                    "hostname": hb.hostname,
                    "status": hb.status.value,
                    "last_seen_at": hb.last_seen_at.isoformat() if hb.last_seen_at else None,
                    "message": hb.message,
                    "watched_paths": json.loads(hb.watched_paths) if hb.watched_paths else [],
                    "version": hb.version,
                }
                for hb in heartbeats
            ]
        finally:
            ops_session.close()

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _make_run_dict(self, run_id: int, project_id: int, status: RunStatus) -> dict:
        """Create a minimal run dict from detached values."""
        return {
            "id": run_id,
            "project_id": project_id,
            "status": status.value,
        }
