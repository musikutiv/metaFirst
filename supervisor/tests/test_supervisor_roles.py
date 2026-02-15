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


class TestProjectListingSupervisorScoped:
    """Test that project listing is supervisor-scoped (not project membership)."""

    @pytest.fixture
    def multiple_projects(self, test_db, users, supervisor):
        """Create multiple projects under the supervisor without project memberships."""
        projects = []
        for i in range(3):
            project = Project(
                name=f"Project {i + 1}",
                description=f"Test project {i + 1}",
                supervisor_id=supervisor.id,
                created_by=users["pi_user"].id,
            )
            test_db.add(project)
            projects.append(project)
        test_db.commit()
        for p in projects:
            test_db.refresh(p)
        return projects

    def test_supervisor_member_sees_all_projects(self, client, users, supervisor, multiple_projects):
        """User with supervisor membership sees all projects for that supervisor."""
        headers = get_auth_headers(client, "pi_user")

        response = client.get("/api/projects/", headers=headers)

        assert response.status_code == 200
        data = response.json()
        # Should see all 3 projects (no project memberships required)
        assert len(data) == 3
        project_names = {p["name"] for p in data}
        assert project_names == {"Project 1", "Project 2", "Project 3"}

    def test_researcher_sees_all_supervisor_projects(self, client, users, supervisor, multiple_projects):
        """RESEARCHER with supervisor membership sees all projects (not just those with project membership)."""
        headers = get_auth_headers(client, "researcher_user")

        response = client.get("/api/projects/", headers=headers)

        assert response.status_code == 200
        data = response.json()
        # Researcher should see all 3 projects via supervisor membership
        assert len(data) == 3

    def test_non_member_sees_no_projects(self, client, users, supervisor, multiple_projects):
        """Non-member of supervisor sees no projects."""
        headers = get_auth_headers(client, "non_member")

        response = client.get("/api/projects/", headers=headers)

        assert response.status_code == 200
        data = response.json()
        # Non-member should see no projects
        assert len(data) == 0


