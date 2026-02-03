"""Unit tests for lab scoping in the ingestor.

Note: Tests use both old (supervisor_*) and new (lab_*) terminology
to verify backward compatibility.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))
from metafirst_ingest import (
    SupervisorClient,
    # Import both old and new names to test aliases
    SupervisorMismatchError,
    LabMismatchError,
    resolve_supervisor_id,
    resolve_lab_id,
    validate_project_supervisor,
    validate_project_lab,
)


class TestResolveLabId:
    """Tests for resolve_lab_id function (and its alias resolve_supervisor_id)."""

    def test_explicit_lab_id_in_config(self):
        """Test that explicit lab_id is used without API call (preferred)."""
        mock_client = MagicMock(spec=SupervisorClient)

        config = {"lab_id": 42}
        lab_id, error = resolve_lab_id(config, mock_client)

        assert error is None
        assert lab_id == 42
        mock_client.get_supervisors.assert_not_called()

    def test_explicit_supervisor_id_in_config_with_deprecation(self, caplog):
        """Test that supervisor_id still works but emits deprecation warning."""
        mock_client = MagicMock(spec=SupervisorClient)

        config = {"supervisor_id": 42}
        with caplog.at_level(logging.WARNING):
            lab_id, error = resolve_lab_id(config, mock_client)

        assert error is None
        assert lab_id == 42
        mock_client.get_supervisors.assert_not_called()
        # Check deprecation warning was emitted
        assert "deprecated" in caplog.text.lower()
        assert "supervisor_id" in caplog.text
        assert "lab_id" in caplog.text

    def test_lab_id_takes_precedence_over_supervisor_id(self):
        """Test that lab_id takes precedence when both are specified."""
        mock_client = MagicMock(spec=SupervisorClient)

        config = {"lab_id": 100, "supervisor_id": 42}
        lab_id, error = resolve_lab_id(config, mock_client)

        assert error is None
        assert lab_id == 100  # lab_id takes precedence

    def test_auto_detect_single_lab(self):
        """Test auto-detection when exactly one lab exists."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_supervisors.return_value = [
            {"id": 7, "name": "Only Lab"}
        ]

        config = {}  # No lab_id specified
        lab_id, error = resolve_lab_id(config, mock_client)

        assert error is None
        assert lab_id == 7
        mock_client.get_supervisors.assert_called_once()

    def test_auto_detect_no_labs(self):
        """Test that missing labs returns error."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_supervisors.return_value = []

        config = {}
        lab_id, error = resolve_lab_id(config, mock_client)

        assert lab_id == 0
        assert error is not None
        assert "No labs found" in error

    def test_auto_detect_multiple_labs_fails(self):
        """Test that multiple labs requires explicit config."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_supervisors.return_value = [
            {"id": 1, "name": "Lab A"},
            {"id": 2, "name": "Lab B"},
        ]

        config = {}
        lab_id, error = resolve_lab_id(config, mock_client)

        assert lab_id == 0
        assert error is not None
        assert "Multiple labs found" in error
        assert "lab_id" in error
        assert "Lab A" in error
        assert "Lab B" in error

    def test_api_error_during_auto_detect(self):
        """Test that API error returns error message."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_supervisors.side_effect = Exception("Connection refused")

        config = {}
        lab_id, error = resolve_lab_id(config, mock_client)

        assert lab_id == 0
        assert error is not None
        assert "Failed to fetch labs" in error

    def test_none_lab_id_triggers_auto_detect(self):
        """Test that lab_id: null triggers auto-detection."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_supervisors.return_value = [
            {"id": 5, "name": "Single Lab"}
        ]

        config = {"lab_id": None}
        lab_id, error = resolve_lab_id(config, mock_client)

        assert error is None
        assert lab_id == 5

    def test_backward_compat_alias(self):
        """Test that resolve_supervisor_id is an alias for resolve_lab_id."""
        assert resolve_supervisor_id is resolve_lab_id


