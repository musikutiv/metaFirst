"""Shared fixtures for discovery tests."""

import os
import tempfile
import pytest

# Create a shared discovery database for tests
_shared_discovery_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_shared_api_key = "test-discovery-api-key"

# Set environment variables before any other imports
os.environ["DISCOVERY_DB_PATH"] = _shared_discovery_db.name
os.environ["DISCOVERY_API_KEY"] = _shared_api_key


@pytest.fixture(scope="session")
def discovery_api_key():
    """Return the shared API key for discovery push operations."""
    return _shared_api_key


@pytest.fixture(scope="session", autouse=True)
def cleanup_discovery_db():
    """Clean up the shared discovery database after all tests."""
    yield
    try:
        os.unlink(_shared_discovery_db.name)
    except OSError:
        pass
