"""Tests for operational database isolation between supervisors."""

import pytest
import tempfile
import os
from pathlib import Path

from supervisor.models.supervisor import Supervisor
from supervisor.models.project import Project
from supervisor.operational import (
    init_operational_db,
    get_operational_session,
    IngestRun,
    Heartbeat,
    MissingDSNError,
    clear_engine_cache,
)
from supervisor.operational.models import RunStatus, HeartbeatStatus
from supervisor.services.operational_service import OperationalService


class TestOperationalDBIsolation:
    """Tests proving operational data is isolated between supervisors."""

    def test_runs_isolated_between_supervisors(self, db, test_user):
        """Create two supervisors with different DBs, verify run records are isolated."""
        # Clear engine cache to ensure fresh connections
        clear_engine_cache()

        # Create two temporary SQLite DBs
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path_a = os.path.join(tmpdir, "supervisor_a_ops.db")
            db_path_b = os.path.join(tmpdir, "supervisor_b_ops.db")
            dsn_a = f"sqlite:///{db_path_a}"
            dsn_b = f"sqlite:///{db_path_b}"

            # Create two supervisors with different operational DBs
            supervisor_a = Supervisor(
                name="Supervisor A",
                description="First supervisor",
                supervisor_db_dsn=dsn_a,
            )
            supervisor_b = Supervisor(
                name="Supervisor B",
                description="Second supervisor",
                supervisor_db_dsn=dsn_b,
            )
            db.add(supervisor_a)
            db.add(supervisor_b)
            db.commit()
            db.refresh(supervisor_a)
            db.refresh(supervisor_b)

            # Create projects under each supervisor
            project_a = Project(
                name="Project A",
                description="Project under Supervisor A",
                created_by=test_user.id,
                supervisor_id=supervisor_a.id,
            )
            project_b = Project(
                name="Project B",
                description="Project under Supervisor B",
                created_by=test_user.id,
                supervisor_id=supervisor_b.id,
            )
            db.add(project_a)
            db.add(project_b)
            db.commit()
            db.refresh(project_a)
            db.refresh(project_b)

            # Initialize operational DBs
            init_operational_db(dsn_a)
            init_operational_db(dsn_b)

            # Create run records in each supervisor's operational DB
            ops_session_a = get_operational_session(supervisor_a.id, db)
            run_a = IngestRun(
                project_id=project_a.id,
                status=RunStatus.COMPLETED,
                file_count=10,
                message="Run in Supervisor A",
            )
            ops_session_a.add(run_a)
            ops_session_a.commit()
            run_a_id = run_a.id
            ops_session_a.close()

            ops_session_b = get_operational_session(supervisor_b.id, db)
            run_b = IngestRun(
                project_id=project_b.id,
                status=RunStatus.RUNNING,
                file_count=5,
                message="Run in Supervisor B",
            )
            ops_session_b.add(run_b)
            ops_session_b.commit()
            run_b_id = run_b.id
            ops_session_b.close()

            # Verify isolation: Supervisor A's run should NOT be visible in Supervisor B
            ops_session_b2 = get_operational_session(supervisor_b.id, db)
            runs_in_b = ops_session_b2.query(IngestRun).all()
            ops_session_b2.close()

            assert len(runs_in_b) == 1
            assert runs_in_b[0].id == run_b_id
            assert runs_in_b[0].message == "Run in Supervisor B"
            assert runs_in_b[0].project_id == project_b.id

            # And Supervisor B's run should NOT be visible in Supervisor A
            ops_session_a2 = get_operational_session(supervisor_a.id, db)
            runs_in_a = ops_session_a2.query(IngestRun).all()
            ops_session_a2.close()

            assert len(runs_in_a) == 1
            assert runs_in_a[0].id == run_a_id
            assert runs_in_a[0].message == "Run in Supervisor A"
            assert runs_in_a[0].project_id == project_a.id

        clear_engine_cache()

    def test_heartbeats_isolated_between_supervisors(self, db, test_user):
        """Verify heartbeat records are isolated between supervisors."""
        clear_engine_cache()

        with tempfile.TemporaryDirectory() as tmpdir:
            dsn_a = f"sqlite:///{os.path.join(tmpdir, 'a.db')}"
            dsn_b = f"sqlite:///{os.path.join(tmpdir, 'b.db')}"

            supervisor_a = Supervisor(name="Sup A", supervisor_db_dsn=dsn_a)
            supervisor_b = Supervisor(name="Sup B", supervisor_db_dsn=dsn_b)
            db.add_all([supervisor_a, supervisor_b])
            db.commit()

            init_operational_db(dsn_a)
            init_operational_db(dsn_b)

            # Add heartbeat to supervisor A
            ops_a = get_operational_session(supervisor_a.id, db)
            hb_a = Heartbeat(
                ingestor_id="ingestor-alpha",
                hostname="host-a",
                status=HeartbeatStatus.HEALTHY,
            )
            ops_a.add(hb_a)
            ops_a.commit()
            ops_a.close()

            # Add heartbeat to supervisor B
            ops_b = get_operational_session(supervisor_b.id, db)
            hb_b = Heartbeat(
                ingestor_id="ingestor-beta",
                hostname="host-b",
                status=HeartbeatStatus.DEGRADED,
            )
            ops_b.add(hb_b)
            ops_b.commit()
            ops_b.close()

            # Verify A's heartbeat is only in A
            ops_a2 = get_operational_session(supervisor_a.id, db)
            heartbeats_a = ops_a2.query(Heartbeat).all()
            ops_a2.close()

            assert len(heartbeats_a) == 1
            assert heartbeats_a[0].ingestor_id == "ingestor-alpha"

            # Verify B's heartbeat is only in B
            ops_b2 = get_operational_session(supervisor_b.id, db)
            heartbeats_b = ops_b2.query(Heartbeat).all()
            ops_b2.close()

            assert len(heartbeats_b) == 1
            assert heartbeats_b[0].ingestor_id == "ingestor-beta"

        clear_engine_cache()


class TestMissingDSNError:
    """Tests for missing DSN handling."""

    def test_missing_dsn_raises_clear_error(self, db):
        """Verify that missing DSN raises MissingDSNError with helpful message."""
        # Create supervisor without DSN
        supervisor = Supervisor(
            name="No DB Supervisor",
            supervisor_db_dsn=None,
        )
        db.add(supervisor)
        db.commit()
        db.refresh(supervisor)

        with pytest.raises(MissingDSNError) as exc_info:
            get_operational_session(supervisor.id, db)

        error = exc_info.value
        assert error.supervisor_id == supervisor.id
        assert "No DB Supervisor" in str(error)
        assert "supervisor_db_dsn" in str(error)
        assert "supervisor-db init" in str(error)


class TestOperationalService:
    """Tests for the OperationalService."""

    def test_create_and_update_run(self, db, test_user, test_supervisor, test_project):
        """Test creating and updating ingest runs via service."""
        clear_engine_cache()

        # Initialize the operational DB
        init_operational_db(test_supervisor.supervisor_db_dsn)

        service = OperationalService(db)

        # Create a run
        run = service.create_ingest_run(
            supervisor_id=test_supervisor.id,
            project_id=test_project.id,
            triggered_by="test",
            ingestor_id="test-ingestor",
        )

        assert run["project_id"] == test_project.id
        assert run["status"] == "PENDING"

        # Update the run
        updated = service.update_ingest_run(
            supervisor_id=test_supervisor.id,
            run_id=run["id"],
            status=RunStatus.COMPLETED,
            file_count=5,
            total_bytes=1024,
            message="All done",
            finished=True,
        )

        assert updated["status"] == "COMPLETED"
        assert updated["file_count"] == 5
        assert updated["total_bytes"] == 1024
        assert updated["finished_at"] is not None

        clear_engine_cache()

    def test_heartbeat_create_and_update(self, db, test_supervisor):
        """Test recording heartbeats via service."""
        clear_engine_cache()

        init_operational_db(test_supervisor.supervisor_db_dsn)

        service = OperationalService(db)

        # Record initial heartbeat
        hb1 = service.record_heartbeat(
            supervisor_id=test_supervisor.id,
            ingestor_id="my-ingestor",
            hostname="myhost",
            status=HeartbeatStatus.HEALTHY,
            watched_paths=["/data/folder1", "/data/folder2"],
            version="1.0.0",
        )

        assert hb1["ingestor_id"] == "my-ingestor"
        assert hb1["status"] == "HEALTHY"

        # Update heartbeat (same ingestor_id)
        hb2 = service.record_heartbeat(
            supervisor_id=test_supervisor.id,
            ingestor_id="my-ingestor",
            status=HeartbeatStatus.DEGRADED,
            message="High load",
        )

        assert hb2["status"] == "DEGRADED"
        assert hb2["message"] == "High load"

        # Should still be only one heartbeat record
        heartbeats = service.get_heartbeats(test_supervisor.id, include_offline=True)
        assert len(heartbeats) == 1

        clear_engine_cache()
