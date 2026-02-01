"""Tests for supervisor-scoped roles and authorization."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from supervisor.main import app
from supervisor.database import get_db, SessionLocal, engine, Base
from supervisor.models.user import User
from supervisor.models.supervisor import Supervisor
from supervisor.models.project import Project
from supervisor.models.membership import Membership
from supervisor.models.supervisor_membership import SupervisorMembership, SupervisorRole
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


def get_auth_headers(client, username, password="test123"):
    """Get auth headers for a user."""
    response = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestSupervisorMembershipModel:
    """Test the supervisor membership model."""

    def test_create_supervisor_membership(self, test_db, users, supervisor):
        """Test that supervisor memberships are created correctly."""
        memberships = (
            test_db.query(SupervisorMembership)
            .filter(SupervisorMembership.supervisor_id == supervisor.id)
            .all()
        )

        assert len(memberships) == 3
        roles = {m.user_id: m.role for m in memberships}

        assert roles[users["pi_user"].id] == SupervisorRole.PI
        assert roles[users["steward_user"].id] == SupervisorRole.STEWARD
        assert roles[users["researcher_user"].id] == SupervisorRole.RESEARCHER

    def test_unique_constraint_on_supervisor_user(self, test_db, users, supervisor):
        """Test that a user can only have one membership per supervisor."""
        from sqlalchemy.exc import IntegrityError

        duplicate = SupervisorMembership(
            supervisor_id=supervisor.id,
            user_id=users["pi_user"].id,
            role=SupervisorRole.RESEARCHER,  # Different role, same user
        )
        test_db.add(duplicate)

        with pytest.raises(IntegrityError):
            test_db.commit()
        test_db.rollback()

    def test_primary_steward_relationship(self, test_db, users, supervisor):
        """Test that primary_steward relationship works."""
        test_db.refresh(supervisor)
        assert supervisor.primary_steward is not None
        assert supervisor.primary_steward.id == users["pi_user"].id


class TestCreateProjectAuthorization:
    """Test project creation requires STEWARD or PI role."""

    def test_pi_can_create_project(self, client, users, supervisor):
        """PI can create projects."""
        headers = get_auth_headers(client, "pi_user")

        response = client.post(
            "/api/projects/",
            json={
                "name": "PI Project",
                "description": "Test",
                "supervisor_id": supervisor.id,
            },
            headers=headers,
        )

        assert response.status_code == 201
        assert response.json()["name"] == "PI Project"

    def test_steward_can_create_project(self, client, users, supervisor):
        """STEWARD can create projects."""
        headers = get_auth_headers(client, "steward_user")

        response = client.post(
            "/api/projects/",
            json={
                "name": "Steward Project",
                "description": "Test",
                "supervisor_id": supervisor.id,
            },
            headers=headers,
        )

        assert response.status_code == 201
        assert response.json()["name"] == "Steward Project"

    def test_researcher_cannot_create_project(self, client, users, supervisor):
        """RESEARCHER cannot create projects (requires STEWARD or PI)."""
        headers = get_auth_headers(client, "researcher_user")

        response = client.post(
            "/api/projects/",
            json={
                "name": "Test Project",
                "description": "Test",
                "supervisor_id": supervisor.id,
            },
            headers=headers,
        )

        assert response.status_code == 403
        assert "Requires one of roles" in response.json()["detail"]

    def test_non_member_cannot_create_project(self, client, users, supervisor):
        """Non-member cannot create projects for a supervisor."""
        headers = get_auth_headers(client, "non_member")

        response = client.post(
            "/api/projects/",
            json={
                "name": "Test Project",
                "description": "Test",
                "supervisor_id": supervisor.id,
            },
            headers=headers,
        )

        assert response.status_code == 403
        assert "Requires one of roles" in response.json()["detail"]


class TestUpdateSupervisorAuthorization:
    """Test supervisor updates require STEWARD or PI role."""

    def test_pi_can_update_supervisor(self, client, users, supervisor):
        """PI can update supervisor."""
        headers = get_auth_headers(client, "pi_user")

        response = client.patch(
            f"/api/supervisors/{supervisor.id}",
            json={"description": "Updated by PI"},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["description"] == "Updated by PI"

    def test_steward_can_update_supervisor(self, client, users, supervisor):
        """STEWARD can update supervisor."""
        headers = get_auth_headers(client, "steward_user")

        response = client.patch(
            f"/api/supervisors/{supervisor.id}",
            json={"description": "Updated by steward"},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["description"] == "Updated by steward"

    def test_researcher_cannot_update_supervisor(self, client, users, supervisor):
        """RESEARCHER cannot update supervisor (requires STEWARD or PI)."""
        headers = get_auth_headers(client, "researcher_user")

        response = client.patch(
            f"/api/supervisors/{supervisor.id}",
            json={"description": "Updated description"},
            headers=headers,
        )

        assert response.status_code == 403
        assert "Requires one of roles" in response.json()["detail"]

    def test_non_member_cannot_update_supervisor(self, client, users, supervisor):
        """Non-member cannot update supervisor."""
        headers = get_auth_headers(client, "non_member")

        response = client.patch(
            f"/api/supervisors/{supervisor.id}",
            json={"description": "Updated description"},
            headers=headers,
        )

        assert response.status_code == 403


class TestIngestRunAuthorization:
    """Test ingest run creation requires RESEARCHER, STEWARD, or PI role."""

    @pytest.fixture
    def project_with_membership(self, test_db, users, supervisor):
        """Create a project and add researcher as a project member."""
        # Create project (need to do this directly in DB since researcher can't create via API)
        project = Project(
            name="Test Ingest Project",
            description="For ingest tests",
            supervisor_id=supervisor.id,
            created_by=users["pi_user"].id,
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        # Add researcher as project member
        membership = Membership(
            project_id=project.id,
            user_id=users["researcher_user"].id,
            role_name="researcher",
            created_by=users["pi_user"].id,
        )
        test_db.add(membership)
        test_db.commit()

        return project

    def test_researcher_can_create_ingest_run(self, client, users, supervisor, project_with_membership):
        """RESEARCHER can create ingest runs."""
        headers = get_auth_headers(client, "researcher_user")

        response = client.post(
            f"/api/ops/projects/{project_with_membership.id}/runs",
            json={"triggered_by": "test"},
            headers=headers,
        )

        # May be 503 if no operational DB configured, but should not be 403
        assert response.status_code != 403, f"Researcher should be authorized: {response.json()}"

    def test_non_member_cannot_create_ingest_run(self, client, users, supervisor, project_with_membership):
        """Non-member cannot create ingest runs."""
        headers = get_auth_headers(client, "non_member")

        response = client.post(
            f"/api/ops/projects/{project_with_membership.id}/runs",
            json={"triggered_by": "test"},
            headers=headers,
        )

        assert response.status_code == 403
