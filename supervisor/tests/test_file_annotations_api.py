"""Tests for the FileAnnotation API endpoints."""

import pytest

from supervisor.models.annotations import FileAnnotation
from supervisor.models.project import Project
from supervisor.models.raw_data import RawDataItem
from supervisor.models.sample import Sample


# ── Module-level fixtures ────────────────────────────────────────────────────

@pytest.fixture
def test_raw_data_item(db, test_project, test_user, test_storage_root):
    """A RawDataItem belonging to test_project."""
    item = RawDataItem(
        project_id=test_project.id,
        storage_root_id=test_storage_root.id,
        relative_path="data/test_file.raw",
        storage_owner_user_id=test_user.id,
        created_by=test_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def test_sample2(db, test_project, test_user):
    """A second sample in test_project."""
    sample = Sample(
        project_id=test_project.id,
        sample_identifier="SAMPLE-002",
        created_by=test_user.id,
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


@pytest.fixture
def other_project_sample(db, test_user, test_supervisor):
    """A sample belonging to a *different* project (same supervisor)."""
    other = Project(
        name="Other Project",
        created_by=test_user.id,
        supervisor_id=test_supervisor.id,
    )
    db.add(other)
    db.commit()
    db.refresh(other)

    sample = Sample(
        project_id=other.id,
        sample_identifier="OTHER-SAMPLE-001",
        created_by=test_user.id,
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


# ── Test class ───────────────────────────────────────────────────────────────

class TestFileAnnotationsAPI:
    """Tests for the FileAnnotation workflow."""

    # ── helpers ──────────────────────────────────────────────────────────────

    def _login(self, client, username="testuser", password="testpass123") -> dict:
        resp = client.post(
            "/api/auth/login",
            data={"username": username, "password": password},
        )
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def _post_batch(self, client, headers, raw_data_item_id, annotations):
        return client.post(
            f"/api/raw-data/{raw_data_item_id}/annotations",
            headers=headers,
            json={"annotations": annotations},
        )

    # ── 1. Successful batch create ────────────────────────────────────────────

    def test_create_annotations_success(
        self,
        client,
        db,
        test_user,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_sample,
        test_raw_data_item,
    ):
        """Create a file-level and a sample-linked annotation in one batch."""
        headers = self._login(client)

        payload = [
            {
                "key": "observation",
                "value_text": "bands look clean",
            },
            {
                "key": "sample_map",
                "sample_id": test_sample.id,
                "index": {"position": 1},
                "value_json": {"condition": "treated"},
                "value_text": "position 1",
            },
        ]

        resp = self._post_batch(client, headers, test_raw_data_item.id, payload)

        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 2

        # File-level annotation
        file_ann = next(d for d in data if d["sample_id"] is None)
        assert file_ann["key"] == "observation"
        assert file_ann["value_text"] == "bands look clean"
        assert file_ann["value_json"] is None
        assert file_ann["index"] is None
        assert file_ann["raw_data_item_id"] == test_raw_data_item.id
        assert file_ann["created_by"] == test_user.id

        # Sample-linked annotation
        sample_ann = next(d for d in data if d["sample_id"] is not None)
        assert sample_ann["key"] == "sample_map"
        assert sample_ann["sample_id"] == test_sample.id
        assert sample_ann["index"] == {"position": 1}
        assert sample_ann["value_json"] == {"condition": "treated"}

        # Verify rows exist in DB
        rows = db.query(FileAnnotation).filter(
            FileAnnotation.raw_data_item_id == test_raw_data_item.id
        ).all()
        assert len(rows) == 2

    # ── 2. Sample from wrong project is rejected ──────────────────────────────

    def test_create_annotations_invalid_sample_mismatch(
        self,
        client,
        db,
        test_user,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_raw_data_item,
        other_project_sample,
    ):
        """Batch with a sample_id from a different project must return 400."""
        headers = self._login(client)

        resp = self._post_batch(
            client,
            headers,
            test_raw_data_item.id,
            [
                {
                    "key": "bad_sample",
                    "sample_id": other_project_sample.id,
                    "value_text": "this sample belongs elsewhere",
                }
            ],
        )

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        # detail is a list of per-item error dicts
        assert isinstance(detail, list)
        assert any("does not belong to the same project" in e["error"] for e in detail)

        # No rows created
        count = db.query(FileAnnotation).filter(
            FileAnnotation.raw_data_item_id == test_raw_data_item.id
        ).count()
        assert count == 0

    # ── 3. Validation errors: missing key / missing both values ───────────────

    def test_create_annotations_validation_error(
        self,
        client,
        db,
        test_user,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_raw_data_item,
    ):
        """Missing key and missing both value fields produce 422; no rows created."""
        headers = self._login(client)

        # Missing both value_json and value_text
        resp = self._post_batch(
            client,
            headers,
            test_raw_data_item.id,
            [{"key": "obs"}],  # no value_json, no value_text
        )
        assert resp.status_code == 422  # Pydantic validation

        # Missing key entirely (fails key validator)
        resp2 = self._post_batch(
            client,
            headers,
            test_raw_data_item.id,
            [{"value_text": "some text"}],  # no key field → pydantic error
        )
        assert resp2.status_code == 422

        # No rows were created by either attempt
        count = db.query(FileAnnotation).filter(
            FileAnnotation.raw_data_item_id == test_raw_data_item.id
        ).count()
        assert count == 0

    # ── 4. List with filters ─────────────────────────────────────────────────

    def test_list_annotations_filters(
        self,
        client,
        db,
        test_user,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_sample,
        test_sample2,
        test_raw_data_item,
    ):
        """Filters by key and sample_id return the expected subsets."""
        headers = self._login(client)

        # Create three annotations
        self._post_batch(
            client,
            headers,
            test_raw_data_item.id,
            [
                {"key": "alpha", "value_text": "file-level"},
                {"key": "alpha", "sample_id": test_sample.id, "value_text": "sample1"},
                {"key": "beta", "sample_id": test_sample2.id, "value_text": "sample2"},
            ],
        )

        base_url = f"/api/raw-data/{test_raw_data_item.id}/annotations"

        # No filter → all three
        resp_all = client.get(base_url, headers=headers)
        assert resp_all.status_code == 200
        assert len(resp_all.json()) == 3

        # Filter by key=alpha → two
        resp_key = client.get(f"{base_url}?key=alpha", headers=headers)
        assert resp_key.status_code == 200
        assert len(resp_key.json()) == 2
        assert all(a["key"] == "alpha" for a in resp_key.json())

        # Filter by sample_id=test_sample.id → one
        resp_sid = client.get(
            f"{base_url}?sample_id={test_sample.id}", headers=headers
        )
        assert resp_sid.status_code == 200
        assert len(resp_sid.json()) == 1
        assert resp_sid.json()[0]["sample_id"] == test_sample.id

        # Filter by key=alpha AND sample_id → one
        resp_both = client.get(
            f"{base_url}?key=alpha&sample_id={test_sample.id}", headers=headers
        )
        assert resp_both.status_code == 200
        assert len(resp_both.json()) == 1

    # ── 5. PATCH annotation ───────────────────────────────────────────────────

    def test_patch_annotation(
        self,
        client,
        db,
        test_user,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_sample,
        test_raw_data_item,
    ):
        """PATCH updates only the supplied fields; others are unchanged."""
        headers = self._login(client)

        # Create one annotation
        create_resp = self._post_batch(
            client,
            headers,
            test_raw_data_item.id,
            [
                {
                    "key": "obs",
                    "value_json": {"score": 1},
                    "value_text": "original",
                }
            ],
        )
        assert create_resp.status_code == 201
        ann_id = create_resp.json()[0]["id"]

        # Patch only value_json
        patch_resp = client.patch(
            f"/api/annotations/{ann_id}",
            headers=headers,
            json={"value_json": {"score": 99}},
        )
        assert patch_resp.status_code == 200
        patched = patch_resp.json()
        assert patched["value_json"] == {"score": 99}
        assert patched["value_text"] == "original"   # unchanged
        assert patched["sample_id"] is None          # unchanged

        # Patch sample_id
        patch_resp2 = client.patch(
            f"/api/annotations/{ann_id}",
            headers=headers,
            json={"sample_id": test_sample.id},
        )
        assert patch_resp2.status_code == 200
        assert patch_resp2.json()["sample_id"] == test_sample.id

        # Unset sample_id by sending null
        patch_resp3 = client.patch(
            f"/api/annotations/{ann_id}",
            headers=headers,
            json={"sample_id": None},
        )
        assert patch_resp3.status_code == 200
        assert patch_resp3.json()["sample_id"] is None

    # ── 6. DELETE annotation ──────────────────────────────────────────────────

    def test_delete_annotation(
        self,
        client,
        db,
        test_user,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_raw_data_item,
    ):
        """DELETE removes the annotation row and returns 204."""
        headers = self._login(client)

        create_resp = self._post_batch(
            client,
            headers,
            test_raw_data_item.id,
            [{"key": "to_delete", "value_text": "gone soon"}],
        )
        assert create_resp.status_code == 201
        ann_id = create_resp.json()[0]["id"]

        # Delete
        del_resp = client.delete(f"/api/annotations/{ann_id}", headers=headers)
        assert del_resp.status_code == 204
        assert del_resp.content == b""

        # Row is gone
        row = db.query(FileAnnotation).filter(FileAnnotation.id == ann_id).first()
        assert row is None

        # Second delete returns 404
        del_resp2 = client.delete(f"/api/annotations/{ann_id}", headers=headers)
        assert del_resp2.status_code == 404

    # ── 7. Authorization ──────────────────────────────────────────────────────

    def test_authorization(
        self,
        client,
        db,
        test_user,
        test_user2,
        test_project,
        test_membership,
        test_storage_root,
        test_rdmp,
        test_raw_data_item,
    ):
        """test_user2 (no Lab membership) receives 403 on all write operations."""
        # Ensure test_user2 exists but has no supervisor/project membership
        headers2 = self._login(client, username="testuser2")

        # CREATE → 403
        resp_create = self._post_batch(
            client,
            headers2,
            test_raw_data_item.id,
            [{"key": "obs", "value_text": "unauthorised"}],
        )
        assert resp_create.status_code == 403

        # LIST → 403 (supervisor membership required)
        resp_list = client.get(
            f"/api/raw-data/{test_raw_data_item.id}/annotations",
            headers=headers2,
        )
        assert resp_list.status_code == 403

        # Create a row as test_user so PATCH/DELETE have a target
        headers1 = self._login(client)
        create_resp = self._post_batch(
            client,
            headers1,
            test_raw_data_item.id,
            [{"key": "obs", "value_text": "owner only"}],
        )
        assert create_resp.status_code == 201
        ann_id = create_resp.json()[0]["id"]

        # PATCH → 403
        resp_patch = client.patch(
            f"/api/annotations/{ann_id}",
            headers=headers2,
            json={"value_text": "stolen"},
        )
        assert resp_patch.status_code == 403

        # DELETE → 403
        resp_delete = client.delete(f"/api/annotations/{ann_id}", headers=headers2)
        assert resp_delete.status_code == 403
