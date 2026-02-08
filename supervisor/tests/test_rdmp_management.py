"""Tests for RDMP management API."""

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
from supervisor.utils.security import hash_password


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
    }

    for user in users_data.values():
        test_db.add(user)
    test_db.commit()

    for user in users_data.values():
        test_db.refresh(user)

    return users_data


@pytest.fixture
def supervisor_and_project(test_db, users):
    """Create a test supervisor and project with memberships."""
    sup = Supervisor(
        name="Test Lab",
        description="Test supervisor",
        supervisor_db_dsn="sqlite:///test_ops.db",
    )
    test_db.add(sup)
    test_db.commit()
    test_db.refresh(sup)

    # Add supervisor memberships
    memberships = [
        SupervisorMembership(supervisor_id=sup.id, user_id=users["pi_user"].id, role=SupervisorRole.PI),
        SupervisorMembership(supervisor_id=sup.id, user_id=users["steward_user"].id, role=SupervisorRole.STEWARD),
        SupervisorMembership(supervisor_id=sup.id, user_id=users["researcher_user"].id, role=SupervisorRole.RESEARCHER),
    ]
    for m in memberships:
        test_db.add(m)

    project = Project(
        name="Test Project",
        description="Test project",
        supervisor_id=sup.id,
        created_by=users["pi_user"].id,
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)

    # Add project memberships (needed for ingest run tests)
    project_memberships = [
        Membership(project_id=project.id, user_id=users["pi_user"].id, role_name="PI", created_by=users["pi_user"].id),
        Membership(project_id=project.id, user_id=users["steward_user"].id, role_name="steward", created_by=users["pi_user"].id),
        Membership(project_id=project.id, user_id=users["researcher_user"].id, role_name="researcher", created_by=users["pi_user"].id),
    ]
    for m in project_memberships:
        test_db.add(m)
    test_db.commit()

    return {"supervisor": sup, "project": project}


