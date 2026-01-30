#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# install_user.sh
# Sets up the metaFirst ingest helper for users (researchers / data stewards).
# Run from the repository root: ./scripts/install_user.sh
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
NON_INTERACTIVE=false
MIN_PYTHON_VERSION="3.11"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Sets up the metaFirst ingest helper for local file watching and metadata entry.

Options:
  --non-interactive  Skip all prompts (use defaults)
  -h, --help         Show this help message

Environment variables:
  PYTHON_BIN         Path to Python binary (default: auto-detect python3.13/3.12/3.11/python3)

Run from the repository root:
  ./scripts/install_user.sh
EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

echo "=============================================="
echo "metaFirst Ingest Helper Installation"
echo "=============================================="

# Validate we're in the repo root
if [[ ! -f "$REPO_ROOT/ingest_helper/metafirst_ingest.py" ]]; then
    echo "ERROR: Must run from repository root (could not find ingest_helper/metafirst_ingest.py)"
    echo "Usage: ./scripts/install_user.sh"
    exit 1
fi

cd "$REPO_ROOT"

# -----------------------------------------------------------------------------
# Python detection and version check
# -----------------------------------------------------------------------------

find_python() {
    # If PYTHON_BIN is set, use it
    if [[ -n "${PYTHON_BIN:-}" ]]; then
        if [[ -x "$PYTHON_BIN" ]]; then
            echo "$PYTHON_BIN"
            return 0
        else
            echo "ERROR: PYTHON_BIN=$PYTHON_BIN is not executable" >&2
            exit 1
        fi
    fi

    # Try specific versions first (prefer newer)
    for py in python3.13 python3.12 python3.11 python3; do
        if command -v "$py" &> /dev/null; then
            echo "$py"
            return 0
        fi
    done

    return 1
}

check_python_version() {
    local python_bin="$1"
    local version
    version=$("$python_bin" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

    local major minor
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)

    local min_major min_minor
    min_major=$(echo "$MIN_PYTHON_VERSION" | cut -d. -f1)
    min_minor=$(echo "$MIN_PYTHON_VERSION" | cut -d. -f2)

    if [[ "$major" -lt "$min_major" ]] || { [[ "$major" -eq "$min_major" ]] && [[ "$minor" -lt "$min_minor" ]]; }; then
        echo ""
        echo "ERROR: Python $version is too old. Requires Python >= $MIN_PYTHON_VERSION"
        echo ""
        echo "Solutions:"
        echo "  macOS (Homebrew):  brew install python@3.12"
        echo "  Conda:             conda create -n metafirst python=3.12 && conda activate metafirst"
        echo "  Override:          PYTHON_BIN=/path/to/python3.12 $0"
        echo ""
        exit 1
    fi

    echo "$version"
}

PYTHON_BIN=$(find_python) || {
    echo "ERROR: python3 not found. Please install Python $MIN_PYTHON_VERSION or later."
    echo ""
    echo "Solutions:"
    echo "  macOS (Homebrew):  brew install python@3.12"
    echo "  Conda:             conda create -n metafirst python=3.12 && conda activate metafirst"
    exit 1
}

PYTHON_VERSION=$(check_python_version "$PYTHON_BIN")
echo "Using Python $PYTHON_VERSION ($PYTHON_BIN)"

echo ""
echo "Setting up ingest helper..."
echo "----------------------------------------------"

# -----------------------------------------------------------------------------
# Virtual environment setup with broken venv detection
# -----------------------------------------------------------------------------

VENV_DIR="$REPO_ROOT/ingest_helper/venv"

setup_venv() {
    if [[ -d "$VENV_DIR" ]]; then
        echo "Virtual environment exists at ingest_helper/venv"

        # Check if venv is broken (pip missing or not working)
        if ! "$VENV_DIR/bin/python" -m pip --version &> /dev/null; then
            echo "WARNING: Virtual environment appears broken (pip not working)"

            # Try to fix with ensurepip
            echo "Attempting to fix with ensurepip..."
            if "$VENV_DIR/bin/python" -m ensurepip --upgrade &> /dev/null; then
                echo "Fixed: ensurepip succeeded"
            else
                echo "Recreating virtual environment..."
                rm -rf "$VENV_DIR"
                "$PYTHON_BIN" -m venv "$VENV_DIR"
            fi
        fi
    else
        echo "Creating virtual environment at ingest_helper/venv..."
        "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi
}

setup_venv

# Activate venv
source "$VENV_DIR/bin/activate"

# Verify pip works
if ! python -m pip --version &> /dev/null; then
    echo "ERROR: pip is not working in the virtual environment."
    echo "Try deleting ingest_helper/venv and running this script again."
    exit 1
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "$REPO_ROOT/ingest_helper/requirements.txt"

echo "Dependencies installed."

# Verify watchdog import
echo "Verifying watchdog installation..."
if ! python -c "import watchdog" 2>/dev/null; then
    echo "ERROR: watchdog module failed to import."
    echo "Try reinstalling: pip install watchdog"
    exit 1
fi
echo "watchdog module OK."

# Create config.yaml if missing
CONFIG_FILE="$REPO_ROOT/ingest_helper/config.yaml"
CONFIG_EXAMPLE="$REPO_ROOT/ingest_helper/config.example.yaml"
CONFIG_CREATED=false

if [[ ! -f "$CONFIG_FILE" ]]; then
    if [[ -f "$CONFIG_EXAMPLE" ]]; then
        echo ""
        echo "Creating config.yaml from config.example.yaml..."
        cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
        echo "Created: ingest_helper/config.yaml"
        CONFIG_CREATED=true
    else
        echo "WARNING: config.example.yaml not found. Create config.yaml manually."
    fi
else
    echo "config.yaml already exists."
fi

echo ""
echo "=============================================="
echo "Ingest helper installation complete!"
echo "=============================================="

if [[ "$CONFIG_CREATED" == "true" ]]; then
    echo ""
    echo "IMPORTANT: Edit ingest_helper/config.yaml before running:"
    echo "  - supervisor_url: URL of your supervisor instance"
    echo "  - ui_url: URL of the web UI"
    echo "  - username/password: Your credentials"
    echo "  - watchers: Folders to watch with project_name + storage_root_name"
    echo ""
    echo "Use name-based config (project_name, storage_root_name) for portability."
    echo "Demo projects include storage root 'LOCAL_DATA' by default."
    echo ""
    echo "See ingest_helper/README.md for configuration details."
fi

echo ""
echo "To start the ingest helper:"
echo "  cd $REPO_ROOT/ingest_helper"
echo "  source venv/bin/activate"
echo "  python metafirst_ingest.py config.yaml"
echo ""
echo "The ingest helper will watch configured folders for new files."
echo "Raw data stays on your machine; only metadata is sent to the supervisor."
