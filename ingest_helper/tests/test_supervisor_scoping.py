"""Unit tests for supervisor scoping in the ingestor."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from metafirst_ingest import (
    SupervisorClient,
    SupervisorMismatchError,
    resolve_supervisor_id,
    validate_project_supervisor,
)


class TestResolveSupervisorId:
    """Tests for resolve_supervisor_id function."""

    def test_explicit_supervisor_id_in_config(self):
        """Test that explicit supervisor_id is used without API call."""
        mock_client = MagicMock(spec=SupervisorClient)

        config = {"supervisor_id": 42}
        supervisor_id, error = resolve_supervisor_id(config, mock_client)

        assert error is None
        assert supervisor_id == 42
        mock_client.get_supervisors.assert_not_called()

    def test_auto_detect_single_supervisor(self):
        """Test auto-detection when exactly one supervisor exists."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_supervisors.return_value = [
            {"id": 7, "name": "Only Supervisor"}
        ]

        config = {}  # No supervisor_id specified
        supervisor_id, error = resolve_supervisor_id(config, mock_client)

        assert error is None
        assert supervisor_id == 7
        mock_client.get_supervisors.assert_called_once()

    def test_auto_detect_no_supervisors(self):
        """Test that missing supervisors returns error."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_supervisors.return_value = []

        config = {}
        supervisor_id, error = resolve_supervisor_id(config, mock_client)

        assert supervisor_id == 0
        assert error is not None
        assert "No supervisors found" in error

    def test_auto_detect_multiple_supervisors_fails(self):
        """Test that multiple supervisors requires explicit config."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_supervisors.return_value = [
            {"id": 1, "name": "Supervisor A"},
            {"id": 2, "name": "Supervisor B"},
        ]

        config = {}
        supervisor_id, error = resolve_supervisor_id(config, mock_client)

        assert supervisor_id == 0
        assert error is not None
        assert "Multiple supervisors found" in error
        assert "supervisor_id" in error
        assert "Supervisor A" in error
        assert "Supervisor B" in error

    def test_api_error_during_auto_detect(self):
        """Test that API error returns error message."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_supervisors.side_effect = Exception("Connection refused")

        config = {}
        supervisor_id, error = resolve_supervisor_id(config, mock_client)

        assert supervisor_id == 0
        assert error is not None
        assert "Failed to fetch supervisors" in error

    def test_none_supervisor_id_triggers_auto_detect(self):
        """Test that supervisor_id: null triggers auto-detection."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_supervisors.return_value = [
            {"id": 5, "name": "Single Supervisor"}
        ]

        config = {"supervisor_id": None}
        supervisor_id, error = resolve_supervisor_id(config, mock_client)

        assert error is None
        assert supervisor_id == 5


class TestValidateProjectSupervisor:
    """Tests for validate_project_supervisor function."""

    def test_matching_supervisor_succeeds(self):
        """Test that matching supervisor_id passes validation."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_project.return_value = {
            "id": 10,
            "name": "Test Project",
            "supervisor_id": 1,
        }

        project = validate_project_supervisor(
            client=mock_client,
            project_id=10,
            expected_supervisor_id=1,
        )

        assert project["id"] == 10
        assert project["supervisor_id"] == 1

    def test_mismatched_supervisor_raises_error(self):
        """Test that mismatched supervisor_id raises SupervisorMismatchError."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_project.return_value = {
            "id": 10,
            "name": "Test Project",
            "supervisor_id": 2,  # Different from expected
        }

        with pytest.raises(SupervisorMismatchError) as exc_info:
            validate_project_supervisor(
                client=mock_client,
                project_id=10,
                expected_supervisor_id=1,
            )

        error = exc_info.value
        assert error.project_id == 10
        assert error.project_supervisor_id == 2
        assert error.configured_supervisor_id == 1
        assert "belongs to supervisor 2" in str(error)
        assert "configured for supervisor 1" in str(error)
        assert "Start a separate ingestor" in str(error)

    def test_uses_cache_when_available(self):
        """Test that cached project data is used to avoid API calls."""
        mock_client = MagicMock(spec=SupervisorClient)
        project_cache = {
            10: {"id": 10, "name": "Cached Project", "supervisor_id": 1}
        }

        project = validate_project_supervisor(
            client=mock_client,
            project_id=10,
            expected_supervisor_id=1,
            project_cache=project_cache,
        )

        assert project["id"] == 10
        mock_client.get_project.assert_not_called()

    def test_populates_cache_after_api_call(self):
        """Test that project cache is populated after API call."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_project.return_value = {
            "id": 10,
            "name": "Test Project",
            "supervisor_id": 1,
        }
        project_cache = {}

        validate_project_supervisor(
            client=mock_client,
            project_id=10,
            expected_supervisor_id=1,
            project_cache=project_cache,
        )

        assert 10 in project_cache
        assert project_cache[10]["supervisor_id"] == 1

    def test_missing_supervisor_id_in_project_raises(self):
        """Test that project without supervisor_id raises exception."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_project.return_value = {
            "id": 10,
            "name": "Legacy Project",
            # No supervisor_id field
        }

        with pytest.raises(Exception) as exc_info:
            validate_project_supervisor(
                client=mock_client,
                project_id=10,
                expected_supervisor_id=1,
            )

        assert "no supervisor_id" in str(exc_info.value).lower()


class TestSupervisorMismatchError:
    """Tests for SupervisorMismatchError exception."""

    def test_error_message_format(self):
        """Test that error message contains all required info."""
        error = SupervisorMismatchError(
            project_id=5,
            project_supervisor_id=2,
            configured_supervisor_id=1,
        )

        message = str(error)
        assert "Project 5" in message
        assert "supervisor 2" in message
        assert "supervisor 1" in message
        assert "Start a separate ingestor" in message

    def test_error_attributes(self):
        """Test that error has correct attributes."""
        error = SupervisorMismatchError(
            project_id=5,
            project_supervisor_id=2,
            configured_supervisor_id=1,
        )

        assert error.project_id == 5
        assert error.project_supervisor_id == 2
        assert error.configured_supervisor_id == 1
