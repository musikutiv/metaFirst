"""Tests for lab status aggregation API."""

import pytest
from fastapi.testclient import TestClient

from supervisor.main import app
from supervisor.database import get_db, SessionLocal, engine, Base
from supervisor.models.user import User
from supervisor.models.supervisor import Supervisor
from supervisor.models.project import Project
from supervisor.models.supervisor_membership import SupervisorMembership, SupervisorRole
from supervisor.models.membership import Membership
from supervisor.models.rdmp import RDMPVersion, RDMPStatus
from supervisor.models.remediation import RemediationTask
from supervisor.utils.security import hash_password


@pytest.fixture(scope="function")
def test_db():
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
        "outsider_user": User(
            username="outsider_user",
            hashed_password=hash_password("test123"),
            display_name="Outsider User",
        ),
    }
    for user in users_data.values():
        test_db.add(user)
    test_db.commit()
    for user in users_data.values():
        test_db.refresh(user)
    return users_data


@pytest.fixture
def lab(test_db, users):
    """Create a lab (supervisor) with PI, steward, and researcher."""
    sup = Supervisor(
        name="Test Lab",
        description="Test supervisor",
        supervisor_db_dsn="sqlite:///test_ops.db",
    )
    test_db.add(sup)
    test_db.commit()
    test_db.refresh(sup)

    for username, role in [
        ("pi_user", SupervisorRole.PI),
        ("steward_user", SupervisorRole.STEWARD),
        ("researcher_user", SupervisorRole.RESEARCHER),
    ]:
        test_db.add(SupervisorMembership(
            supervisor_id=sup.id,
            user_id=users[username].id,
            role=role,
        ))
    test_db.commit()

    return sup