class TestValidateProjectLab:
    """Tests for validate_project_lab function (and its alias validate_project_supervisor)."""

    def test_matching_lab_succeeds(self):
        """Test that matching lab_id passes validation."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_project.return_value = {
            "id": 10,
            "name": "Test Project",
            "supervisor_id": 1,  # API returns supervisor_id
        }

        project = validate_project_lab(
            client=mock_client,
            project_id=10,
            expected_lab_id=1,
        )

        assert project["id"] == 10
        assert project["supervisor_id"] == 1

    def test_mismatched_lab_raises_error(self):
        """Test that mismatched lab_id raises LabMismatchError."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_project.return_value = {
            "id": 10,
            "name": "Test Project",
            "supervisor_id": 2,  # Different from expected
        }

        with pytest.raises(LabMismatchError) as exc_info:
            validate_project_lab(
                client=mock_client,
                project_id=10,
                expected_lab_id=1,
            )

        error = exc_info.value
        assert error.project_id == 10
        assert error.project_lab_id == 2
        assert error.configured_lab_id == 1
        # New terminology in error message
        assert "belongs to lab 2" in str(error)
        assert "configured for lab 1" in str(error)
        assert "Start a separate ingestor" in str(error)

    def test_backward_compat_attributes(self):
        """Test that LabMismatchError has backward-compatible attributes."""
        error = LabMismatchError(
            project_id=10,
            project_lab_id=2,
            configured_lab_id=1,
        )
        # Old attribute names still work
        assert error.project_supervisor_id == 2
        assert error.configured_supervisor_id == 1

    def test_uses_cache_when_available(self):
        """Test that cached project data is used to avoid API calls."""
        mock_client = MagicMock(spec=SupervisorClient)
        project_cache = {
            10: {"id": 10, "name": "Cached Project", "supervisor_id": 1}
        }

        project = validate_project_lab(
            client=mock_client,
            project_id=10,
            expected_lab_id=1,
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

        validate_project_lab(
            client=mock_client,
            project_id=10,
            expected_lab_id=1,
            project_cache=project_cache,
        )

        assert 10 in project_cache
        assert project_cache[10]["supervisor_id"] == 1

    def test_missing_lab_id_in_project_raises(self):
        """Test that project without lab_id raises exception."""
        mock_client = MagicMock(spec=SupervisorClient)
        mock_client.get_project.return_value = {
            "id": 10,
            "name": "Legacy Project",
            # No supervisor_id field
        }

        with pytest.raises(Exception) as exc_info:
            validate_project_lab(
                client=mock_client,
                project_id=10,
                expected_lab_id=1,
            )

        assert "no lab_id" in str(exc_info.value).lower()

    def test_backward_compat_alias(self):
        """Test that validate_project_supervisor is an alias for validate_project_lab."""
        assert validate_project_supervisor is validate_project_lab


class TestLabMismatchError:
    """Tests for LabMismatchError exception (and its alias SupervisorMismatchError)."""

    def test_error_message_format(self):
        """Test that error message uses lab terminology."""
        error = LabMismatchError(
            project_id=5,
            project_lab_id=2,
            configured_lab_id=1,
        )

        message = str(error)
        assert "Project 5" in message
        assert "lab 2" in message
        assert "lab 1" in message
        assert "Start a separate ingestor" in message

    def test_error_attributes(self):
        """Test that error has correct attributes."""
        error = LabMismatchError(
            project_id=5,
            project_lab_id=2,
            configured_lab_id=1,
        )

        assert error.project_id == 5
        assert error.project_lab_id == 2
        assert error.configured_lab_id == 1

    def test_backward_compat_alias(self):
        """Test that SupervisorMismatchError is an alias for LabMismatchError."""
        assert SupervisorMismatchError is LabMismatchError

    def test_backward_compat_constructor(self):
        """Test that old constructor parameter names still work via alias."""
        # This tests that code using old parameter names still works
        error = SupervisorMismatchError(
            project_id=5,
            project_supervisor_id=2,
            configured_supervisor_id=1,
        )
        # Should work but attributes are renamed
        assert error.project_id == 5
        assert error.project_supervisor_id == 2
        assert error.configured_supervisor_id == 1
