"""Tests for storage roots, mappings, and raw data API."""

import pytest
from supervisor.models.storage import StorageRoot
from supervisor.models.raw_data import RawDataItem, PathChange
from supervisor.models.sample import Sample
from supervisor.models.audit import AuditLog
from supervisor.models.membership import Membership


class TestStorageRoots:
    """Tests for storage root API endpoints."""

    def test_create_storage_root(
        self, client, db, test_project, test_membership, test_rdmp, auth_headers
    ):
        """Test creating a storage root."""
        response = client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Main Storage", "description": "Primary data storage"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Main Storage"
        assert data["description"] == "Primary data storage"
        assert data["project_id"] == test_project.id

        # Verify audit log was created
        audit_log = db.query(AuditLog).filter(
            AuditLog.target_type == "StorageRoot",
            AuditLog.action_type == "CREATE",
        ).first()
        assert audit_log is not None
        assert audit_log.after_json["name"] == "Main Storage"

    def test_create_storage_root_duplicate_name(
        self, client, db, test_project, test_membership, test_rdmp, auth_headers
    ):
        """Test that duplicate storage root names are rejected."""
        # Create first storage root
        client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Main Storage"},
            headers=auth_headers,
        )

        # Try to create duplicate
        response = client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Main Storage"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_list_storage_roots(
        self, client, db, test_project, test_membership, test_rdmp, auth_headers
    ):
        """Test listing storage roots."""
        # Create some storage roots
        for i in range(3):
            client.post(
                f"/api/projects/{test_project.id}/storage-roots",
                json={"name": f"Storage {i}"},
                headers=auth_headers,
            )

        response = client.get(
            f"/api/projects/{test_project.id}/storage-roots",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_create_storage_root_no_permission(
        self, client, db, test_project, test_user2, test_rdmp, auth_headers_user2
    ):
        """Test that users without can_manage_rdmp cannot create storage roots."""
        # Add user2 as viewer (no permissions)
        membership = Membership(
            project_id=test_project.id,
            user_id=test_user2.id,
            role_name="viewer",
            created_by=test_user2.id,
        )
        db.add(membership)
        db.commit()

        response = client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Test Storage"},
            headers=auth_headers_user2,
        )
        assert response.status_code == 403


