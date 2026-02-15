"""Tests for RDMP-derived multi-sample ingestion template."""

import csv
import io
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
from supervisor.models.storage import StorageRoot
from supervisor.models.raw_data import RawDataItem
from supervisor.models.sample import Sample, SampleFieldValue
from supervisor.models.audit import AuditLog
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
def setup(test_db, users):
    """Create supervisor, project, memberships, RDMP, storage root, and raw data item."""
    sup = Supervisor(
        name="Test Lab",
        description="Test supervisor",
        supervisor_db_dsn="sqlite:///test_ops.db",
    )
    test_db.add(sup)
    test_db.commit()
    test_db.refresh(sup)

    # Supervisor memberships
    for username, role in [
        ("pi_user", SupervisorRole.PI),
        ("steward_user", SupervisorRole.STEWARD),
        ("researcher_user", SupervisorRole.RESEARCHER),
    ]:
        test_db.add(SupervisorMembership(
            supervisor_id=sup.id, user_id=users[username].id, role=role,
        ))

    project = Project(
        name="Test Project",
        description="Test project",
        supervisor_id=sup.id,
        created_by=users["pi_user"].id,
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)

    # Project memberships
    for username, role_name in [
        ("pi_user", "PI"),
        ("steward_user", "steward"),
        ("researcher_user", "researcher"),
    ]:
        test_db.add(Membership(
            project_id=project.id,
            user_id=users[username].id,
            role_name=role_name,
            created_by=users["pi_user"].id,
        ))
    test_db.commit()

    # RDMP with fields
    rdmp_json = {
        "name": "Test RDMP",
        "fields": [
            {"key": "tissue_type", "label": "Tissue Type", "type": "categorical",
             "required": True, "allowed_values": ["brain", "liver", "kidney"]},
            {"key": "treatment", "label": "Treatment", "type": "string",
             "required": False},
            {"key": "concentration", "label": "Concentration", "type": "number",
             "required": False},
        ],
        "roles": [
            {"name": "PI", "permissions": {
                "can_edit_metadata": True, "can_edit_paths": True,
                "can_create_release": True, "can_manage_rdmp": True,
            }},
            {"name": "steward", "permissions": {
                "can_edit_metadata": True, "can_edit_paths": True,
                "can_create_release": False, "can_manage_rdmp": True,
            }},
            {"name": "researcher", "permissions": {
                "can_edit_metadata": False, "can_edit_paths": False,
                "can_create_release": False, "can_manage_rdmp": False,
            }},
        ],
    }
    rdmp = RDMPVersion(
        project_id=project.id,
        version_int=1,
        title="Test RDMP",
        status=RDMPStatus.ACTIVE,
        rdmp_json=rdmp_json,
        created_by=users["pi_user"].id,
        approved_by=users["pi_user"].id,
    )
    test_db.add(rdmp)
    test_db.commit()
    test_db.refresh(rdmp)

    # Storage root + raw data item
    storage_root = StorageRoot(
        project_id=project.id, name="primary-store",
    )
    test_db.add(storage_root)
    test_db.commit()
    test_db.refresh(storage_root)

    raw_data = RawDataItem(
        project_id=project.id,
        storage_root_id=storage_root.id,
        relative_path="data/experiment1.fastq.gz",
        storage_owner_user_id=users["pi_user"].id,
        created_by=users["pi_user"].id,
    )
    test_db.add(raw_data)
    test_db.commit()
    test_db.refresh(raw_data)

    return {
        "supervisor": sup,
        "project": project,
        "rdmp": rdmp,
        "storage_root": storage_root,
        "raw_data": raw_data,
    }