def get_auth_headers(client, username, password="test123"):
    """Get auth headers for a user."""
    response = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestRDMPCreate:
    """Test RDMP creation."""

    def test_steward_can_create_draft(self, client, users, supervisor_and_project):
        """STEWARD can create RDMP drafts."""
        headers = get_auth_headers(client, "steward_user")
        project_id = supervisor_and_project["project"].id

        response = client.post(
            f"/api/projects/{project_id}/rdmps",
            json={"title": "Test RDMP", "content": {"fields": []}},
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test RDMP"
        assert data["status"] == "DRAFT"
        assert data["version"] == 1

    def test_pi_can_create_draft(self, client, users, supervisor_and_project):
        """PI can create RDMP drafts."""
        headers = get_auth_headers(client, "pi_user")
        project_id = supervisor_and_project["project"].id

        response = client.post(
            f"/api/projects/{project_id}/rdmps",
            json={"title": "PI RDMP", "content": {}},
            headers=headers,
        )

        assert response.status_code == 201
        assert response.json()["status"] == "DRAFT"

    def test_researcher_cannot_create_draft(self, client, users, supervisor_and_project):
        """RESEARCHER cannot create RDMP drafts."""
        headers = get_auth_headers(client, "researcher_user")
        project_id = supervisor_and_project["project"].id

        response = client.post(
            f"/api/projects/{project_id}/rdmps",
            json={"title": "Test RDMP", "content": {}},
            headers=headers,
        )

        assert response.status_code == 403


class TestRDMPActivation:
    """Test RDMP activation."""

    def test_pi_can_activate_rdmp(self, client, test_db, users, supervisor_and_project):
        """PI can activate an RDMP."""
        project_id = supervisor_and_project["project"].id

        # Create draft as steward
        headers = get_auth_headers(client, "steward_user")
        response = client.post(
            f"/api/projects/{project_id}/rdmps",
            json={"title": "Activation Test", "content": {}},
            headers=headers,
        )
        rdmp_id = response.json()["id"]

        # Activate as PI
        headers = get_auth_headers(client, "pi_user")
        response = client.post(
            f"/api/rdmps/{rdmp_id}/activate",
            json={"reason": "Test activation"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ACTIVE"
        assert data["approved_by"] == users["pi_user"].id

    def test_steward_cannot_activate_rdmp(self, client, test_db, users, supervisor_and_project):
        """STEWARD cannot activate an RDMP."""
        project_id = supervisor_and_project["project"].id

        # Create draft
        headers = get_auth_headers(client, "steward_user")
        response = client.post(
            f"/api/projects/{project_id}/rdmps",
            json={"title": "No Activate", "content": {}},
            headers=headers,
        )
        rdmp_id = response.json()["id"]

        # Try to activate as steward
        response = client.post(
            f"/api/rdmps/{rdmp_id}/activate",
            json={"reason": "Test activation"},
            headers=headers,
        )

        assert response.status_code == 403

    def test_activating_new_rdmp_supersedes_previous(self, client, test_db, users, supervisor_and_project):
        """Activating a new RDMP supersedes the previously active one."""
        project_id = supervisor_and_project["project"].id
        pi_headers = get_auth_headers(client, "pi_user")

        # Create and activate first RDMP
        response = client.post(
            f"/api/projects/{project_id}/rdmps",
            json={"title": "First RDMP", "content": {}},
            headers=pi_headers,
        )
        first_rdmp_id = response.json()["id"]
        client.post(f"/api/rdmps/{first_rdmp_id}/activate", json={"reason": "First activation"}, headers=pi_headers)

        # Create and activate second RDMP
        response = client.post(
            f"/api/projects/{project_id}/rdmps",
            json={"title": "Second RDMP", "content": {}},
            headers=pi_headers,
        )
        second_rdmp_id = response.json()["id"]
        client.post(f"/api/rdmps/{second_rdmp_id}/activate", json={"reason": "Superseding first"}, headers=pi_headers)

        # Verify first is SUPERSEDED, second is ACTIVE
        response = client.get(f"/api/rdmps/{first_rdmp_id}", headers=pi_headers)
        assert response.json()["status"] == "SUPERSEDED"

        response = client.get(f"/api/rdmps/{second_rdmp_id}", headers=pi_headers)
        assert response.json()["status"] == "ACTIVE"

        # Verify only one ACTIVE
        response = client.get(f"/api/projects/{project_id}/rdmps", headers=pi_headers)
        rdmps = response.json()
        active_count = sum(1 for r in rdmps if r["status"] == "ACTIVE")
        assert active_count == 1


class TestRDMPActivationScoping:
    """Test that RDMP activation is properly scoped to project."""

    def test_activating_rdmp_in_project_a_does_not_affect_project_b(
        self, client, test_db, users, supervisor_and_project
    ):
        """Activating an RDMP in project A should NOT supersede active RDMP in project B."""
        supervisor = supervisor_and_project["supervisor"]
        project_a = supervisor_and_project["project"]

        # Create project B under the same supervisor
        project_b = Project(
            name="Project B",
            description="Second test project",
            supervisor_id=supervisor.id,
            created_by=users["pi_user"].id,
        )
        test_db.add(project_b)
        test_db.commit()
        test_db.refresh(project_b)

        # Add project B membership
        membership_b = Membership(
            project_id=project_b.id,
            user_id=users["pi_user"].id,
            role_name="PI",
            created_by=users["pi_user"].id,
        )
        test_db.add(membership_b)
        test_db.commit()

        pi_headers = get_auth_headers(client, "pi_user")

        # Create and activate RDMP in project A
        response = client.post(
            f"/api/projects/{project_a.id}/rdmps",
            json={"title": "RDMP A", "content": {}},
            headers=pi_headers,
        )
        rdmp_a_id = response.json()["id"]
        client.post(f"/api/rdmps/{rdmp_a_id}/activate", json={"reason": "Initial activation A"}, headers=pi_headers)

        # Create and activate RDMP in project B
        response = client.post(
            f"/api/projects/{project_b.id}/rdmps",
            json={"title": "RDMP B", "content": {}},
            headers=pi_headers,
        )
        rdmp_b_id = response.json()["id"]
        client.post(f"/api/rdmps/{rdmp_b_id}/activate", json={"reason": "Initial activation B"}, headers=pi_headers)

        # Verify both RDMPs are ACTIVE
        response = client.get(f"/api/rdmps/{rdmp_a_id}", headers=pi_headers)
        assert response.json()["status"] == "ACTIVE", "Project A's RDMP should still be ACTIVE"

        response = client.get(f"/api/rdmps/{rdmp_b_id}", headers=pi_headers)
        assert response.json()["status"] == "ACTIVE", "Project B's RDMP should be ACTIVE"

        # Now create and activate a NEW RDMP in project A
        response = client.post(
            f"/api/projects/{project_a.id}/rdmps",
            json={"title": "RDMP A v2", "content": {}},
            headers=pi_headers,
        )
        rdmp_a_v2_id = response.json()["id"]
        client.post(f"/api/rdmps/{rdmp_a_v2_id}/activate", json={"reason": "Supersede in A"}, headers=pi_headers)

        # Verify: Project A's first RDMP should be SUPERSEDED
        response = client.get(f"/api/rdmps/{rdmp_a_id}", headers=pi_headers)
        assert response.json()["status"] == "SUPERSEDED", "Project A's first RDMP should be SUPERSEDED"

        # Verify: Project A's second RDMP should be ACTIVE
        response = client.get(f"/api/rdmps/{rdmp_a_v2_id}", headers=pi_headers)
        assert response.json()["status"] == "ACTIVE", "Project A's second RDMP should be ACTIVE"

        # CRITICAL: Project B's RDMP should STILL be ACTIVE (not affected)
        response = client.get(f"/api/rdmps/{rdmp_b_id}", headers=pi_headers)
        assert response.json()["status"] == "ACTIVE", "Project B's RDMP should NOT be affected"

        # Verify via the active endpoint
        response = client.get(f"/api/projects/{project_a.id}/rdmps/active", headers=pi_headers)
        assert response.status_code == 200
        assert response.json()["id"] == rdmp_a_v2_id

        response = client.get(f"/api/projects/{project_b.id}/rdmps/active", headers=pi_headers)
        assert response.status_code == 200
        assert response.json()["id"] == rdmp_b_id

    def test_active_endpoint_returns_correct_project_rdmp(
        self, client, test_db, users, supervisor_and_project
    ):
        """The /active endpoint should return the active RDMP for the specific project only."""
        supervisor = supervisor_and_project["supervisor"]
        project_a = supervisor_and_project["project"]

        # Create project B
        project_b = Project(
            name="Project B Active Test",
            description="Test project",
            supervisor_id=supervisor.id,
            created_by=users["pi_user"].id,
        )
        test_db.add(project_b)
        test_db.commit()
        test_db.refresh(project_b)

        membership_b = Membership(
            project_id=project_b.id,
            user_id=users["pi_user"].id,
            role_name="PI",
            created_by=users["pi_user"].id,
        )
        test_db.add(membership_b)
        test_db.commit()

        pi_headers = get_auth_headers(client, "pi_user")

        # Activate RDMP only in project A
        response = client.post(
            f"/api/projects/{project_a.id}/rdmps",
            json={"title": "RDMP A Only", "content": {}},
            headers=pi_headers,
        )
        rdmp_a_id = response.json()["id"]
        client.post(f"/api/rdmps/{rdmp_a_id}/activate", json={"reason": "Active endpoint test"}, headers=pi_headers)

        # Project A should have active RDMP
        response = client.get(f"/api/projects/{project_a.id}/rdmps/active", headers=pi_headers)
        assert response.status_code == 200
        assert response.json()["id"] == rdmp_a_id

        # Project B should have NO active RDMP (returns null)
        response = client.get(f"/api/projects/{project_b.id}/rdmps/active", headers=pi_headers)
        assert response.status_code == 200
        # The endpoint returns null (not 404) when no active RDMP
        assert response.json() is None


class TestIngestRunRDMPProvenance:
    """Test that ingest runs record RDMP provenance."""

    def test_ingest_run_records_active_rdmp(self, client, test_db, users, supervisor_and_project):
        """Ingest run creation records the active RDMP ID."""
        from supervisor.operational import init_operational_db

        project_id = supervisor_and_project["project"].id
        supervisor = supervisor_and_project["supervisor"]

        # Initialize operational DB
        init_operational_db(supervisor.supervisor_db_dsn)

        pi_headers = get_auth_headers(client, "pi_user")

        # Create and activate an RDMP
        response = client.post(
            f"/api/projects/{project_id}/rdmps",
            json={"title": "Provenance Test RDMP", "content": {}},
            headers=pi_headers,
        )
        rdmp_id = response.json()["id"]
        client.post(f"/api/rdmps/{rdmp_id}/activate", json={"reason": "Provenance test"}, headers=pi_headers)

        # Create ingest run
        response = client.post(
            f"/api/ops/projects/{project_id}/runs",
            json={"triggered_by": "test"},
            headers=pi_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["rdmp_version_id"] == rdmp_id

    def test_ingest_run_records_null_if_no_active_rdmp(self, client, test_db, users, supervisor_and_project):
        """Ingest run creation records null if no RDMP is active."""
        from supervisor.operational import init_operational_db

        project_id = supervisor_and_project["project"].id
        supervisor = supervisor_and_project["supervisor"]

        # Initialize operational DB
        init_operational_db(supervisor.supervisor_db_dsn)

        pi_headers = get_auth_headers(client, "pi_user")

        # Create ingest run without any active RDMP
        response = client.post(
            f"/api/ops/projects/{project_id}/runs",
            json={"triggered_by": "test"},
            headers=pi_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["rdmp_version_id"] is None