class TestStorageRootMappings:
    """Tests for storage root mapping API endpoints."""

    def test_create_mapping(
        self, client, db, test_project, test_membership, test_rdmp, auth_headers
    ):
        """Test creating a storage root mapping."""
        # Create storage root first
        sr_response = client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Main Storage"},
            headers=auth_headers,
        )
        storage_root_id = sr_response.json()["id"]

        # Create mapping
        response = client.post(
            f"/api/storage-roots/{storage_root_id}/mappings",
            json={"local_mount_path": "/Users/testuser/data"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["local_mount_path"] == "/Users/testuser/data"
        assert data["storage_root_id"] == storage_root_id

    def test_update_mapping(
        self, client, db, test_project, test_membership, test_rdmp, auth_headers
    ):
        """Test updating an existing storage root mapping."""
        # Create storage root
        sr_response = client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Main Storage"},
            headers=auth_headers,
        )
        storage_root_id = sr_response.json()["id"]

        # Create mapping
        client.post(
            f"/api/storage-roots/{storage_root_id}/mappings",
            json={"local_mount_path": "/old/path"},
            headers=auth_headers,
        )

        # Update mapping
        response = client.post(
            f"/api/storage-roots/{storage_root_id}/mappings",
            json={"local_mount_path": "/new/path"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["local_mount_path"] == "/new/path"

    def test_list_mappings(
        self, client, db, test_project, test_membership, test_rdmp, auth_headers
    ):
        """Test listing storage root mappings."""
        # Create storage root and mapping
        sr_response = client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Main Storage"},
            headers=auth_headers,
        )
        storage_root_id = sr_response.json()["id"]

        client.post(
            f"/api/storage-roots/{storage_root_id}/mappings",
            json={"local_mount_path": "/Users/testuser/data"},
            headers=auth_headers,
        )

        response = client.get(
            f"/api/storage-roots/{storage_root_id}/mappings",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestRawDataItems:
    """Tests for raw data item API endpoints."""

    @pytest.fixture
    def storage_root(self, client, test_project, test_membership, test_rdmp, auth_headers, db):
        """Create a storage root for raw data tests."""
        response = client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Main Storage"},
            headers=auth_headers,
        )
        return response.json()

    @pytest.fixture
    def sample(self, client, test_project, test_membership, test_rdmp, auth_headers, db):
        """Create a sample for raw data tests."""
        response = client.post(
            f"/api/projects/{test_project.id}/samples",
            json={"sample_identifier": "SAMPLE-001"},
            headers=auth_headers,
        )
        return response.json()

    def test_create_raw_data_item(
        self, client, db, test_project, storage_root, auth_headers
    ):
        """Test creating a raw data item."""
        response = client.post(
            f"/api/projects/{test_project.id}/raw-data",
            json={
                "storage_root_id": storage_root["id"],
                "relative_path": "experiment1/data.csv",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["relative_path"] == "experiment1/data.csv"
        assert data["storage_root_id"] == storage_root["id"]

        # Verify audit log
        audit_log = db.query(AuditLog).filter(
            AuditLog.target_type == "RawDataItem",
            AuditLog.action_type == "CREATE",
        ).first()
        assert audit_log is not None

    def test_create_raw_data_item_with_sample(
        self, client, db, test_project, storage_root, sample, auth_headers
    ):
        """Test creating a raw data item linked to a sample."""
        response = client.post(
            f"/api/projects/{test_project.id}/raw-data",
            json={
                "storage_root_id": storage_root["id"],
                "relative_path": "experiment1/data.csv",
                "sample_id": sample["id"],
                "file_size_bytes": 1024,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["sample_id"] == sample["id"]
        assert data["file_size_bytes"] == 1024

    def test_create_raw_data_item_absolute_path_rejected(
        self, client, test_project, storage_root, auth_headers
    ):
        """Test that absolute paths are rejected."""
        response = client.post(
            f"/api/projects/{test_project.id}/raw-data",
            json={
                "storage_root_id": storage_root["id"],
                "relative_path": "/absolute/path/data.csv",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_raw_data_item_path_traversal_rejected(
        self, client, test_project, storage_root, auth_headers
    ):
        """Test that path traversal is rejected."""
        response = client.post(
            f"/api/projects/{test_project.id}/raw-data",
            json={
                "storage_root_id": storage_root["id"],
                "relative_path": "experiment1/../../../etc/passwd",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_raw_data_item_duplicate_path_rejected(
        self, client, test_project, storage_root, auth_headers
    ):
        """Test that duplicate paths in the same storage root are rejected."""
        # Create first item
        client.post(
            f"/api/projects/{test_project.id}/raw-data",
            json={
                "storage_root_id": storage_root["id"],
                "relative_path": "experiment1/data.csv",
            },
            headers=auth_headers,
        )

        # Try to create duplicate
        response = client.post(
            f"/api/projects/{test_project.id}/raw-data",
            json={
                "storage_root_id": storage_root["id"],
                "relative_path": "experiment1/data.csv",
            },
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_list_raw_data_items(
        self, client, test_project, storage_root, auth_headers
    ):
        """Test listing raw data items."""
        # Create some items
        for i in range(3):
            client.post(
                f"/api/projects/{test_project.id}/raw-data",
                json={
                    "storage_root_id": storage_root["id"],
                    "relative_path": f"experiment{i}/data.csv",
                },
                headers=auth_headers,
            )

        response = client.get(
            f"/api/projects/{test_project.id}/raw-data",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_list_raw_data_items_filter_by_sample(
        self, client, test_project, storage_root, sample, auth_headers
    ):
        """Test filtering raw data items by sample."""
        # Create items with and without sample
        client.post(
            f"/api/projects/{test_project.id}/raw-data",
            json={
                "storage_root_id": storage_root["id"],
                "relative_path": "with_sample.csv",
                "sample_id": sample["id"],
            },
            headers=auth_headers,
        )
        client.post(
            f"/api/projects/{test_project.id}/raw-data",
            json={
                "storage_root_id": storage_root["id"],
                "relative_path": "without_sample.csv",
            },
            headers=auth_headers,
        )

        # Filter by sample
        response = client.get(
            f"/api/projects/{test_project.id}/raw-data",
            params={"sample_id": sample["id"]},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["relative_path"] == "with_sample.csv"

    def test_get_raw_data_item(
        self, client, test_project, storage_root, auth_headers
    ):
        """Test getting a specific raw data item."""
        # Create item
        create_response = client.post(
            f"/api/projects/{test_project.id}/raw-data",
            json={
                "storage_root_id": storage_root["id"],
                "relative_path": "test/data.csv",
            },
            headers=auth_headers,
        )
        item_id = create_response.json()["id"]

        # Get item
        response = client.get(
            f"/api/raw-data/{item_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item_id
        assert data["storage_root_name"] == "Main Storage"


class TestPathUpdates:
    """Tests for raw data path update API."""

    @pytest.fixture
    def storage_root(self, client, test_project, test_membership, test_rdmp, auth_headers, db):
        """Create a storage root."""
        response = client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Main Storage"},
            headers=auth_headers,
        )
        return response.json()

    @pytest.fixture
    def storage_root2(self, client, test_project, test_membership, test_rdmp, auth_headers, db):
        """Create a second storage root."""
        response = client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Backup Storage"},
            headers=auth_headers,
        )
        return response.json()

    @pytest.fixture
    def raw_data_item(self, client, test_project, storage_root, auth_headers, db):
        """Create a raw data item."""
        response = client.post(
            f"/api/projects/{test_project.id}/raw-data",
            json={
                "storage_root_id": storage_root["id"],
                "relative_path": "original/path/data.csv",
            },
            headers=auth_headers,
        )
        return response.json()

    def test_update_path(
        self, client, db, test_project, storage_root, raw_data_item, auth_headers
    ):
        """Test updating a raw data item's path."""
        response = client.put(
            f"/api/raw-data/{raw_data_item['id']}/path",
            json={
                "new_storage_root_id": storage_root["id"],
                "new_relative_path": "new/path/data.csv",
                "reason": "File was moved",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["relative_path"] == "new/path/data.csv"

        # Verify PathChange was created
        path_change = db.query(PathChange).filter(
            PathChange.raw_data_item_id == raw_data_item["id"]
        ).first()
        assert path_change is not None
        assert path_change.old_relative_path == "original/path/data.csv"
        assert path_change.new_relative_path == "new/path/data.csv"
        assert path_change.reason == "File was moved"

        # Verify AuditLog was created
        audit_log = db.query(AuditLog).filter(
            AuditLog.target_type == "RawDataItem",
            AuditLog.action_type == "UPDATE",
        ).first()
        assert audit_log is not None

    def test_update_path_change_storage_root(
        self, client, db, storage_root, storage_root2, raw_data_item, auth_headers
    ):
        """Test moving a raw data item to a different storage root."""
        response = client.put(
            f"/api/raw-data/{raw_data_item['id']}/path",
            json={
                "new_storage_root_id": storage_root2["id"],
                "new_relative_path": "backup/data.csv",
                "reason": "Moved to backup storage",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["storage_root_id"] == storage_root2["id"]
        assert data["relative_path"] == "backup/data.csv"

    def test_get_path_history(
        self, client, db, storage_root, raw_data_item, auth_headers
    ):
        """Test getting path change history."""
        # Make some path changes
        for i in range(3):
            client.put(
                f"/api/raw-data/{raw_data_item['id']}/path",
                json={
                    "new_storage_root_id": storage_root["id"],
                    "new_relative_path": f"path{i}/data.csv",
                    "reason": f"Change {i}",
                },
                headers=auth_headers,
            )

        response = client.get(
            f"/api/raw-data/{raw_data_item['id']}/path-history",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3


class TestIngestWorkflow:
    """Tests simulating the full ingest workflow."""

    def test_full_ingest_workflow(
        self, client, db, test_project, test_membership, test_rdmp, auth_headers, test_user
    ):
        """Test a complete ingest workflow: storage root -> mapping -> sample -> raw data."""
        # 1. Create storage root
        sr_response = client.post(
            f"/api/projects/{test_project.id}/storage-roots",
            json={"name": "Lab NAS", "description": "Network attached storage in the lab"},
            headers=auth_headers,
        )
        assert sr_response.status_code == 201
        storage_root_id = sr_response.json()["id"]

        # 2. Create mapping for current user
        mapping_response = client.post(
            f"/api/storage-roots/{storage_root_id}/mappings",
            json={"local_mount_path": "/Volumes/LabNAS"},
            headers=auth_headers,
        )
        assert mapping_response.status_code == 201

        # 3. Create sample
        sample_response = client.post(
            f"/api/projects/{test_project.id}/samples",
            json={"sample_identifier": "EXP-2024-001"},
            headers=auth_headers,
        )
        assert sample_response.status_code == 201
        sample_id = sample_response.json()["id"]

        # 4. Register raw data files for the sample
        files = [
            "EXP-2024-001/run1/data.csv",
            "EXP-2024-001/run1/metadata.json",
            "EXP-2024-001/run2/data.csv",
        ]
        raw_data_ids = []
        for file_path in files:
            raw_response = client.post(
                f"/api/projects/{test_project.id}/raw-data",
                json={
                    "storage_root_id": storage_root_id,
                    "relative_path": file_path,
                    "sample_id": sample_id,
                    "file_size_bytes": 1024,
                },
                headers=auth_headers,
            )
            assert raw_response.status_code == 201
            raw_data_ids.append(raw_response.json()["id"])

        # 5. Set some sample metadata
        field_response = client.put(
            f"/api/samples/{sample_id}/fields/gene_name",
            json={"value": "ACTB"},
            headers=auth_headers,
        )
        assert field_response.status_code == 200

        # 6. Verify the data
        # List raw data for sample
        list_response = client.get(
            f"/api/projects/{test_project.id}/raw-data",
            params={"sample_id": sample_id},
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        raw_data_list = list_response.json()
        assert len(raw_data_list) == 3

        # Check sample completeness
        sample_response = client.get(
            f"/api/samples/{sample_id}",
            headers=auth_headers,
        )
        assert sample_response.status_code == 200
        sample_data = sample_response.json()
        assert sample_data["fields"]["gene_name"] == "ACTB"

        # 7. Verify audit trail
        audit_logs = db.query(AuditLog).filter(
            AuditLog.project_id == test_project.id
        ).all()
        # Should have: 1 storage root + 1 mapping + 3 raw data items = 5 CREATE actions
        create_logs = [log for log in audit_logs if log.action_type == "CREATE"]
        assert len(create_logs) >= 5
