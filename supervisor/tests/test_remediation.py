"""Tests for remediation tasks API and detection logic."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from supervisor.main import app
from supervisor.database import get_db, SessionLocal, engine, Base
from supervisor.models.user import User
from supervisor.models.supervisor import Supervisor
from supervisor.models.project import Project
from supervisor.models.sample import Sample
from supervisor.models.rdmp import RDMPVersion, RDMPStatus
from supervisor.models.remediation import RemediationTask, TaskStatus, IssueType
from supervisor.models.supervisor_membership import SupervisorMembership, SupervisorRole
from supervisor.utils.security import hash_password
from supervisor.services.remediation_service import (
    detect_issues_for_project,
    create_task,
    task_exists,
    transition_task_status,
)


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh database for each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def users(test_db):
    """Create test users."""
    users_data = {
        "pi_user": User(
            username="pi_user",
            hashed_password=hash_password("test123"),
            display_name="PI User",
        ),
        "steward_user": User(
            username="steward_user",
            hashed_password=hash_password("test123"),
            display_name="Steward User",
        ),
        "researcher_user": User(
            username="researcher_user",
            hashed_password=hash_password("test123"),
            display_name="Researcher User",
        ),
        "non_member": User(
            username="non_member",
            hashed_password=hash_password("test123"),
            display_name="Non Member User",
        ),
    }

    for user in users_data.values():
        test_db.add(user)
    test_db.commit()

    for user in users_data.values():
        test_db.refresh(user)

    return users_data


@pytest.fixture
def supervisor(test_db, users):
    """Create a test supervisor with memberships."""
    sup = Supervisor(
        name="Test Lab",
        description="Test supervisor",
        primary_steward_user_id=users["pi_user"].id,
        enable_automated_execution=False,  # Default to disabled
    )
    test_db.add(sup)
    test_db.commit()
    test_db.refresh(sup)

    # Add supervisor memberships
    memberships = [
        SupervisorMembership(
            supervisor_id=sup.id,
            user_id=users["pi_user"].id,
            role=SupervisorRole.PI,
        ),
        SupervisorMembership(
            supervisor_id=sup.id,
            user_id=users["steward_user"].id,
            role=SupervisorRole.STEWARD,
        ),
        SupervisorMembership(
            supervisor_id=sup.id,
            user_id=users["researcher_user"].id,
            role=SupervisorRole.RESEARCHER,
        ),
    ]
    for m in memberships:
        test_db.add(m)
    test_db.commit()

    return sup


@pytest.fixture
def project(test_db, users, supervisor):
    """Create a test project."""
    proj = Project(
        name="Test Project",
        description="Test project",
        supervisor_id=supervisor.id,
        created_by=users["pi_user"].id,
    )
    test_db.add(proj)
    test_db.commit()
    test_db.refresh(proj)
    return proj


@pytest.fixture
def rdmp_with_retention(test_db, project, users):
    """Create an RDMP with retention policy."""
    rdmp = RDMPVersion(
        project_id=project.id,
        version_int=1,
        status=RDMPStatus.ACTIVE,
        title="Test RDMP",
        created_by=users["pi_user"].id,
        rdmp_json={"name": "Test"},
        retention_days=30,  # 30 day retention
    )
    test_db.add(rdmp)
    test_db.commit()
    test_db.refresh(rdmp)
    return rdmp


@pytest.fixture
def old_sample(test_db, project, users):
    """Create a sample that's older than retention period."""
    sample = Sample(
        project_id=project.id,
        sample_identifier="OLD-SAMPLE-001",
        created_by=users["pi_user"].id,
    )
    test_db.add(sample)
    test_db.commit()
    test_db.refresh(sample)

    # Manually set created_at to be 60 days ago
    old_date = datetime.now(timezone.utc) - timedelta(days=60)
    sample.created_at = old_date
    test_db.commit()
    test_db.refresh(sample)

    return sample


def get_auth_headers(client, username: str, password: str = "test123") -> dict:
    """Get auth headers for a user."""
    response = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- Detection Logic Tests ---

