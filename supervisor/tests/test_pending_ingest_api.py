"""Tests for pending ingest API endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestPendingIngestAPI:
    """Tests for the pending ingest workflow."""

    def test_create_pending_ingest(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """Test creating a new pending ingest."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create pending ingest
        response = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/sample001.raw",
                "inferred_sample_identifier": "SAMPLE-001",
                "file_size_bytes": 1024,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["project_id"] == test_project.id
        assert data["storage_root_id"] == test_storage_root.id
        assert data["relative_path"] == "data/sample001.raw"
        assert data["inferred_sample_identifier"] == "SAMPLE-001"
        assert data["status"] == "PENDING"
        assert data["file_size_bytes"] == 1024

    def test_list_pending_ingests(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """Test listing pending ingests for a project."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create two pending ingests
        for i in range(2):
            client.post(
                f"/api/projects/{test_project.id}/pending-ingests",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "storage_root_id": test_storage_root.id,
                    "relative_path": f"data/file{i}.raw",
                },
            )

        # List pending ingests
        response = client.get(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_pending_ingests_filter_by_status(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """Test filtering pending ingests by status."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create pending ingest
        create_resp = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/file.raw",
            },
        )
        assert create_resp.status_code == 201

        # List only PENDING
        response = client.get(
            f"/api/projects/{test_project.id}/pending-ingests?status_filter=PENDING",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "PENDING"

        # List only COMPLETED (should be empty)
        response = client.get(
            f"/api/projects/{test_project.id}/pending-ingests?status_filter=COMPLETED",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_pending_ingest(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """Test getting a single pending ingest."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create pending ingest
        create_response = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/file.raw",
            },
        )
        assert create_response.status_code == 201
        pending_id = create_response.json()["id"]

        # Get pending ingest
        response = client.get(
            f"/api/pending-ingests/{pending_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == pending_id
        assert data["relative_path"] == "data/file.raw"

    def test_finalize_pending_ingest_no_sample(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """Test finalizing a pending ingest without creating a sample."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create pending ingest
        create_response = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/orphan.raw",
            },
        )
        assert create_response.status_code == 201
        pending_id = create_response.json()["id"]

        # Finalize without sample
        response = client.post(
            f"/api/pending-ingests/{pending_id}/finalize",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["relative_path"] == "data/orphan.raw"
        assert data["sample_id"] is None

        # Verify pending ingest is now COMPLETED
        get_response = client.get(
            f"/api/pending-ingests/{pending_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_response.json()["status"] == "COMPLETED"

    def test_finalize_pending_ingest_create_new_sample(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """Test finalizing a pending ingest with a new sample."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create pending ingest
        create_response = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/newsample.raw",
            },
        )
        assert create_response.status_code == 201
        pending_id = create_response.json()["id"]

        # Finalize with new sample
        response = client.post(
            f"/api/pending-ingests/{pending_id}/finalize",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "sample_identifier": "NEW-SAMPLE-001",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["relative_path"] == "data/newsample.raw"
        assert data["sample_id"] is not None

        # Verify sample was created
        samples_response = client.get(
            f"/api/projects/{test_project.id}/samples",
            headers={"Authorization": f"Bearer {token}"},
        )
        sample_ids = [s["sample_identifier"] for s in samples_response.json()["items"]]
        assert "NEW-SAMPLE-001" in sample_ids

    def test_finalize_pending_ingest_link_existing_sample(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp, test_sample
    ):
        """Test finalizing a pending ingest linked to an existing sample."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create pending ingest
        create_response = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/existing.raw",
            },
        )
        assert create_response.status_code == 201
        pending_id = create_response.json()["id"]

        # Finalize linking to existing sample
        response = client.post(
            f"/api/pending-ingests/{pending_id}/finalize",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "sample_id": test_sample.id,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sample_id"] == test_sample.id

    def test_cancel_pending_ingest(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """Test cancelling a pending ingest."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create pending ingest
        create_response = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/cancel.raw",
            },
        )
        assert create_response.status_code == 201
        pending_id = create_response.json()["id"]

        # Cancel
        response = client.delete(
            f"/api/pending-ingests/{pending_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"

    def test_finalize_already_completed_fails(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """Test that finalizing an already completed ingest fails."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create and finalize pending ingest
        create_response = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/complete.raw",
            },
        )
        assert create_response.status_code == 201
        pending_id = create_response.json()["id"]

        # First finalize
        client.post(
            f"/api/pending-ingests/{pending_id}/finalize",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )

        # Second finalize should fail
        response = client.post(
            f"/api/pending-ingests/{pending_id}/finalize",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )

        assert response.status_code == 400
        assert "not in PENDING status" in response.json()["detail"]

    def test_cancel_already_cancelled_fails(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """Test that cancelling an already cancelled ingest fails."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create and cancel pending ingest
        create_response = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/cancel2.raw",
            },
        )
        assert create_response.status_code == 201
        pending_id = create_response.json()["id"]

        # First cancel
        client.delete(
            f"/api/pending-ingests/{pending_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Second cancel should fail
        response = client.delete(
            f"/api/pending-ingests/{pending_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        assert "not in PENDING status" in response.json()["detail"]

    def test_pending_ingest_duplicate_path_rejected(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """Test that duplicate paths in pending ingests are rejected."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create first pending ingest
        first_resp = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/duplicate.raw",
            },
        )
        assert first_resp.status_code == 201

        # Try to create second with same path
        response = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/duplicate.raw",
            },
        )

        assert response.status_code == 400
        assert "already pending" in response.json()["detail"].lower()

    def test_get_pending_ingest_includes_project_data_for_deep_link(
        self, client, db, test_user, test_project, test_membership, test_storage_root, test_rdmp
    ):
        """
        Regression test for deep linking: fetching a pending ingest by ID
        must include project_id, project_name, and storage_root_name so the
        UI can load project context without requiring prior project selection.
        """
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create pending ingest with inferred sample identifier
        create_response = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/deeplink-test.raw",
                "inferred_sample_identifier": "DEEPLINK-001",
                "file_size_bytes": 2048,
            },
        )
        assert create_response.status_code == 201
        pending_id = create_response.json()["id"]

        # Fetch pending ingest by ID (simulates UI deep link to /ingest/{id})
        response = client.get(
            f"/api/pending-ingests/{pending_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all data needed for deep linking is present
        assert data["id"] == pending_id
        assert data["project_id"] == test_project.id
        assert data["storage_root_id"] == test_storage_root.id
        assert data["relative_path"] == "data/deeplink-test.raw"
        assert data["inferred_sample_identifier"] == "DEEPLINK-001"
        assert data["file_size_bytes"] == 2048
        assert data["status"] == "PENDING"
        # These fields are populated by the API to help the UI
        assert "project_name" in data
        assert "storage_root_name" in data
