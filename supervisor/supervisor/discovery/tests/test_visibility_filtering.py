"""Tests for visibility-based access control in discovery search.

Requirements:
- Create 2 supervisors, each with one project and different visibility settings
- Assert: Non-member authenticated user cannot see PRIVATE from other supervisor
- Assert: Non-member authenticated user can see INSTITUTION
- Assert: Unauthenticated can see PUBLIC only
"""

import json
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from supervisor.database import Base, get_db
from supervisor.main import app
from supervisor.models.user import User
from supervisor.models.supervisor import Supervisor
from supervisor.models.project import Project
from supervisor.models.supervisor_membership import SupervisorMembership, SupervisorRole
from supervisor.utils.security import hash_password


# Central database for users/supervisors
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for tests."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def setup_database():
    """Create database tables and seed data for visibility tests."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Create two users
    user_alpha = User(
        username="user_alpha",
        hashed_password=hash_password("password123"),
        display_name="User Alpha",
    )
    user_beta = User(
        username="user_beta",
        hashed_password=hash_password("password123"),
        display_name="User Beta",
    )
    db.add_all([user_alpha, user_beta])
    db.commit()
    db.refresh(user_alpha)
    db.refresh(user_beta)

    # Create two supervisors
    supervisor_alpha = Supervisor(
        name="Supervisor Alpha",
        description="First supervisor",
        supervisor_db_dsn="sqlite:///:memory:",
    )
    supervisor_beta = Supervisor(
        name="Supervisor Beta",
        description="Second supervisor",
        supervisor_db_dsn="sqlite:///:memory:",
    )
    db.add_all([supervisor_alpha, supervisor_beta])
    db.commit()
    db.refresh(supervisor_alpha)
    db.refresh(supervisor_beta)

    # Create supervisor memberships
    # user_alpha is member of supervisor_alpha only
    membership_alpha = SupervisorMembership(
        supervisor_id=supervisor_alpha.id,
        user_id=user_alpha.id,
        role=SupervisorRole.RESEARCHER,
    )
    # user_beta is member of supervisor_beta only
    membership_beta = SupervisorMembership(
        supervisor_id=supervisor_beta.id,
        user_id=user_beta.id,
        role=SupervisorRole.RESEARCHER,
    )
    db.add_all([membership_alpha, membership_beta])
    db.commit()

    # Create projects
    project_alpha = Project(
        name="Project Alpha",
        description="Project in Supervisor Alpha",
        created_by=user_alpha.id,
        supervisor_id=supervisor_alpha.id,
    )
    project_beta = Project(
        name="Project Beta",
        description="Project in Supervisor Beta",
        created_by=user_beta.id,
        supervisor_id=supervisor_beta.id,
    )
    db.add_all([project_alpha, project_beta])
    db.commit()
    db.refresh(project_alpha)
    db.refresh(project_beta)

    yield {
        "user_alpha": user_alpha,
        "user_beta": user_beta,
        "supervisor_alpha": supervisor_alpha,
        "supervisor_beta": supervisor_beta,
        "project_alpha": project_alpha,
        "project_beta": project_beta,
    }

    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def client(setup_database):
    """Create test client with database override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def api_key_header():
    """Return headers with valid API key for push."""
    return {"Authorization": f"ApiKey {os.environ.get('DISCOVERY_API_KEY')}"}


