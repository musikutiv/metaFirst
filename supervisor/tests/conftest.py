"""Test fixtures and configuration."""

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
from supervisor.models.membership import Membership
from supervisor.models.rdmp import RDMPVersion
from supervisor.models.storage import StorageRoot
from supervisor.models.sample import Sample
from supervisor.utils.security import hash_password


# Create test database
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


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with database override."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db) -> User:
    """Create a test user."""
    user = User(
        username="testuser",
        hashed_password=hash_password("testpass123"),
        display_name="Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_user2(db) -> User:
    """Create a second test user."""
    user = User(
        username="testuser2",
        hashed_password=hash_password("testpass123"),
        display_name="Test User 2",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_supervisor(db) -> Supervisor:
    """Create a test supervisor."""
    supervisor = Supervisor(
        name="Test Supervisor",
        description="A test supervisor",
        supervisor_db_dsn="sqlite:///:memory:",  # In-memory for tests
    )
    db.add(supervisor)
    db.commit()
    db.refresh(supervisor)
    return supervisor


@pytest.fixture
def test_project(db, test_user, test_supervisor) -> Project:
    """Create a test project."""
    project = Project(
        name="Test Project",
        description="A test project",
        created_by=test_user.id,
        supervisor_id=test_supervisor.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@pytest.fixture
def test_membership(db, test_user, test_project) -> Membership:
    """Create a test membership with full permissions."""
    membership = Membership(
        project_id=test_project.id,
        user_id=test_user.id,
        role_name="PI",
        created_by=test_user.id,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


@pytest.fixture
def test_rdmp(db, test_project, test_user) -> RDMPVersion:
    """Create a test RDMP with PI role having full permissions."""
    rdmp_json = {
        "name": "Test RDMP",
        "version": 1,
        "roles": [
            {
                "name": "PI",
                "permissions": {
                    "can_edit_metadata": True,
                    "can_edit_paths": True,
                    "can_create_release": True,
                    "can_manage_rdmp": True,
                },
            },
            {
                "name": "researcher",
                "permissions": {
                    "can_edit_metadata": True,
                    "can_edit_paths": True,
                    "can_create_release": False,
                    "can_manage_rdmp": False,
                },
            },
            {
                "name": "viewer",
                "permissions": {
                    "can_edit_metadata": False,
                    "can_edit_paths": False,
                    "can_create_release": False,
                    "can_manage_rdmp": False,
                },
            },
        ],
        "fields": [
            {
                "key": "gene_name",
                "type": "string",
                "required": True,
                "visibility": "private",
            },
            {
                "key": "notes",
                "type": "string",
                "required": False,
                "visibility": "private",
            },
        ],
    }

    rdmp = RDMPVersion(
        project_id=test_project.id,
        version_int=1,
        rdmp_json=rdmp_json,
        provenance_json={"created_by": test_user.id},
        created_by=test_user.id,
    )
    db.add(rdmp)
    db.commit()
    db.refresh(rdmp)
    return rdmp


@pytest.fixture
def auth_headers(client, test_user) -> dict:
    """Get authentication headers for test user."""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpass123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user2(client, test_user2) -> dict:
    """Get authentication headers for second test user."""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser2", "password": "testpass123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_storage_root(db, test_project) -> StorageRoot:
    """Create a test storage root."""
    storage_root = StorageRoot(
        project_id=test_project.id,
        name="Test Storage",
        description="A test storage root",
    )
    db.add(storage_root)
    db.commit()
    db.refresh(storage_root)
    return storage_root


@pytest.fixture
def test_sample(db, test_project, test_user) -> Sample:
    """Create a test sample."""
    sample = Sample(
        project_id=test_project.id,
        sample_identifier="SAMPLE-001",
        created_by=test_user.id,
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample
