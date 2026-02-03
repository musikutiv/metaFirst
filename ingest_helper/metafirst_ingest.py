#!/usr/bin/env python3
"""
metaFirst Ingest Helper

A watchdog-based tool that watches folders on user machines and creates
pending ingests in the supervisor for browser-based metadata entry.
"""

import os
import sys
import time
import re
import hashlib
import platform
import subprocess
import webbrowser
import logging
from pathlib import Path
from typing import Any

import yaml
import httpx
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)

# Deprecation warnings for v0.4 terminology migration
def _emit_deprecation_warning(old_key: str, new_key: str) -> None:
    """Emit deprecation warning when legacy config key is used."""
    logging.warning(
        f"Config key '{old_key}' is deprecated. Use '{new_key}' instead. "
        f"'{old_key}' will continue to work for backward compatibility."
    )
logger = logging.getLogger(__name__)


class SupervisorClient:
    """Client for interacting with the metaFirst Supervisor API."""

    # Endpoints that require trailing slash (router root paths)
    # These are mounted with prefix and have @router.get("/") or @router.post("/")
    _TRAILING_SLASH_ENDPOINTS = frozenset([
        "/api/projects",
        "/api/rdmp/templates",
    ])

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: str | None = None
        self._client = httpx.Client(timeout=30.0)

    def _normalize_endpoint(self, endpoint: str) -> str:
        """Normalize endpoint path to match supervisor's canonical routes.

        The supervisor has redirect_slashes=False, so we must use exact paths.
        Router root endpoints (e.g., /api/projects) need trailing slashes.
        """
        # Strip any existing trailing slash for comparison
        normalized = endpoint.rstrip("/")

        # Add trailing slash for known router root endpoints
        if normalized in self._TRAILING_SLASH_ENDPOINTS:
            return normalized + "/"

        return endpoint

    def _get_token(self) -> str:
        """Get or refresh JWT token."""
        if self._token:
            return self._token

        response = self._client.post(
            f"{self.base_url}/api/auth/login",
            data={"username": self.username, "password": self.password},
        )
        if response.status_code != 200:
            raise Exception(f"Login failed: {response.text}")

        self._token = response.json()["access_token"]
        return self._token

    def _request(
        self,
        method: str,
        endpoint: str,
        json: dict | None = None,
        params: dict | None = None,
        retries: int = 0,
        retry_delay: float = 1.0,
    ) -> dict[str, Any]:
        """Make an authenticated request to the API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            json: JSON body (optional)
            params: Query parameters (optional)
            retries: Number of retries for 5xx errors (default 0)
            retry_delay: Initial delay between retries in seconds (exponential backoff)
        """
        # Normalize endpoint to match supervisor's canonical routes
        endpoint = self._normalize_endpoint(endpoint)

        headers = {"Authorization": f"Bearer {self._get_token()}"}

        attempt = 0
        max_attempts = retries + 1

        while attempt < max_attempts:
            response = self._client.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=json,
                params=params,
            )

            # Handle token expiration
            if response.status_code == 401:
                self._token = None
                headers = {"Authorization": f"Bearer {self._get_token()}"}
                response = self._client.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    json=json,
                    params=params,
                )

            # Retry on 5xx errors
            if response.status_code >= 500 and attempt < max_attempts - 1:
                delay = retry_delay * (2 ** attempt)
                logger.warning(
                    f"Server error {response.status_code} on {endpoint}, "
                    f"retrying in {delay:.1f}s (attempt {attempt + 1}/{max_attempts})"
                )
                time.sleep(delay)
                attempt += 1
                continue

            break

        if response.status_code >= 400:
            raise Exception(f"API error {response.status_code}: {response.text}")

        return response.json()

    def get_samples(self, project_id: int) -> list[dict]:
        """Get samples for a project."""
        return self._request("GET", f"/api/projects/{project_id}/samples")

    def create_sample(self, project_id: int, sample_identifier: str) -> dict:
        """Create a new sample."""
        return self._request(
            "POST",
            f"/api/projects/{project_id}/samples",
            json={"sample_identifier": sample_identifier},
        )

    def find_or_create_sample(self, project_id: int, sample_identifier: str) -> dict:
        """Find existing sample or create a new one."""
        samples = self.get_samples(project_id)
        for sample in samples:
            if sample["sample_identifier"] == sample_identifier:
                return sample
        return self.create_sample(project_id, sample_identifier)

    def set_sample_field(
        self, sample_id: int, field_key: str, value: Any
    ) -> dict:
        """Set a field value for a sample."""
        return self._request(
            "PUT",
            f"/api/samples/{sample_id}/fields/{field_key}",
            json={"value": value},
        )

    def get_rdmp(self, project_id: int) -> dict | None:
        """Get the current RDMP for a project."""
        try:
            return self._request("GET", f"/api/rdmp/projects/{project_id}/rdmp")
        except Exception:
            return None

    def create_raw_data_item(
        self,
        project_id: int,
        storage_root_id: int,
        relative_path: str,
        sample_id: int | None = None,
        file_size_bytes: int | None = None,
        file_hash_sha256: str | None = None,
    ) -> dict:
        """Register a new raw data item."""
        data = {
            "storage_root_id": storage_root_id,
            "relative_path": relative_path,
        }
        if sample_id:
            data["sample_id"] = sample_id
        if file_size_bytes:
            data["file_size_bytes"] = file_size_bytes
        if file_hash_sha256:
            data["file_hash_sha256"] = file_hash_sha256

        return self._request("POST", f"/api/projects/{project_id}/raw-data", json=data)

    def create_pending_ingest(
        self,
        project_id: int,
        storage_root_id: int,
        relative_path: str,
        inferred_sample_identifier: str | None = None,
        file_size_bytes: int | None = None,
        file_hash_sha256: str | None = None,
    ) -> dict:
        """Create a pending ingest for browser-based metadata entry."""
        data = {
            "storage_root_id": storage_root_id,
            "relative_path": relative_path,
        }
        if inferred_sample_identifier:
            data["inferred_sample_identifier"] = inferred_sample_identifier
        if file_size_bytes:
            data["file_size_bytes"] = file_size_bytes
        if file_hash_sha256:
            data["file_hash_sha256"] = file_hash_sha256

        return self._request("POST", f"/api/projects/{project_id}/pending-ingests", json=data)

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def get_projects(self) -> list[dict]:
        """Get list of projects the user has access to.

        Returns:
            List of project dicts with at least 'id' and 'name' fields.

        Raises:
            Exception: On API error (401, 5xx after retries, etc.)
        """
        return self._request("GET", "/api/projects", retries=3, retry_delay=1.0)

    def get_storage_roots(self, project_id: int) -> list[dict]:
        """Get storage roots for a project.

        Args:
            project_id: The project ID to get storage roots for.

        Returns:
            List of storage root dicts with at least 'id' and 'name' fields.

        Raises:
            Exception: On API error (401, 5xx after retries, etc.)
        """
        return self._request(
            "GET", f"/api/projects/{project_id}/storage-roots", retries=3, retry_delay=1.0
        )

    def get_supervisors(self) -> list[dict]:
        """Get list of supervisors.

        Returns:
            List of supervisor dicts with at least 'id' and 'name' fields.

        Raises:
            Exception: On API error (401, 5xx after retries, etc.)
        """
        return self._request("GET", "/api/supervisors/", retries=3, retry_delay=1.0)

    def get_project(self, project_id: int) -> dict:
        """Get a single project by ID.

        Returns:
            Project dict with 'id', 'name', 'supervisor_id', etc.

        Raises:
            Exception: On API error (401, 404, etc.)
        """
        return self._request("GET", f"/api/projects/{project_id}")


class LabMismatchError(Exception):
    """Raised when a project belongs to a different lab than configured."""

    def __init__(
        self,
        project_id: int,
        project_lab_id: int | None = None,
        configured_lab_id: int | None = None,
        # Backward-compatible parameter names
        project_supervisor_id: int | None = None,
        configured_supervisor_id: int | None = None,
    ):
        self.project_id = project_id
        # Accept either new or old parameter names
        self.project_lab_id = project_lab_id if project_lab_id is not None else project_supervisor_id
        self.configured_lab_id = configured_lab_id if configured_lab_id is not None else configured_supervisor_id
        # Keep backward-compatible attributes
        self.project_supervisor_id = self.project_lab_id
        self.configured_supervisor_id = self.configured_lab_id
        super().__init__(
            f"Project {project_id} belongs to lab {self.project_lab_id} "
            f"but this ingestor is configured for lab {self.configured_lab_id}. "
            f"Start a separate ingestor instance for lab {self.project_lab_id}."
        )


# Backward compatibility alias
SupervisorMismatchError = LabMismatchError


def resolve_lab_id(
    config: dict,
    client: SupervisorClient,
) -> tuple[int, str | None]:
    """Resolve the lab_id from config or auto-detect.

    Resolution rules:
    1. If lab_id is explicitly provided in config, use it (preferred).
    2. If supervisor_id is provided (deprecated), use it with warning.
    3. If not provided, fetch labs from API:
       - If exactly 1 lab exists, auto-bind to it.
       - If 0 or >1 labs, fail with clear error.

    Args:
        config: Config dict from YAML
        client: SupervisorClient for API calls

    Returns:
        Tuple of (lab_id, None) on success, or
        (0, error_message) on failure.
    """
    # Check for explicit lab_id (preferred)
    if "lab_id" in config and config["lab_id"] is not None:
        return int(config["lab_id"]), None

    # Check for deprecated supervisor_id
    if "supervisor_id" in config and config["supervisor_id"] is not None:
        _emit_deprecation_warning("supervisor_id", "lab_id")
        return int(config["supervisor_id"]), None

    # Auto-detect: fetch labs
    try:
        labs = client.get_supervisors()
    except Exception as e:
        return 0, f"Failed to fetch labs for auto-detection: {e}"

    if len(labs) == 0:
        return 0, "No labs found. Create a lab first."

    if len(labs) == 1:
        lab = labs[0]
        logger.info(
            f"Auto-detected single lab: {lab['name']} (id={lab['id']})"
        )
        return lab["id"], None

    # Multiple labs - require explicit config
    lab_names = [f"  - {s['name']} (id={s['id']})" for s in labs]
    return 0, (
        f"Multiple labs found. Add 'lab_id' to config:\n"
        + "\n".join(lab_names)
    )


# Backward compatibility alias
resolve_supervisor_id = resolve_lab_id


class WatcherConfig:
    """Configuration for a single watched folder."""

    def __init__(
        self,
        watch_path: str,
        project_id: int,
        storage_root_id: int,
        base_path_for_relative: str | None = None,
        sample_identifier_pattern: str | None = None,
    ):
        self.watch_path = Path(watch_path).resolve()
        self.project_id = project_id
        self.storage_root_id = storage_root_id
        self.base_path_for_relative = (
            Path(base_path_for_relative).resolve()
            if base_path_for_relative
            else self.watch_path
        )
        self.sample_identifier_pattern = sample_identifier_pattern

    def compute_relative_path(self, file_path: Path) -> str:
        """Compute the relative path from base_path_for_relative."""
        return str(file_path.relative_to(self.base_path_for_relative))

    def extract_sample_identifier(self, file_path: Path) -> str | None:
        """Extract sample identifier from filename using pattern, or return None."""
        if not self.sample_identifier_pattern:
            return None

        filename = file_path.name
        match = re.match(self.sample_identifier_pattern, filename)
        if match:
            # Return first capturing group if exists, otherwise full match
            groups = match.groups()
            return groups[0] if groups else match.group(0)
        return None


def validate_project_lab(
    client: SupervisorClient,
    project_id: int,
    expected_lab_id: int,
    project_cache: dict[int, dict] | None = None,
) -> dict:
    """Validate that a project belongs to the expected lab.

    Args:
        client: SupervisorClient for API calls
        project_id: Project ID to validate
        expected_lab_id: The lab_id this ingestor is configured for
        project_cache: Optional cache of projects by ID to avoid repeated API calls

    Returns:
        The project dict on success.

    Raises:
        LabMismatchError: If project belongs to different lab.
        Exception: On API error (project not found, etc.)
    """
    # Check cache first
    if project_cache is not None and project_id in project_cache:
        project = project_cache[project_id]
    else:
        project = client.get_project(project_id)
        if project_cache is not None:
            project_cache[project_id] = project

    # API returns supervisor_id (internal field name)
    project_lab_id = project.get("supervisor_id")
    if project_lab_id is None:
        raise Exception(f"Project {project_id} has no lab_id (data integrity issue)")

    if project_lab_id != expected_lab_id:
        raise LabMismatchError(
            project_id=project_id,
            project_lab_id=project_lab_id,
            configured_lab_id=expected_lab_id,
        )

    return project