@pytest.fixture(scope="module")
def auth_headers_alpha(client, setup_database):
    """Get auth headers for user_alpha."""
    response = client.post(
        "/api/auth/login",
        data={"username": "user_alpha", "password": "password123"},
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def auth_headers_beta(client, setup_database):
    """Get auth headers for user_beta."""
    response = client.post(
        "/api/auth/login",
        data={"username": "user_beta", "password": "password123"},
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def indexed_samples(client, api_key_header, setup_database):
    """Push samples to discovery index with different visibilities."""
    data = setup_database

    payload = {
        "origin": "visibility-test-origin",
        "records": [
            # PUBLIC sample from supervisor_alpha
            {
                "origin_supervisor_id": data["supervisor_alpha"].id,
                "origin_project_id": data["project_alpha"].id,
                "origin_sample_id": 1001,
                "sample_identifier": "ALPHA-PUBLIC-001",
                "visibility": "PUBLIC",
                "metadata": {"sample_identifier": "ALPHA-PUBLIC-001", "type": "public_alpha"},
            },
            # INSTITUTION sample from supervisor_alpha
            {
                "origin_supervisor_id": data["supervisor_alpha"].id,
                "origin_project_id": data["project_alpha"].id,
                "origin_sample_id": 1002,
                "sample_identifier": "ALPHA-INSTITUTION-001",
                "visibility": "INSTITUTION",
                "metadata": {"sample_identifier": "ALPHA-INSTITUTION-001", "type": "institution_alpha"},
            },
            # PRIVATE sample from supervisor_alpha
            {
                "origin_supervisor_id": data["supervisor_alpha"].id,
                "origin_project_id": data["project_alpha"].id,
                "origin_sample_id": 1003,
                "sample_identifier": "ALPHA-PRIVATE-001",
                "visibility": "PRIVATE",
                "metadata": {"sample_identifier": "ALPHA-PRIVATE-001", "type": "private_alpha"},
            },
            # PUBLIC sample from supervisor_beta
            {
                "origin_supervisor_id": data["supervisor_beta"].id,
                "origin_project_id": data["project_beta"].id,
                "origin_sample_id": 2001,
                "sample_identifier": "BETA-PUBLIC-001",
                "visibility": "PUBLIC",
                "metadata": {"sample_identifier": "BETA-PUBLIC-001", "type": "public_beta"},
            },
            # INSTITUTION sample from supervisor_beta
            {
                "origin_supervisor_id": data["supervisor_beta"].id,
                "origin_project_id": data["project_beta"].id,
                "origin_sample_id": 2002,
                "sample_identifier": "BETA-INSTITUTION-001",
                "visibility": "INSTITUTION",
                "metadata": {"sample_identifier": "BETA-INSTITUTION-001", "type": "institution_beta"},
            },
            # PRIVATE sample from supervisor_beta
            {
                "origin_supervisor_id": data["supervisor_beta"].id,
                "origin_project_id": data["project_beta"].id,
                "origin_sample_id": 2003,
                "sample_identifier": "BETA-PRIVATE-001",
                "visibility": "PRIVATE",
                "metadata": {"sample_identifier": "BETA-PRIVATE-001", "type": "private_beta"},
            },
        ],
    }

    response = client.post(
        "/api/discovery/push",
        json=payload,
        headers=api_key_header,
    )
    assert response.status_code == 200, f"Push failed: {response.json()}"
    assert response.json()["upserted"] == 6

    return payload["records"]


class TestPublicVisibility:
    """Tests for PUBLIC visibility."""

    def test_unauthenticated_can_see_public_only(self, client, indexed_samples):
        """Unauthenticated users can only see PUBLIC samples."""
        response = client.get("/api/discovery/search?q=&visibility=PUBLIC")
        assert response.status_code == 200
        data = response.json()

        # Should see PUBLIC samples from both supervisors
        sample_ids = [hit["origin_sample_id"] for hit in data["hits"]]
        assert 1001 in sample_ids, "Should see ALPHA-PUBLIC-001"
        assert 2001 in sample_ids, "Should see BETA-PUBLIC-001"

        # Should NOT see INSTITUTION or PRIVATE
        assert 1002 not in sample_ids, "Should NOT see ALPHA-INSTITUTION-001"
        assert 2003 not in sample_ids, "Should NOT see BETA-PRIVATE-001"

    def test_unauthenticated_cannot_search_institution(self, client, indexed_samples):
        """Unauthenticated users cannot search INSTITUTION visibility."""
        response = client.get("/api/discovery/search?q=&visibility=INSTITUTION")
        assert response.status_code == 401

    def test_unauthenticated_cannot_search_private(self, client, indexed_samples):
        """Unauthenticated users cannot search PRIVATE visibility."""
        response = client.get("/api/discovery/search?q=&visibility=PRIVATE")
        assert response.status_code == 401


class TestInstitutionVisibility:
    """Tests for INSTITUTION visibility."""

    def test_authenticated_can_see_institution(self, client, auth_headers_alpha, indexed_samples):
        """Any authenticated user can see INSTITUTION samples."""
        response = client.get(
            "/api/discovery/search?q=&visibility=INSTITUTION",
            headers=auth_headers_alpha,
        )
        assert response.status_code == 200
        data = response.json()

        sample_ids = [hit["origin_sample_id"] for hit in data["hits"]]
        # user_alpha (member of supervisor_alpha) can see INSTITUTION from both supervisors
        assert 1002 in sample_ids, "Should see ALPHA-INSTITUTION-001"
        assert 2002 in sample_ids, "Should see BETA-INSTITUTION-001"

    def test_non_member_can_see_institution(self, client, auth_headers_beta, indexed_samples):
        """User_beta (not member of supervisor_alpha) can still see INSTITUTION from alpha."""
        response = client.get(
            "/api/discovery/search?q=institution_alpha&visibility=INSTITUTION",
            headers=auth_headers_beta,
        )
        assert response.status_code == 200
        data = response.json()

        # user_beta should be able to see ALPHA-INSTITUTION-001 (INSTITUTION is visible to any authenticated user)
        sample_ids = [hit["origin_sample_id"] for hit in data["hits"]]
        assert 1002 in sample_ids, "Non-member should see INSTITUTION from other supervisor"


class TestPrivateVisibility:
    """Tests for PRIVATE visibility."""

    def test_member_can_see_own_supervisor_private(self, client, auth_headers_alpha, indexed_samples):
        """User can see PRIVATE samples from their own supervisor."""
        response = client.get(
            "/api/discovery/search?q=&visibility=PRIVATE",
            headers=auth_headers_alpha,
        )
        assert response.status_code == 200
        data = response.json()

        sample_ids = [hit["origin_sample_id"] for hit in data["hits"]]
        # user_alpha is member of supervisor_alpha, should see PRIVATE from alpha
        assert 1003 in sample_ids, "Should see ALPHA-PRIVATE-001 (own supervisor)"
        # But NOT from supervisor_beta
        assert 2003 not in sample_ids, "Should NOT see BETA-PRIVATE-001 (other supervisor)"

    def test_non_member_cannot_see_private_from_other_supervisor(
        self, client, auth_headers_alpha, indexed_samples
    ):
        """User cannot see PRIVATE samples from supervisors they're not a member of."""
        response = client.get(
            "/api/discovery/search?q=private_beta&visibility=PRIVATE",
            headers=auth_headers_alpha,
        )
        assert response.status_code == 200
        data = response.json()

        # user_alpha searching for "private_beta" should find nothing
        # because BETA-PRIVATE-001 is PRIVATE and user_alpha is not member of supervisor_beta
        sample_ids = [hit["origin_sample_id"] for hit in data["hits"]]
        assert 2003 not in sample_ids, "Non-member should NOT see PRIVATE from other supervisor"

    def test_user_beta_can_see_own_private(self, client, auth_headers_beta, indexed_samples):
        """user_beta can see PRIVATE samples from supervisor_beta."""
        response = client.get(
            "/api/discovery/search?q=&visibility=PRIVATE",
            headers=auth_headers_beta,
        )
        assert response.status_code == 200
        data = response.json()

        sample_ids = [hit["origin_sample_id"] for hit in data["hits"]]
        # user_beta is member of supervisor_beta
        assert 2003 in sample_ids, "Should see BETA-PRIVATE-001 (own supervisor)"
        # But NOT from supervisor_alpha
        assert 1003 not in sample_ids, "Should NOT see ALPHA-PRIVATE-001 (other supervisor)"


class TestCombinedVisibility:
    """Tests for combined visibility searches."""

    def test_search_multiple_visibilities(self, client, auth_headers_alpha, indexed_samples):
        """Search can combine multiple visibility levels."""
        response = client.get(
            "/api/discovery/search?q=&visibility=PUBLIC,INSTITUTION,PRIVATE",
            headers=auth_headers_alpha,
        )
        assert response.status_code == 200
        data = response.json()

        sample_ids = [hit["origin_sample_id"] for hit in data["hits"]]

        # Should see all PUBLIC
        assert 1001 in sample_ids
        assert 2001 in sample_ids

        # Should see all INSTITUTION
        assert 1002 in sample_ids
        assert 2002 in sample_ids

        # Should see PRIVATE only from own supervisor
        assert 1003 in sample_ids
        assert 2003 not in sample_ids  # user_alpha not member of supervisor_beta


class TestRecordDetail:
    """Tests for individual record access control."""

    def test_unauthenticated_can_access_public_record(
        self, client, indexed_samples
    ):
        """Unauthenticated user can get detail of PUBLIC record."""
        # First find a public record
        search = client.get("/api/discovery/search?q=ALPHA-PUBLIC&visibility=PUBLIC")
        assert search.status_code == 200
        hits = search.json()["hits"]
        assert len(hits) > 0
        record_id = hits[0]["id"]

        # Get detail without auth
        response = client.get(f"/api/discovery/records/{record_id}")
        assert response.status_code == 200

    def test_unauthenticated_cannot_access_institution_record(
        self, client, auth_headers_alpha, indexed_samples
    ):
        """Unauthenticated user cannot get detail of INSTITUTION record."""
        # First find an INSTITUTION record (need auth to search)
        search = client.get(
            "/api/discovery/search?q=ALPHA-INSTITUTION&visibility=INSTITUTION",
            headers=auth_headers_alpha,
        )
        assert search.status_code == 200
        hits = search.json()["hits"]
        assert len(hits) > 0
        record_id = hits[0]["id"]

        # Try to get detail without auth
        response = client.get(f"/api/discovery/records/{record_id}")
        assert response.status_code == 401

    def test_non_member_cannot_access_private_record(
        self, client, auth_headers_alpha, auth_headers_beta, indexed_samples
    ):
        """User cannot access PRIVATE record from supervisor they're not member of."""
        # user_beta finds their own PRIVATE record
        search = client.get(
            "/api/discovery/search?q=BETA-PRIVATE&visibility=PRIVATE",
            headers=auth_headers_beta,
        )
        assert search.status_code == 200
        hits = search.json()["hits"]
        assert len(hits) > 0
        record_id = hits[0]["id"]

        # user_alpha tries to access it - should fail
        response = client.get(
            f"/api/discovery/records/{record_id}",
            headers=auth_headers_alpha,
        )
        assert response.status_code == 403