class TestDetectionLogic:
    """Tests for issue detection logic."""

    def test_detect_retention_exceeded(self, test_db, project, rdmp_with_retention, old_sample):
        """Should detect samples that exceed retention period."""
        issues = detect_issues_for_project(test_db, project.id)

        assert len(issues) == 1
        assert issues[0]["issue_type"] == IssueType.RETENTION_EXCEEDED.value
        assert issues[0]["sample_id"] == old_sample.id
        assert "60 days old" in issues[0]["description"]

    def test_detect_embargo_active(self, test_db, project, users):
        """Should detect active embargo."""
        # Create RDMP with future embargo
        rdmp = RDMPVersion(
            project_id=project.id,
            version_int=1,
            status=RDMPStatus.ACTIVE,
            title="Test RDMP",
            created_by=users["pi_user"].id,
            rdmp_json={"name": "Test"},
            embargo_until=datetime.now(timezone.utc) + timedelta(days=30),
        )
        test_db.add(rdmp)
        test_db.commit()

        issues = detect_issues_for_project(test_db, project.id)

        assert len(issues) == 1
        assert issues[0]["issue_type"] == IssueType.EMBARGO_ACTIVE.value

    def test_no_issues_without_active_rdmp(self, test_db, project):
        """Should return no issues if no active RDMP."""
        issues = detect_issues_for_project(test_db, project.id)
        assert len(issues) == 0

    def test_no_retention_issue_for_recent_sample(self, test_db, project, rdmp_with_retention, users):
        """Should not flag recent samples."""
        # Create a recent sample
        sample = Sample(
            project_id=project.id,
            sample_identifier="NEW-SAMPLE-001",
            created_by=users["pi_user"].id,
        )
        test_db.add(sample)
        test_db.commit()

        issues = detect_issues_for_project(test_db, project.id)

        # Should have no issues (sample is new)
        assert len(issues) == 0


class TestTaskCreation:
    """Tests for task creation."""

    def test_create_task(self, test_db, supervisor, project):
        """Should create a remediation task."""
        task = create_task(
            test_db,
            supervisor_id=supervisor.id,
            project_id=project.id,
            issue_type=IssueType.RETENTION_EXCEEDED.value,
            description="Test task",
        )

        assert task.id is not None
        assert task.status == TaskStatus.PENDING.value
        assert task.supervisor_id == supervisor.id

    def test_task_exists_check(self, test_db, supervisor, project):
        """Should detect existing open tasks."""
        create_task(
            test_db,
            supervisor_id=supervisor.id,
            project_id=project.id,
            issue_type=IssueType.RETENTION_EXCEEDED.value,
            description="Test task",
        )

        assert task_exists(test_db, project.id, IssueType.RETENTION_EXCEEDED.value) is True
        assert task_exists(test_db, project.id, IssueType.EMBARGO_ACTIVE.value) is False


class TestTaskTransitions:
    """Tests for task status transitions."""

    def test_valid_transitions(self, test_db, supervisor, project, users):
        """Should allow valid status transitions."""
        task = create_task(
            test_db,
            supervisor_id=supervisor.id,
            project_id=project.id,
            issue_type=IssueType.RETENTION_EXCEEDED.value,
            description="Test task",
        )

        # PENDING -> ACKED
        task = transition_task_status(test_db, task, TaskStatus.ACKED, users["researcher_user"].id)
        assert task.status == TaskStatus.ACKED.value
        assert task.acked_by == users["researcher_user"].id

        # ACKED -> APPROVED
        task = transition_task_status(test_db, task, TaskStatus.APPROVED, users["pi_user"].id)
        assert task.status == TaskStatus.APPROVED.value
        assert task.approved_by == users["pi_user"].id

    def test_invalid_transition(self, test_db, supervisor, project, users):
        """Should reject invalid transitions."""
        task = create_task(
            test_db,
            supervisor_id=supervisor.id,
            project_id=project.id,
            issue_type=IssueType.RETENTION_EXCEEDED.value,
            description="Test task",
        )

        # Can't go directly from PENDING to APPROVED
        with pytest.raises(ValueError):
            transition_task_status(test_db, task, TaskStatus.APPROVED, users["pi_user"].id)


# --- API Tests ---