def get_auth_headers(client, username, password="test123"):
    response = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _add_project(test_db, lab, users, name, is_active=True):
    """Helper: create a project under the lab."""
    project = Project(
        name=name,
        description=f"{name} description",
        supervisor_id=lab.id,
        created_by=users["pi_user"].id,
        is_active=is_active,
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    return project


def _add_rdmp(test_db, project, users, status, version=1):
    """Helper: create an RDMP for a project."""
    rdmp = RDMPVersion(
        project_id=project.id,
        version_int=version,
        title=f"RDMP v{version}",
        status=status,
        rdmp_json={"name": f"RDMP v{version}", "fields": [], "roles": []},
        created_by=users["pi_user"].id,
        approved_by=users["pi_user"].id if status == RDMPStatus.ACTIVE else None,
    )
    test_db.add(rdmp)
    test_db.commit()
    test_db.refresh(rdmp)
    return rdmp


def _add_remediation(test_db, lab, project, issue_type, task_status="PENDING"):
    """Helper: create a remediation task."""
    task = RemediationTask(
        supervisor_id=lab.id,
        project_id=project.id,
        issue_type=issue_type,
        status=task_status,
        description=f"Test {issue_type}",
    )
    test_db.add(task)
    test_db.commit()
    test_db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEmptyLab:
    """Empty lab → all counts zero, no needs_attention items."""

    def test_empty_lab(self, client, users, lab):
        headers = get_auth_headers(client, "pi_user")
        response = client.get(
            f"/api/supervisors/{lab.id}/status-summary",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Projects
        assert data["projects"]["total_projects"] == 0
        assert data["projects"]["by_operational_state"]["operational"] == 0
        assert data["projects"]["by_operational_state"]["non_operational"] == 0
        assert data["projects"]["by_rdmp_status"]["no_rdmp"] == 0
        assert data["projects"]["by_rdmp_status"]["draft"] == 0
        assert data["projects"]["by_rdmp_status"]["active"] == 0
        assert data["projects"]["by_rdmp_status"]["superseded"] == 0

        # No needs_attention items
        assert data["needs_attention"] == []

        # Remediation
        assert data["remediation_summary"]["total_open"] == 0
        assert data["remediation_summary"]["by_severity"]["high"] == 0
        assert data["remediation_summary"]["by_severity"]["warning"] == 0
        assert data["remediation_summary"]["by_severity"]["info"] == 0


class TestOperationalWithDraftRDMP:
    """Operational project + draft RDMP → one high-severity needs_attention item."""

    def test_operational_project_draft_rdmp(self, client, test_db, users, lab):
        project = _add_project(test_db, lab, users, "Active Project", is_active=True)
        _add_rdmp(test_db, project, users, RDMPStatus.DRAFT)

        headers = get_auth_headers(client, "pi_user")
        response = client.get(
            f"/api/supervisors/{lab.id}/status-summary",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["projects"]["total_projects"] == 1
        assert data["projects"]["by_operational_state"]["operational"] == 1
        assert data["projects"]["by_rdmp_status"]["draft"] == 1

        # Should have high-severity needs_attention
        high_items = [
            item for item in data["needs_attention"]
            if item["type"] == "project_operational_without_active_rdmp"
        ]
        assert len(high_items) == 1
        assert high_items[0]["severity"] == "high"
        assert high_items[0]["count"] == 1
        assert project.id in high_items[0]["entity_ids"]


class TestSupersededRDMP:
    """Superseded RDMP without active replacement → warning surfaced."""

    def test_superseded_rdmp_warning(self, client, test_db, users, lab):
        project = _add_project(test_db, lab, users, "Superseded Project", is_active=False)
        _add_rdmp(test_db, project, users, RDMPStatus.SUPERSEDED)

        headers = get_auth_headers(client, "steward_user")
        response = client.get(
            f"/api/supervisors/{lab.id}/status-summary",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["projects"]["by_rdmp_status"]["superseded"] == 1

        warning_items = [
            item for item in data["needs_attention"]
            if item["type"] == "project_with_superseded_rdmp"
        ]
        assert len(warning_items) == 1
        assert warning_items[0]["severity"] == "warning"
        assert warning_items[0]["count"] == 1
        assert project.id in warning_items[0]["entity_ids"]


class TestMultipleProjects:
    """Multiple projects aggregate correctly."""

    def test_multi_project_aggregation(self, client, test_db, users, lab):
        # Project A: operational + active RDMP (healthy)
        proj_a = _add_project(test_db, lab, users, "Project A", is_active=True)
        _add_rdmp(test_db, proj_a, users, RDMPStatus.ACTIVE)

        # Project B: operational + no RDMP (problematic)
        proj_b = _add_project(test_db, lab, users, "Project B", is_active=True)

        # Project C: non-operational + draft RDMP
        proj_c = _add_project(test_db, lab, users, "Project C", is_active=False)
        _add_rdmp(test_db, proj_c, users, RDMPStatus.DRAFT)

        # Project D: non-operational + no RDMP
        proj_d = _add_project(test_db, lab, users, "Project D", is_active=False)

        headers = get_auth_headers(client, "pi_user")
        response = client.get(
            f"/api/supervisors/{lab.id}/status-summary",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["projects"]["total_projects"] == 4
        assert data["projects"]["by_operational_state"]["operational"] == 2
        assert data["projects"]["by_operational_state"]["non_operational"] == 2
        assert data["projects"]["by_rdmp_status"]["active"] == 1
        assert data["projects"]["by_rdmp_status"]["draft"] == 1
        assert data["projects"]["by_rdmp_status"]["no_rdmp"] == 2

        # Project B is operational without RDMP → high
        high_items = [
            item for item in data["needs_attention"]
            if item["type"] == "project_operational_without_active_rdmp"
        ]
        assert len(high_items) == 1
        assert high_items[0]["count"] == 1
        assert proj_b.id in high_items[0]["entity_ids"]

        # Projects B and D have no RDMP → info
        no_rdmp_items = [
            item for item in data["needs_attention"]
            if item["type"] == "project_without_rdmp"
        ]
        assert len(no_rdmp_items) == 1
        assert no_rdmp_items[0]["count"] == 2
        assert set(no_rdmp_items[0]["entity_ids"]) == {proj_b.id, proj_d.id}


class TestRemediationAggregation:
    """Remediation aggregation by severity."""

    def test_remediation_by_severity(self, client, test_db, users, lab):
        project = _add_project(test_db, lab, users, "Remediation Project", is_active=True)
        _add_rdmp(test_db, project, users, RDMPStatus.ACTIVE)

        # 2 high (retention_exceeded), 1 warning (embargo_active), 1 resolved
        _add_remediation(test_db, lab, project, "retention_exceeded", "PENDING")
        _add_remediation(test_db, lab, project, "retention_exceeded", "ACKED")
        _add_remediation(test_db, lab, project, "embargo_active", "PENDING")
        _add_remediation(test_db, lab, project, "retention_exceeded", "DISMISSED")  # resolved

        headers = get_auth_headers(client, "pi_user")
        response = client.get(
            f"/api/supervisors/{lab.id}/status-summary",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Remediation summary (only unresolved)
        assert data["remediation_summary"]["total_open"] == 3
        assert data["remediation_summary"]["by_severity"]["high"] == 2
        assert data["remediation_summary"]["by_severity"]["warning"] == 1
        assert data["remediation_summary"]["by_severity"]["info"] == 0

        # Needs attention: remediation items
        high_remediation = [
            item for item in data["needs_attention"]
            if item["type"] == "unresolved_remediation_high"
        ]
        assert len(high_remediation) == 1
        assert high_remediation[0]["count"] == 2

        warning_remediation = [
            item for item in data["needs_attention"]
            if item["type"] == "unresolved_remediation_warning"
        ]
        assert len(warning_remediation) == 1
        assert warning_remediation[0]["count"] == 1


class TestCrossLabIsolation:
    """Cross-lab isolation (no leakage)."""

    def test_no_cross_lab_leakage(self, client, test_db, users, lab):
        # Create a second lab with its own project
        lab_b = Supervisor(
            name="Other Lab",
            description="Other supervisor",
            supervisor_db_dsn="sqlite:///other_ops.db",
        )
        test_db.add(lab_b)
        test_db.commit()
        test_db.refresh(lab_b)

        test_db.add(SupervisorMembership(
            supervisor_id=lab_b.id,
            user_id=users["pi_user"].id,
            role=SupervisorRole.PI,
        ))
        test_db.commit()

        # Add project to lab B only
        proj_b = Project(
            name="Lab B Project",
            description="Should not appear in lab A",
            supervisor_id=lab_b.id,
            created_by=users["pi_user"].id,
            is_active=True,
        )
        test_db.add(proj_b)
        test_db.commit()
        test_db.refresh(proj_b)

        # Add remediation task to lab B
        _add_remediation(test_db, lab_b, proj_b, "retention_exceeded")

        # Query lab A → should see nothing
        headers = get_auth_headers(client, "pi_user")
        response = client.get(
            f"/api/supervisors/{lab.id}/status-summary",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["projects"]["total_projects"] == 0
        assert data["needs_attention"] == []
        assert data["remediation_summary"]["total_open"] == 0

        # Query lab B → should see its data
        response = client.get(
            f"/api/supervisors/{lab_b.id}/status-summary",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["projects"]["total_projects"] == 1
        assert data["remediation_summary"]["total_open"] == 1


class TestAccessControl:
    """Permission enforcement."""

    def test_researcher_denied(self, client, users, lab):
        """Researcher cannot access status summary."""
        headers = get_auth_headers(client, "researcher_user")
        response = client.get(
            f"/api/supervisors/{lab.id}/status-summary",
            headers=headers,
        )
        assert response.status_code == 403

    def test_outsider_denied(self, client, users, lab):
        """Non-member cannot access status summary."""
        headers = get_auth_headers(client, "outsider_user")
        response = client.get(
            f"/api/supervisors/{lab.id}/status-summary",
            headers=headers,
        )
        assert response.status_code == 403

    def test_steward_allowed(self, client, users, lab):
        """Steward can access status summary."""
        headers = get_auth_headers(client, "steward_user")
        response = client.get(
            f"/api/supervisors/{lab.id}/status-summary",
            headers=headers,
        )
        assert response.status_code == 200