class TestProjectAccessSupervisorScoped:
    """Test that project access is supervisor-scoped (not project membership)."""

    @pytest.fixture
    def project_without_memberships(self, test_db, users, supervisor):
        """Create a project without any project-level memberships."""
        project = Project(
            name="No Membership Project",
            description="Project without any Membership rows",
            supervisor_id=supervisor.id,
            created_by=users["pi_user"].id,
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)
        return project

    def test_supervisor_member_can_access_project(self, client, users, supervisor, project_without_memberships):
        """User with supervisor membership can access project without project membership."""
        headers = get_auth_headers(client, "pi_user")

        response = client.get(f"/api/projects/{project_without_memberships.id}", headers=headers)

        assert response.status_code == 200
        assert response.json()["name"] == "No Membership Project"

    def test_researcher_can_access_project_via_supervisor(self, client, users, supervisor, project_without_memberships):
        """RESEARCHER can access project via supervisor membership (no project membership needed)."""
        headers = get_auth_headers(client, "researcher_user")

        response = client.get(f"/api/projects/{project_without_memberships.id}", headers=headers)

        assert response.status_code == 200
        assert response.json()["name"] == "No Membership Project"

    def test_non_member_cannot_access_project(self, client, users, supervisor, project_without_memberships):
        """Non-member of supervisor cannot access project."""
        headers = get_auth_headers(client, "non_member")

        response = client.get(f"/api/projects/{project_without_memberships.id}", headers=headers)

        assert response.status_code == 403
        assert "Not a member of this project's supervisor" in response.json()["detail"]

    def test_supervisor_member_can_list_samples(self, client, users, supervisor, project_without_memberships):
        """User with supervisor membership can list samples without project membership."""
        headers = get_auth_headers(client, "researcher_user")

        response = client.get(f"/api/projects/{project_without_memberships.id}/samples", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []  # Empty but accessible
        assert data["total"] == 0

    def test_non_member_cannot_list_samples(self, client, users, supervisor, project_without_memberships):
        """Non-member cannot list samples."""
        headers = get_auth_headers(client, "non_member")

        response = client.get(f"/api/projects/{project_without_memberships.id}/samples", headers=headers)

        assert response.status_code == 403

    def test_supervisor_member_can_list_raw_data(self, client, users, supervisor, project_without_memberships):
        """User with supervisor membership can list raw data without project membership."""
        headers = get_auth_headers(client, "researcher_user")

        response = client.get(f"/api/projects/{project_without_memberships.id}/raw-data", headers=headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_non_member_cannot_list_raw_data(self, client, users, supervisor, project_without_memberships):
        """Non-member cannot list raw data."""
        headers = get_auth_headers(client, "non_member")

        response = client.get(f"/api/projects/{project_without_memberships.id}/raw-data", headers=headers)

        assert response.status_code == 403

    def test_supervisor_member_can_list_storage_roots(self, client, users, supervisor, project_without_memberships):
        """User with supervisor membership can list storage roots without project membership."""
        headers = get_auth_headers(client, "researcher_user")

        response = client.get(f"/api/projects/{project_without_memberships.id}/storage-roots", headers=headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_non_member_cannot_list_storage_roots(self, client, users, supervisor, project_without_memberships):
        """Non-member cannot list storage roots."""
        headers = get_auth_headers(client, "non_member")

        response = client.get(f"/api/projects/{project_without_memberships.id}/storage-roots", headers=headers)

        assert response.status_code == 403


class TestCrossSupervisorIsolation:
    """Test that users from one supervisor cannot access projects from another."""

    @pytest.fixture
    def second_supervisor_and_project(self, test_db, users):
        """Create a second supervisor with its own project (non_member is PI)."""
        # Create second supervisor
        sup2 = Supervisor(
            name="Second Lab",
            description="Another supervisor",
            primary_steward_user_id=users["non_member"].id,
        )
        test_db.add(sup2)
        test_db.commit()
        test_db.refresh(sup2)

        # Add non_member as PI of second supervisor
        membership = SupervisorMembership(
            supervisor_id=sup2.id,
            user_id=users["non_member"].id,
            role=SupervisorRole.PI,
        )
        test_db.add(membership)
        test_db.commit()

        # Create project under second supervisor
        project = Project(
            name="Second Lab Project",
            description="Project in second supervisor",
            supervisor_id=sup2.id,
            created_by=users["non_member"].id,
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        return {"supervisor": sup2, "project": project}

    def test_user_cannot_access_other_supervisor_project(
        self, client, users, supervisor, second_supervisor_and_project
    ):
        """User from supervisor 1 cannot access project from supervisor 2."""
        # pi_user is in supervisor 1, not supervisor 2
        headers = get_auth_headers(client, "pi_user")
        project_id = second_supervisor_and_project["project"].id

        response = client.get(f"/api/projects/{project_id}", headers=headers)

        assert response.status_code == 403
        assert "Not a member of this project's supervisor" in response.json()["detail"]

    def test_user_only_lists_own_supervisor_projects(
        self, client, users, supervisor, second_supervisor_and_project
    ):
        """User only sees projects from supervisors they belong to."""
        # Create a project in supervisor 1
        headers = get_auth_headers(client, "pi_user")
        response = client.post(
            "/api/projects/",
            json={
                "name": "First Lab Project",
                "description": "Test",
                "supervisor_id": supervisor.id,
            },
            headers=headers,
        )
        assert response.status_code == 201

        # pi_user should only see their supervisor's project
        response = client.get("/api/projects/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        project_names = {p["name"] for p in data}
        assert "First Lab Project" in project_names
        assert "Second Lab Project" not in project_names

        # non_member (PI of second supervisor) should only see second lab's project
        headers = get_auth_headers(client, "non_member")
        response = client.get("/api/projects/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        project_names = {p["name"] for p in data}
        assert "Second Lab Project" in project_names
        assert "First Lab Project" not in project_names


class TestSupervisorMemberManagement:
    """Test supervisor member management endpoints."""

    def test_list_members(self, client, users, supervisor):
        """Any member can list supervisor members."""
        headers = get_auth_headers(client, "researcher_user")

        response = client.get(f"/api/supervisors/{supervisor.id}/members", headers=headers)

        assert response.status_code == 200
        data = response.json()
        # Should have 3 members from the supervisor fixture
        assert len(data) >= 3
        usernames = {m["username"] for m in data}
        assert "pi_user" in usernames
        assert "steward_user" in usernames
        assert "researcher_user" in usernames

    def test_add_member_requires_steward_or_pi(self, client, users, supervisor):
        """Adding members requires STEWARD or PI role."""
        # Researcher cannot add members
        headers = get_auth_headers(client, "researcher_user")
        response = client.post(
            f"/api/supervisors/{supervisor.id}/members",
            json={"username": "non_member", "role": "RESEARCHER"},
            headers=headers,
        )
        assert response.status_code == 403

        # Steward can add members
        headers = get_auth_headers(client, "steward_user")
        response = client.post(
            f"/api/supervisors/{supervisor.id}/members",
            json={"username": "non_member", "role": "RESEARCHER"},
            headers=headers,
        )
        assert response.status_code == 201
        assert response.json()["username"] == "non_member"
        assert response.json()["role"] == "RESEARCHER"

    def test_update_member_role_requires_pi(self, client, users, supervisor):
        """Updating member role requires PI role."""
        # Steward cannot change roles
        headers = get_auth_headers(client, "steward_user")
        response = client.patch(
            f"/api/supervisors/{supervisor.id}/members/{users['researcher_user'].id}",
            json={"role": "STEWARD", "reason": "Promotion"},
            headers=headers,
        )
        assert response.status_code == 403

        # PI can change roles
        headers = get_auth_headers(client, "pi_user")
        response = client.patch(
            f"/api/supervisors/{supervisor.id}/members/{users['researcher_user'].id}",
            json={"role": "STEWARD", "reason": "Promotion for excellent work"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["role"] == "STEWARD"

    def test_remove_member_requires_pi(self, client, test_db, users, supervisor):
        """Removing members requires PI role."""
        # First add a member to remove
        headers = get_auth_headers(client, "pi_user")
        response = client.post(
            f"/api/supervisors/{supervisor.id}/members",
            json={"username": "non_member", "role": "RESEARCHER"},
            headers=headers,
        )
        assert response.status_code == 201

        # Steward cannot remove members
        headers = get_auth_headers(client, "steward_user")
        response = client.delete(
            f"/api/supervisors/{supervisor.id}/members/{users['non_member'].id}",
            headers=headers,
        )
        assert response.status_code == 403

        # PI can remove members
        headers = get_auth_headers(client, "pi_user")
        response = client.delete(
            f"/api/supervisors/{supervisor.id}/members/{users['non_member'].id}",
            headers=headers,
        )
        assert response.status_code == 204

    def test_cannot_remove_last_pi(self, client, users, supervisor):
        """Cannot remove the last PI from a supervisor."""
        headers = get_auth_headers(client, "pi_user")

        # Try to remove the only PI
        response = client.delete(
            f"/api/supervisors/{supervisor.id}/members/{users['pi_user'].id}",
            headers=headers,
        )

        assert response.status_code == 400
        assert "last PI" in response.json()["detail"]

    def test_non_member_cannot_list_members(self, client, users, supervisor):
        """Non-member cannot list supervisor members."""
        headers = get_auth_headers(client, "non_member")

        response = client.get(f"/api/supervisors/{supervisor.id}/members", headers=headers)

        assert response.status_code == 403
