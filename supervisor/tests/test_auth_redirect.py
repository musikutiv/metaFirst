"""Regression tests for auth flow without 307 redirects.

This test ensures that the UI can successfully authenticate and load
/api/projects without receiving 307 redirects that would drop the
Authorization header.
"""

import pytest
from fastapi.testclient import TestClient


class TestAuthNoRedirect:
    """Tests to verify auth works without 307 redirects."""

    def test_login_and_get_projects_no_redirect(
        self, client, db, test_user, test_project, test_membership, test_rdmp
    ):
        """Regression test: login then GET /api/projects/ must not 307/401.

        This simulates the UI flow:
        1. POST /api/auth/login -> get token
        2. GET /api/projects/ (with trailing slash) -> must return 200

        Note: Backend defines route as "/" with prefix "/api/projects", so
        canonical path is /api/projects/. UI client must use trailing slash.
        """
        # Step 1: Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        assert login_response.status_code == 200, "Login should succeed"
        token = login_response.json()["access_token"]

        # Step 2: GET /api/projects/ WITH trailing slash (canonical path)
        projects_response = client.get(
            "/api/projects/",  # With trailing slash - matches backend route
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,  # Don't follow redirects - we want to catch 307
        )

        # Must be 200, not 307 or 401
        assert projects_response.status_code == 200, (
            f"Expected 200, got {projects_response.status_code}. "
            "If 307, redirect_slashes issue. "
            "If 401, Authorization header was lost."
        )

        # Verify we got valid project data
        data = projects_response.json()
        assert isinstance(data, list), "Response should be a list of projects"

    def test_get_projects_with_trailing_slash_also_works(
        self, client, db, test_user, test_project, test_membership, test_rdmp
    ):
        """Verify that /api/projects/ (with trailing slash) also works."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # GET /api/projects/ WITH trailing slash
        projects_response = client.get(
            "/api/projects/",  # With trailing slash
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )

        assert projects_response.status_code == 200, (
            f"Expected 200, got {projects_response.status_code}"
        )

    def test_auth_me_no_redirect(self, client, db, test_user):
        """Verify /api/auth/me works without redirect."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # GET /api/auth/me
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )

        assert me_response.status_code == 200
        assert me_response.json()["username"] == "testuser"

    def test_samples_endpoint_no_redirect(
        self, client, db, test_user, test_project, test_membership, test_rdmp
    ):
        """Verify /api/projects/{id}/samples works without redirect."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # GET samples
        samples_response = client.get(
            f"/api/projects/{test_project.id}/samples",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )

        assert samples_response.status_code == 200
        data = samples_response.json()
        assert "items" in data  # Paginated response
        assert isinstance(data["items"], list)

    def test_rdmp_endpoint_no_redirect(
        self, client, db, test_user, test_project, test_membership, test_rdmp
    ):
        """Verify /api/rdmp/projects/{id}/rdmp works without redirect."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # GET RDMP
        rdmp_response = client.get(
            f"/api/rdmp/projects/{test_project.id}/rdmp",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )

        assert rdmp_response.status_code == 200
        assert "rdmp_json" in rdmp_response.json()