# Backward compatibility alias
validate_project_supervisor = validate_project_lab


def compute_file_hash(file_path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


class IngestEventHandler(FileSystemEventHandler):
    """Handler for file creation events - creates pending ingests for browser-based entry."""

    def __init__(
        self,
        client: SupervisorClient,
        watcher_config: WatcherConfig,
        supervisor_id: int,
        compute_hash: bool = False,
        open_browser: bool = False,
        ui_base_url: str | None = None,
    ):
        super().__init__()
        self.client = client
        self.config = watcher_config
        self.supervisor_id = supervisor_id
        self.compute_hash = compute_hash
        self.open_browser = open_browser
        self.ui_base_url = ui_base_url or "http://localhost:5173"
        self.processed_files: set[str] = set()
        # Cache project lookups to avoid repeated API calls
        self._project_cache: dict[int, dict] = {}

    def on_created(self, event: FileCreatedEvent):
        """Handle file creation event."""
        if event.is_directory:
            return

        file_path = Path(event.src_path).resolve()

        # Skip if already processed
        if str(file_path) in self.processed_files:
            return

        # Wait a moment for file to be fully written
        time.sleep(0.5)

        # Skip if file doesn't exist anymore (e.g., temp files)
        if not file_path.exists():
            return

        self.processed_files.add(str(file_path))

        try:
            self._process_file(file_path)
        except Exception as e:
            print(f"[ERROR] Failed to process {file_path}: {e}")

    def _process_file(self, file_path: Path):
        """Process a newly created file - create pending ingest."""
        print(f"\n[NEW FILE] {file_path}")

        # Validate project belongs to this ingestor's lab
        try:
            validate_project_lab(
                client=self.client,
                project_id=self.config.project_id,
                expected_lab_id=self.supervisor_id,  # Internal param still named supervisor_id
                project_cache=self._project_cache,
            )
        except LabMismatchError as e:
            print(f"  [REJECT] {e}")
            return
        except Exception as e:
            print(f"  [ERROR] Failed to validate project lab: {e}")
            return

        # Compute relative path
        try:
            relative_path = self.config.compute_relative_path(file_path)
        except ValueError as e:
            print(f"  [SKIP] Cannot compute relative path: {e}")
            return

        print(f"  Relative path: {relative_path}")

        # Extract sample identifier from filename pattern (if configured)
        inferred_sample_identifier = self.config.extract_sample_identifier(file_path)
        if inferred_sample_identifier:
            print(f"  Inferred sample identifier: {inferred_sample_identifier}")

        # Get file metadata
        file_size = file_path.stat().st_size
        file_hash = compute_file_hash(file_path) if self.compute_hash else None

        # Create pending ingest (no terminal prompts)
        try:
            pending_ingest = self.client.create_pending_ingest(
                project_id=self.config.project_id,
                storage_root_id=self.config.storage_root_id,
                relative_path=relative_path,
                inferred_sample_identifier=inferred_sample_identifier,
                file_size_bytes=file_size,
                file_hash_sha256=file_hash,
            )
            ingest_id = pending_ingest["id"]
            print(f"  Created pending ingest: {ingest_id}")

            # Construct ingest URL (rstrip to avoid double slashes)
            ingest_url = f"{self.ui_base_url.rstrip('/')}/ingest/{ingest_id}"
            print(f"  Complete metadata entry in browser at: {ingest_url}")

            # Optionally open browser
            if self.open_browser:
                print(f"  Opening browser: {ingest_url}")
                self._open_browser(ingest_url)

        except Exception as e:
            print(f"  [ERROR] Failed to create pending ingest: {e}")

    def _open_browser(self, url: str):
        """Open URL in browser, using subprocess on macOS with webbrowser fallback."""
        if platform.system() == "Darwin":
            try:
                subprocess.run(["open", url], check=True)
                return
            except subprocess.CalledProcessError as e:
                print(f"  [WARN] subprocess open failed: {e}, falling back to webbrowser")
        webbrowser.open(url)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


class ResolvedWatcherConfig:
    """Result of resolving a watcher config with names to numeric IDs."""

    def __init__(
        self,
        watch_path: str,
        project_id: int,
        storage_root_id: int,
        project_name: str | None = None,
        storage_root_name: str | None = None,
        base_path_for_relative: str | None = None,
        sample_identifier_pattern: str | None = None,
        resolved_by_name: bool = False,
    ):
        self.watch_path = watch_path
        self.project_id = project_id
        self.storage_root_id = storage_root_id
        self.project_name = project_name
        self.storage_root_name = storage_root_name
        self.base_path_for_relative = base_path_for_relative
        self.sample_identifier_pattern = sample_identifier_pattern
        self.resolved_by_name = resolved_by_name


def resolve_watcher_config(
    watcher_cfg: dict,
    client: SupervisorClient,
    projects_cache: dict[str, dict] | None = None,
    storage_roots_cache: dict[int, list[dict]] | None = None,
) -> tuple[ResolvedWatcherConfig | None, str | None]:
    """Resolve a watcher config, converting project_name/storage_root_name to IDs.

    Args:
        watcher_cfg: Raw watcher config dict from YAML
        client: SupervisorClient for API calls
        projects_cache: Optional cache of projects by name (populated if None)
        storage_roots_cache: Optional cache of storage roots by project_id

    Returns:
        Tuple of (ResolvedWatcherConfig, None) on success, or
        (None, error_message) on failure.
    """
    watch_path = watcher_cfg.get("watch_path")
    if not watch_path:
        return None, "Missing 'watch_path'"

    resolved_by_name = False
    project_id: int | None = None
    project_name: str | None = None
    storage_root_id: int | None = None
    storage_root_name: str | None = None

    # --- Resolve project_id ---
    if "project_id" in watcher_cfg and watcher_cfg["project_id"] is not None:
        # Numeric ID takes precedence
        project_id = int(watcher_cfg["project_id"])
    elif "project_name" in watcher_cfg and watcher_cfg["project_name"]:
        # Resolve by name
        project_name = watcher_cfg["project_name"]

        # Get projects (use cache or fetch)
        try:
            if projects_cache is None:
                projects = client.get_projects()
                projects_cache = {p["name"]: p for p in projects}
            else:
                projects = list(projects_cache.values())
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg:
                return None, f"Authentication failed while resolving project_name '{project_name}'"
            return None, f"API error resolving project_name '{project_name}': {e}"

        # Find matching projects by name
        matches = [p for p in projects if p["name"] == project_name]

        if len(matches) == 0:
            return None, f"Project not found: '{project_name}'"
        elif len(matches) > 1:
            return None, f"Ambiguous project_name '{project_name}': found {len(matches)} matches"

        project_id = matches[0]["id"]
        resolved_by_name = True
        logger.debug(f"Resolved project_name '{project_name}' -> project_id={project_id}")
    else:
        return None, "Missing both 'project_id' and 'project_name'"

    # --- Resolve storage_root_id ---
    if "storage_root_id" in watcher_cfg and watcher_cfg["storage_root_id"] is not None:
        # Numeric ID takes precedence
        storage_root_id = int(watcher_cfg["storage_root_id"])
    elif "storage_root_name" in watcher_cfg and watcher_cfg["storage_root_name"]:
        # Resolve by name
        storage_root_name = watcher_cfg["storage_root_name"]

        # Get storage roots for the resolved project
        try:
            if storage_roots_cache is None:
                storage_roots_cache = {}
            if project_id not in storage_roots_cache:
                storage_roots_cache[project_id] = client.get_storage_roots(project_id)
            storage_roots = storage_roots_cache[project_id]
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg:
                return None, f"Authentication failed while resolving storage_root_name '{storage_root_name}'"
            return None, f"API error resolving storage_root_name '{storage_root_name}': {e}"

        # Find matching storage roots by name
        matches = [sr for sr in storage_roots if sr["name"] == storage_root_name]

        if len(matches) == 0:
            return None, f"Storage root not found: '{storage_root_name}' in project {project_id}"
        elif len(matches) > 1:
            return None, f"Ambiguous storage_root_name '{storage_root_name}': found {len(matches)} matches"

        storage_root_id = matches[0]["id"]
        resolved_by_name = True
        logger.debug(
            f"Resolved storage_root_name '{storage_root_name}' -> storage_root_id={storage_root_id}"
        )
    else:
        return None, "Missing both 'storage_root_id' and 'storage_root_name'"

    # Build resolved config
    return ResolvedWatcherConfig(
        watch_path=watch_path,
        project_id=project_id,
        storage_root_id=storage_root_id,
        project_name=project_name,
        storage_root_name=storage_root_name,
        base_path_for_relative=watcher_cfg.get("base_path_for_relative"),
        sample_identifier_pattern=watcher_cfg.get("sample_identifier_pattern"),
        resolved_by_name=resolved_by_name,
    ), None


def resolve_all_watchers(
    watchers_cfg: list[dict],
    client: SupervisorClient,
) -> tuple[list[ResolvedWatcherConfig], list[tuple[dict, str]]]:
    """Resolve all watcher configs, converting names to IDs where needed.

    Args:
        watchers_cfg: List of raw watcher config dicts from YAML
        client: SupervisorClient for API calls

    Returns:
        Tuple of:
        - List of successfully resolved watcher configs
        - List of (failed_config, error_message) tuples for skipped watchers
    """
    resolved = []
    failed = []

    # Cache for API responses to avoid repeated calls
    projects_cache: dict[str, dict] | None = None
    storage_roots_cache: dict[int, list[dict]] = {}

    # Pre-fetch projects if any watcher uses project_name
    if any("project_name" in w and w.get("project_name") for w in watchers_cfg):
        try:
            projects = client.get_projects()
            projects_cache = {p["name"]: p for p in projects}
        except Exception as e:
            logger.error(f"Failed to fetch projects from API: {e}")
            # All watchers with project_name will fail
            projects_cache = {}

    for watcher_cfg in watchers_cfg:
        result, error = resolve_watcher_config(
            watcher_cfg, client, projects_cache, storage_roots_cache
        )
        if result:
            resolved.append(result)
        else:
            failed.append((watcher_cfg, error or "Unknown error"))

    return resolved, failed


def _get_server_url(config: dict) -> str:
    """Get server URL from config with backward compatibility."""
    # Prefer server_url (new)
    if "server_url" in config:
        return config["server_url"]
    # Fall back to supervisor_url (deprecated)
    if "supervisor_url" in config:
        _emit_deprecation_warning("supervisor_url", "server_url")
        return config["supervisor_url"]
    raise ValueError("Missing required config: server_url (or supervisor_url)")


def run_watcher(config_path: str):
    """Run the folder watcher based on configuration."""
    config = load_config(config_path)

    # Print startup banner
    print("=" * 60)
    print("metaFirst Ingest Helper")
    print("=" * 60)
    print(f"Config file: {config_path}")

    # Get server URL with backward compatibility
    server_url = _get_server_url(config)

    # Initialize client
    client = SupervisorClient(
        base_url=server_url,
        username=config["username"],
        password=config["password"],
    )

    # Test connection
    try:
        client._get_token()
        print(f"Connected to server at {server_url}")
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        sys.exit(1)

    # Resolve lab_id (required for scoping)
    lab_id, error = resolve_lab_id(config, client)
    if error:
        print(f"[ERROR] {error}")
        sys.exit(1)

    # Show lab binding
    try:
        labs = client.get_supervisors()
        lab_name = next(
            (s["name"] for s in labs if s["id"] == lab_id),
            f"<unknown id={lab_id}>"
        )
    except Exception:
        lab_name = f"<id={lab_id}>"

    print(f"Bound to lab: {lab_name} (id={lab_id})")

    # Get UI settings
    ui_base_url = config.get("ui_url", "http://localhost:5173")
    open_browser = config.get("open_browser", False)

    print(f"UI URL: {ui_base_url}")
    print(f"Auto-open browser: {open_browser}")
    print("-" * 60)

    # Resolve watcher configs (convert names to IDs if needed)
    watchers_cfg = config.get("watchers", [])
    if not watchers_cfg:
        print("[ERROR] No watchers configured")
        sys.exit(1)

    print(f"Resolving {len(watchers_cfg)} watcher configuration(s)...")

    resolved_watchers, failed_watchers = resolve_all_watchers(watchers_cfg, client)

    # Log any failed watchers
    for failed_cfg, error_msg in failed_watchers:
        watch_path = failed_cfg.get("watch_path", "<unknown>")
        print(f"[SKIP] {watch_path}: {error_msg}")

    # Exit if no valid watchers
    if not resolved_watchers:
        print("\n[ERROR] No valid watchers after resolution. Please fix configuration.")
        sys.exit(1)

    # Check if any resolution happened by name
    any_resolved_by_name = any(w.resolved_by_name for w in resolved_watchers)

    # Print resolved mappings banner
    print("-" * 60)
    print("Resolved watcher mappings:")
    for resolved in resolved_watchers:
        project_display = (
            f"{resolved.project_name} (id={resolved.project_id})"
            if resolved.project_name
            else f"id={resolved.project_id}"
        )
        storage_display = (
            f"{resolved.storage_root_name} (id={resolved.storage_root_id})"
            if resolved.storage_root_name
            else f"id={resolved.storage_root_id}"
        )
        print(f"  {resolved.watch_path}")
        print(f"    -> project: {project_display}")
        print(f"    -> storage_root: {storage_display}")

    # Print caution note if names were resolved
    if any_resolved_by_name:
        print("-" * 60)
        print("[NOTE] Resolved names to IDs at startup.")
        print("       After database reseed, re-run helper if projects/storage roots change.")

    print("=" * 60)

    # Set up observers for each watcher
    observer = Observer()
    handlers = []
    active_watchers = 0

    for resolved in resolved_watchers:
        watcher_config = WatcherConfig(
            watch_path=resolved.watch_path,
            project_id=resolved.project_id,
            storage_root_id=resolved.storage_root_id,
            base_path_for_relative=resolved.base_path_for_relative,
            sample_identifier_pattern=resolved.sample_identifier_pattern,
        )

        handler = IngestEventHandler(
            client=client,
            watcher_config=watcher_config,
            supervisor_id=lab_id,  # Internal param still named supervisor_id for compat
            compute_hash=config.get("compute_hash", False),
            open_browser=open_browser,
            ui_base_url=ui_base_url,
        )
        handlers.append(handler)

        # Schedule observer
        if not watcher_config.watch_path.exists():
            print(f"[WARN] Watch path does not exist: {watcher_config.watch_path}")
            continue

        observer.schedule(handler, str(watcher_config.watch_path), recursive=True)
        active_watchers += 1
        print(f"[WATCH] {watcher_config.watch_path}")

    if active_watchers == 0:
        print("[ERROR] No valid watch paths found. All paths may not exist.")
        client.close()
        sys.exit(1)

    # Start observer
    observer.start()
    print(f"\n[READY] Watching {active_watchers} folder(s) for new files. Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down...")
        observer.stop()

    observer.join()
    client.close()
    print("[DONE] Watcher stopped.")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python metafirst_ingest.py <config.yaml>")
        print("\nExample config.yaml:")
        print("""
server_url: http://localhost:8000  # or supervisor_url (deprecated)
ui_url: http://localhost:5173
username: alice
password: demo123

# Lab binding (required if multiple labs exist)
# If omitted and exactly one lab exists, auto-binds to it.
lab_id: 1  # or supervisor_id (deprecated)

compute_hash: false
open_browser: true  # Open browser when new file detected
watchers:
  # Using numeric IDs (classic):
  - watch_path: /path/to/data/folder
    project_id: 1
    storage_root_id: 1
    base_path_for_relative: /path/to/data
    sample_identifier_pattern: "^([A-Z]+-\\d+)"

  # Using names (resolved at startup):
  - watch_path: /path/to/other/folder
    project_name: "My Project"
    storage_root_name: "LOCAL_DATA"
""")
        sys.exit(1)

    config_path = sys.argv[1]
    if not os.path.exists(config_path):
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)

    run_watcher(config_path)


if __name__ == "__main__":
    main()