def get_auth_headers(client, username, password="test123"):
    """Get auth headers for a user."""
    response = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_csv(rows: list[list[str]]) -> bytes:
    """Build CSV bytes from a list of rows (first row = header)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Template export
# ---------------------------------------------------------------------------

class TestTemplateExport:
    """Test template download and info endpoints."""

    def test_active_rdmp_csv_headers(self, client, users, setup):
        """ACTIVE RDMP → CSV headers match expected columns."""
        headers = get_auth_headers(client, "pi_user")
        project_id = setup["project"].id

        response = client.get(
            f"/api/projects/{project_id}/ingest/sample-template",
            headers=headers,
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert response.headers["x-rdmp-status"] == "ACTIVE"
        assert "x-template-hash" in response.headers

        # Parse returned CSV
        reader = csv.reader(io.StringIO(response.text))
        csv_headers = next(reader)

        assert csv_headers == [
            "sample_name", "visibility",
            "tissue_type", "treatment", "concentration",
        ]

    def test_draft_rdmp_allowed_and_audited(self, client, test_db, users, setup):
        """DRAFT RDMP → template allowed; audit records draft usage."""
        project_id = setup["project"].id

        # Supersede the active RDMP and create a draft-only one
        setup["rdmp"].status = RDMPStatus.SUPERSEDED
        draft_rdmp = RDMPVersion(
            project_id=project_id,
            version_int=2,
            title="Draft RDMP",
            status=RDMPStatus.DRAFT,
            rdmp_json={"name": "Draft", "fields": [
                {"key": "species", "label": "Species", "type": "string", "required": True},
            ], "roles": []},
            created_by=users["pi_user"].id,
        )
        test_db.add(draft_rdmp)
        test_db.commit()
        test_db.refresh(draft_rdmp)

        headers = get_auth_headers(client, "pi_user")
        response = client.get(
            f"/api/projects/{project_id}/ingest/sample-template",
            headers=headers,
        )

        assert response.status_code == 200
        assert response.headers["x-rdmp-status"] == "DRAFT"

        # Check audit recorded draft usage
        audit = (
            test_db.query(AuditLog)
            .filter(AuditLog.action_type == "INGEST_TEMPLATE_GENERATED")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.after_json["rdmp_status"] == "DRAFT"
        assert audit.after_json["rdmp_id"] == draft_rdmp.id

    def test_no_rdmp_returns_409(self, client, test_db, users, setup):
        """No RDMP → 409."""
        project_id = setup["project"].id

        # Remove all RDMPs
        test_db.query(RDMPVersion).filter(
            RDMPVersion.project_id == project_id
        ).delete()
        test_db.commit()

        headers = get_auth_headers(client, "pi_user")
        response = client.get(
            f"/api/projects/{project_id}/ingest/sample-template",
            headers=headers,
        )
        assert response.status_code == 409

    def test_template_info_endpoint(self, client, users, setup):
        """Info endpoint returns column definitions without CSV download."""
        headers = get_auth_headers(client, "pi_user")
        project_id = setup["project"].id

        response = client.get(
            f"/api/projects/{project_id}/ingest/sample-template/info",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rdmp_status"] == "ACTIVE"
        keys = [c["key"] for c in data["columns"]]
        assert "sample_name" in keys
        assert "tissue_type" in keys


# ---------------------------------------------------------------------------
# CSV preview
# ---------------------------------------------------------------------------

class TestCSVPreview:
    """Test CSV validation/preview (confirm=false)."""

    def test_detects_missing_required_columns(self, client, users, setup):
        """CSV missing sample_name column → error."""
        headers = get_auth_headers(client, "pi_user")
        project_id = setup["project"].id
        raw_data_id = setup["raw_data"].id

        csv_data = make_csv([
            ["visibility", "tissue_type"],
            ["PRIVATE", "brain"],
        ])

        response = client.post(
            f"/api/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "false"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["can_import"] is False
        assert any("sample_name" in e["message"] for e in data["errors"])

    def test_detects_duplicate_sample_name_within_file(self, client, users, setup):
        """Duplicate sample_name within the same CSV → error."""
        headers = get_auth_headers(client, "pi_user")
        project_id = setup["project"].id
        raw_data_id = setup["raw_data"].id

        csv_data = make_csv([
            ["sample_name", "tissue_type"],
            ["S001", "brain"],
            ["S001", "liver"],
        ])

        response = client.post(
            f"/api/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "false"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["can_import"] is False
        assert any("Duplicate" in e["message"] for e in data["errors"])

    def test_detects_duplicate_sample_name_vs_existing(self, client, test_db, users, setup):
        """Sample name that already exists in project → error."""
        project_id = setup["project"].id
        raw_data_id = setup["raw_data"].id

        # Create an existing sample
        existing = Sample(
            project_id=project_id,
            sample_identifier="EXISTING_01",
            created_by=users["pi_user"].id,
        )
        test_db.add(existing)
        test_db.commit()

        headers = get_auth_headers(client, "pi_user")
        csv_data = make_csv([
            ["sample_name", "tissue_type"],
            ["EXISTING_01", "brain"],
        ])

        response = client.post(
            f"/api/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "false"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["can_import"] is False
        assert any("already exists" in e["message"] for e in data["errors"])

    def test_valid_csv_preview(self, client, users, setup):
        """Valid CSV → can_import=true, no errors."""
        headers = get_auth_headers(client, "pi_user")
        project_id = setup["project"].id
        raw_data_id = setup["raw_data"].id

        csv_data = make_csv([
            ["sample_name", "tissue_type", "treatment", "concentration"],
            ["S001", "brain", "control", "1.5"],
            ["S002", "liver", "treated", "2.0"],
        ])

        response = client.post(
            f"/api/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "false"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["can_import"] is True
        assert data["total_rows"] == 2
        assert data["valid_rows"] == 2
        assert data["errors"] == []

    def test_invalid_categorical_value(self, client, users, setup):
        """Invalid categorical value → error."""
        headers = get_auth_headers(client, "pi_user")
        project_id = setup["project"].id
        raw_data_id = setup["raw_data"].id

        csv_data = make_csv([
            ["sample_name", "tissue_type"],
            ["S001", "invalid_tissue"],
        ])

        response = client.post(
            f"/api/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "false"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["can_import"] is False
        assert any("tissue_type" == e["column"] for e in data["errors"])


# ---------------------------------------------------------------------------
# CSV import (confirm=true)
# ---------------------------------------------------------------------------

class TestCSVImport:
    """Test confirmed CSV import."""

    def test_import_creates_samples_and_audit(self, client, test_db, users, setup):
        """Confirmed import creates N samples and emits audit event with method=csv."""
        headers = get_auth_headers(client, "pi_user")
        project_id = setup["project"].id
        raw_data_id = setup["raw_data"].id

        csv_data = make_csv([
            ["sample_name", "tissue_type", "treatment", "concentration", "visibility"],
            ["S001", "brain", "control", "1.5", "PRIVATE"],
            ["S002", "liver", "treated", "2.0", "INSTITUTION"],
            ["S003", "kidney", "", "", "PUBLIC"],
        ])

        response = client.post(
            f"/api/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "true"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 3
        assert len(data["sample_ids"]) == 3

        # Verify samples in DB
        samples = test_db.query(Sample).filter(
            Sample.project_id == project_id
        ).all()
        assert len(samples) == 3
        identifiers = {s.sample_identifier for s in samples}
        assert identifiers == {"S001", "S002", "S003"}

        # Verify field values created
        field_values = test_db.query(SampleFieldValue).all()
        tissue_vals = [fv for fv in field_values if fv.field_key == "tissue_type"]
        assert len(tissue_vals) == 3

        # Verify audit event
        audit = (
            test_db.query(AuditLog)
            .filter(AuditLog.action_type == "INGEST_SAMPLES_CREATED")
            .first()
        )
        assert audit is not None
        assert audit.after_json["method"] == "csv"
        assert audit.after_json["count"] == 3
        assert len(audit.after_json["sample_ids"]) == 3

    def test_import_failure_no_samples_created(self, client, test_db, users, setup):
        """CSV with invalid row + confirm=true → 400, no samples created."""
        headers = get_auth_headers(client, "pi_user")
        project_id = setup["project"].id
        raw_data_id = setup["raw_data"].id

        csv_data = make_csv([
            ["sample_name", "tissue_type"],
            ["S001", "brain"],
            ["S001", "liver"],  # Duplicate name
        ])

        response = client.post(
            f"/api/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "true"},
        )

        assert response.status_code == 400

        # No samples should have been created
        count = test_db.query(Sample).filter(
            Sample.project_id == project_id
        ).count()
        assert count == 0

        # No creation audit event
        audit = (
            test_db.query(AuditLog)
            .filter(AuditLog.action_type == "INGEST_SAMPLES_CREATED")
            .first()
        )
        assert audit is None

    def test_empty_csv_rejected(self, client, users, setup):
        """CSV with headers only → 400 on confirm."""
        headers = get_auth_headers(client, "pi_user")
        project_id = setup["project"].id
        raw_data_id = setup["raw_data"].id

        csv_data = make_csv([
            ["sample_name", "tissue_type"],
        ])

        response = client.post(
            f"/api/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "true"},
        )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Lab scoping
# ---------------------------------------------------------------------------

class TestLabScoping:
    """Test that ingest template respects project access."""

    def test_outsider_cannot_download_template(self, client, users, setup):
        """User not in lab/project cannot download template."""
        headers = get_auth_headers(client, "outsider_user")
        project_id = setup["project"].id

        response = client.get(
            f"/api/projects/{project_id}/ingest/sample-template",
            headers=headers,
        )
        assert response.status_code == 403

    def test_outsider_cannot_import_csv(self, client, users, setup):
        """User not in lab/project cannot import CSV."""
        headers = get_auth_headers(client, "outsider_user")
        project_id = setup["project"].id
        raw_data_id = setup["raw_data"].id

        csv_data = make_csv([
            ["sample_name", "tissue_type"],
            ["S001", "brain"],
        ])

        response = client.post(
            f"/api/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "true"},
        )
        assert response.status_code == 403

    def test_researcher_cannot_import_without_edit_permission(self, client, test_db, users, setup):
        """Researcher without can_edit_metadata cannot import samples."""
        # The researcher role by default should not have can_edit_metadata
        # unless the RDMP grants it. We test against the permission check.
        headers = get_auth_headers(client, "researcher_user")
        project_id = setup["project"].id
        raw_data_id = setup["raw_data"].id

        csv_data = make_csv([
            ["sample_name", "tissue_type"],
            ["S001", "brain"],
        ])

        response = client.post(
            f"/api/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "true"},
        )
        assert response.status_code == 403

    def test_raw_data_cross_project_rejected(self, client, test_db, users, setup):
        """Raw data item from different project → 400."""
        # Create a second project with its own raw data item
        project_b = Project(
            name="Other Project",
            description="Different project",
            supervisor_id=setup["supervisor"].id,
            created_by=users["pi_user"].id,
        )
        test_db.add(project_b)
        test_db.commit()
        test_db.refresh(project_b)

        test_db.add(Membership(
            project_id=project_b.id,
            user_id=users["pi_user"].id,
            role_name="PI",
            created_by=users["pi_user"].id,
        ))
        test_db.commit()

        sr = StorageRoot(project_id=project_b.id, name="other-store")
        test_db.add(sr)
        test_db.commit()
        test_db.refresh(sr)

        other_raw = RawDataItem(
            project_id=project_b.id,
            storage_root_id=sr.id,
            relative_path="other/file.txt",
            storage_owner_user_id=users["pi_user"].id,
            created_by=users["pi_user"].id,
        )
        test_db.add(other_raw)
        test_db.commit()
        test_db.refresh(other_raw)

        # Try to import into project A using project B's raw data item
        headers = get_auth_headers(client, "pi_user")
        csv_data = make_csv([
            ["sample_name", "tissue_type"],
            ["S001", "brain"],
        ])

        response = client.post(
            f"/api/projects/{setup['project'].id}/raw-data/{other_raw.id}/samples:import-csv",
            headers=headers,
            files={"file": ("samples.csv", csv_data, "text/csv")},
            params={"confirm": "true"},
        )
        assert response.status_code == 400
        assert "does not belong" in response.json()["detail"]