class TestRemediationAPI:
    """Tests for remediation API endpoints."""

    def test_list_tasks_requires_steward_or_pi(self, client, users, supervisor, project, test_db):
        """Listing tasks should require STEWARD or PI role."""
        # Create a task
        create_task(
            test_db,
            supervisor_id=supervisor.id,
            project_id=project.id,
            issue_type=IssueType.RETENTION_EXCEEDED.value,
            description="Test task",
        )

        # Researcher should be denied
        headers = get_auth_headers(client, "researcher_user")
        response = client.get(f"/api/remediation/tasks?supervisor_id={supervisor.id}", headers=headers)
        assert response.status_code == 403

        # PI should succeed
        headers = get_auth_headers(client, "pi_user")
        response = client.get(f"/api/remediation/tasks?supervisor_id={supervisor.id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_ack_allowed_for_any_member(self, client, users, supervisor, project, test_db):
        """Any member should be able to acknowledge a task."""
        task = create_task(
            test_db,
            supervisor_id=supervisor.id,
            project_id=project.id,
            issue_type=IssueType.RETENTION_EXCEEDED.value,
            description="Test task",
        )

        # Researcher should be able to ack
        headers = get_auth_headers(client, "researcher_user")
        response = client.post(f"/api/remediation/tasks/{task.id}/ack", headers=headers)
        assert response.status_code == 200
        assert response.json()["new_status"] == "ACKED"

    def test_approve_requires_steward_or_pi(self, client, users, supervisor, project, test_db):
        """Approving tasks should require STEWARD or PI role."""
        task = create_task(
            test_db,
            supervisor_id=supervisor.id,
            project_id=project.id,
            issue_type=IssueType.RETENTION_EXCEEDED.value,
            description="Test task",
        )

        # First ack the task
        headers = get_auth_headers(client, "researcher_user")
        client.post(f"/api/remediation/tasks/{task.id}/ack", headers=headers)

        # Researcher should be denied for approve
        response = client.post(f"/api/remediation/tasks/{task.id}/approve", headers=headers)
        assert response.status_code == 403

        # Steward should succeed
        headers = get_auth_headers(client, "steward_user")
        response = client.post(f"/api/remediation/tasks/{task.id}/approve", headers=headers)
        assert response.status_code == 200
        assert response.json()["new_status"] == "APPROVED"

    def test_execute_requires_automation_enabled(self, client, users, supervisor, project, test_db):
        """Execute should return 403 if automation is disabled."""
        task = create_task(
            test_db,
            supervisor_id=supervisor.id,
            project_id=project.id,
            issue_type=IssueType.RETENTION_EXCEEDED.value,
            description="Test task",
        )

        # Progress task to APPROVED
        headers = get_auth_headers(client, "pi_user")
        client.post(f"/api/remediation/tasks/{task.id}/ack", headers=headers)
        client.post(f"/api/remediation/tasks/{task.id}/approve", headers=headers)

        # Execute should fail - automation disabled
        response = client.post(f"/api/remediation/tasks/{task.id}/execute", headers=headers)
        assert response.status_code == 403
        assert "Automated execution is disabled" in response.json()["detail"]

    def test_execute_succeeds_with_automation_enabled(self, client, users, supervisor, project, test_db):
        """Execute should succeed if automation is enabled."""
        # Enable automation
        supervisor.enable_automated_execution = True
        test_db.commit()

        task = create_task(
            test_db,
            supervisor_id=supervisor.id,
            project_id=project.id,
            issue_type=IssueType.RETENTION_EXCEEDED.value,
            description="Test task",
        )

        # Progress task to APPROVED
        headers = get_auth_headers(client, "pi_user")
        client.post(f"/api/remediation/tasks/{task.id}/ack", headers=headers)
        client.post(f"/api/remediation/tasks/{task.id}/approve", headers=headers)

        # Execute should succeed
        response = client.post(f"/api/remediation/tasks/{task.id}/execute", headers=headers)
        assert response.status_code == 200
        assert response.json()["new_status"] == "EXECUTED"

    def test_non_member_cannot_access_tasks(self, client, users, supervisor, project, test_db):
        """Non-members should not be able to access tasks."""
        task = create_task(
            test_db,
            supervisor_id=supervisor.id,
            project_id=project.id,
            issue_type=IssueType.RETENTION_EXCEEDED.value,
            description="Test task",
        )

        headers = get_auth_headers(client, "non_member")
        response = client.get(f"/api/remediation/tasks/{task.id}", headers=headers)
        assert response.status_code == 403


# --- CLI Tests ---

class TestRemediationCLI:
    """Tests for remediation CLI."""

    def test_dry_run_detection(self, test_db, supervisor, project, rdmp_with_retention, old_sample, capsys):
        """Dry run should detect issues without creating tasks."""
        from supervisor.cli.remediation import run_remediation

        results = run_remediation(test_db, supervisor_id=supervisor.id, dry_run=True)

        assert results["detected"] == 1
        assert results["created"] == 0

        # Verify no task was created
        task_count = test_db.query(RemediationTask).count()
        assert task_count == 0

    def test_create_tasks(self, test_db, supervisor, project, rdmp_with_retention, old_sample):
        """Should create tasks when not dry run."""
        from supervisor.cli.remediation import run_remediation

        results = run_remediation(test_db, supervisor_id=supervisor.id, dry_run=False)

        assert results["detected"] == 1
        assert results["created"] == 1

        # Verify task was created
        task = test_db.query(RemediationTask).first()
        assert task is not None
        assert task.issue_type == IssueType.RETENTION_EXCEEDED.value

    def test_skip_existing_tasks(self, test_db, supervisor, project, rdmp_with_retention, old_sample):
        """Should skip creating duplicate tasks."""
        from supervisor.cli.remediation import run_remediation

        # First run
        results1 = run_remediation(test_db, supervisor_id=supervisor.id, dry_run=False)
        assert results1["created"] == 1

        # Second run should skip
        results2 = run_remediation(test_db, supervisor_id=supervisor.id, dry_run=False)
        assert results2["detected"] == 1
        assert results2["created"] == 0
        assert results2["skipped"] == 1
