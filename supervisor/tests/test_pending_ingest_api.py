"""Tests for pending ingest API endpoints."""

import pytest
from fastapi.testclient import TestClient
from supervisor.models.rdmp import RDMPVersion, RDMPStatus


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

    # ------------------------------------------------------------------
    # Multi-sample finalize tests
    # ------------------------------------------------------------------

    def _make_multi_rdmp(self, db, test_project, test_user) -> RDMPVersion:
        """Create and activate a multi-sample RDMP for the test project."""
        rdmp_json = {
            "name": "Multi RDMP",
            "roles": [
                {
                    "name": "PI",
                    "permissions": {
                        "can_edit_metadata": True,
                        "can_edit_paths": True,
                        "can_create_release": True,
                        "can_manage_rdmp": True,
                    },
                }
            ],
            "fields": [],
            "ingest": {
                "measured_samples_mode": "multi",
                "multi": {
                    "annotation_key": "observation",
                    "index_fields": ["position", "target"],
                    "run_fields": [
                        {"key": "run_notes", "label": "Run notes", "type": "text"}
                    ],
                },
            },
        }
        rdmp = RDMPVersion(
            project_id=test_project.id,
            version_int=2,
            status=RDMPStatus.ACTIVE,
            title="Multi RDMP",
            rdmp_json=rdmp_json,
            provenance_json={},
            created_by=test_user.id,
        )
        db.add(rdmp)
        db.commit()
        db.refresh(rdmp)
        return rdmp

    def test_multi_finalize_creates_null_sample_item_and_annotations(
        self,
        client,
        db,
        test_user,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_sample,
    ):
        """Multi finalize creates RawDataItem(sample_id=NULL) + run/measured annotations."""
        self._make_multi_rdmp(db, test_project, test_user)

        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create second sample
        s2_resp = client.post(
            f"/api/projects/{test_project.id}/samples",
            headers={"Authorization": f"Bearer {token}"},
            json={"sample_identifier": "SAMPLE-002"},
        )
        assert s2_resp.status_code == 201
        sample2_id = s2_resp.json()["id"]

        # Create pending ingest
        create_resp = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/multi_run.csv",
            },
        )
        assert create_resp.status_code == 201
        pending_id = create_resp.json()["id"]

        # Multi finalize
        response = client.post(
            f"/api/pending-ingests/{pending_id}/finalize",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "run_annotations": [
                    {"key": "run_notes", "sample_id": None, "value_text": "Plate 1 run"}
                ],
                "measured_samples": [
                    {
                        "key": "observation",
                        "sample_id": test_sample.id,
                        "index": {"position": "A1", "target": "GAPDH"},
                        "value_json": {"ct": 22.5},
                    },
                    {
                        "key": "observation",
                        "sample_id": sample2_id,
                        "index": {"position": "A2", "target": "GAPDH"},
                        "value_json": {"ct": 23.1},
                    },
                ],
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["sample_id"] is None  # multi-sample item has no primary sample

        # Verify PendingIngest completed
        get_resp = client.get(
            f"/api/pending-ingests/{pending_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.json()["status"] == "COMPLETED"
        raw_item_id = get_resp.json()["raw_data_item_id"]
        assert raw_item_id is not None

        # Verify annotations created
        ann_resp = client.get(
            f"/api/raw-data/{raw_item_id}/annotations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ann_resp.status_code == 200
        annotations = ann_resp.json()
        # 1 run-level + 2 measured-sample = 3 total
        assert len(annotations) == 3

        run_anns = [a for a in annotations if a["sample_id"] is None]
        sample_anns = [a for a in annotations if a["sample_id"] is not None]
        assert len(run_anns) == 1
        assert run_anns[0]["key"] == "run_notes"
        assert run_anns[0]["value_text"] == "Plate 1 run"
        assert len(sample_anns) == 2

    def test_multi_finalize_rejects_cross_project_sample(
        self,
        client,
        db,
        test_user,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_supervisor,
    ):
        """Multi finalize with a sample from a different project returns 400."""
        from supervisor.models.project import Project
        from supervisor.models.sample import Sample as SampleModel

        self._make_multi_rdmp(db, test_project, test_user)

        # Create a second project and a sample in it
        other_project = Project(
            name="Other Project",
            supervisor_id=test_supervisor.id,
            created_by=test_user.id,
        )
        db.add(other_project)
        db.commit()
        db.refresh(other_project)

        other_sample = SampleModel(
            project_id=other_project.id,
            sample_identifier="OTHER-001",
            created_by=test_user.id,
        )
        db.add(other_sample)
        db.commit()
        db.refresh(other_sample)

        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        create_resp = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/cross_project.csv",
            },
        )
        assert create_resp.status_code == 201
        pending_id = create_resp.json()["id"]

        response = client.post(
            f"/api/pending-ingests/{pending_id}/finalize",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "measured_samples": [
                    {
                        "key": "observation",
                        "sample_id": other_sample.id,
                        "index": {"position": "A1", "target": "GAPDH"},
                    }
                ]
            },
        )
        assert response.status_code == 400

    def test_multi_finalize_sentinel_inserted_when_no_value(
        self,
        client,
        db,
        test_user,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_sample,
    ):
        """Measured-sample rows with no value get sentinel value_json={"present": true}."""
        self._make_multi_rdmp(db, test_project, test_user)

        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        create_resp = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/sentinel_test.csv",
            },
        )
        assert create_resp.status_code == 201
        pending_id = create_resp.json()["id"]

        response = client.post(
            f"/api/pending-ingests/{pending_id}/finalize",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "measured_samples": [
                    {
                        "key": "observation",
                        "sample_id": test_sample.id,
                        "index": {"position": "B3", "target": "ACTB"},
                        # no value_json, no value_text → sentinel
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
        raw_item_id = response.json()["id"]

        ann_resp = client.get(
            f"/api/raw-data/{raw_item_id}/annotations",
            headers={"Authorization": f"Bearer {token}"},
        )
        annotations = ann_resp.json()
        assert len(annotations) == 1
        assert annotations[0]["value_json"] == {"present": True}

    def test_multi_finalize_rejects_missing_rdmp_mode(
        self,
        client,
        db,
        test_user,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_sample,
    ):
        """Multi finalize when RDMP does not set measured_samples_mode=multi returns 400."""
        # test_rdmp fixture provides a single-sample RDMP (no ingest key)
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Activate the existing single-sample RDMP
        from supervisor.models.rdmp import RDMPStatus as _RDMPStatus
        test_rdmp.status = _RDMPStatus.ACTIVE
        db.commit()

        create_resp = client.post(
            f"/api/projects/{test_project.id}/pending-ingests",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "storage_root_id": test_storage_root.id,
                "relative_path": "data/bad_mode.csv",
            },
        )
        assert create_resp.status_code == 201
        pending_id = create_resp.json()["id"]

        response = client.post(
            f"/api/pending-ingests/{pending_id}/finalize",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "measured_samples": [
                    {
                        "key": "observation",
                        "sample_id": test_sample.id,
                        "index": {"position": "A1", "target": "GAPDH"},
                    }
                ]
            },
        )
        assert response.status_code == 400
        assert "multi" in response.json()["detail"].lower()

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
