#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# install_user.sh
# Sets up the metaFirst ingest helper for users (researchers / data stewards).
# Run from the repository root: ./scripts/install_user.sh
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Sets up the metaFirst ingest helper for local file watching and metadata entry.

Options:
  --non-interactive  Skip all prompts (use defaults)
  -h, --help         Show this help message

Run from the repository root:
  ./scripts/install_user.sh
EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --non-interactive)
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

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.11 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Found Python $PYTHON_VERSION"

echo ""
echo "Setting up ingest helper..."
echo "----------------------------------------------"

# Create venv if missing (separate from supervisor for cleaner user setup)
VENV_DIR="$REPO_ROOT/ingest_helper/venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment at ingest_helper/venv..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists at ingest_helper/venv"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

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

if [[ ! -f "$CONFIG_FILE" ]]; then
    if [[ -f "$CONFIG_EXAMPLE" ]]; then
        echo ""
        echo "Creating config.yaml from config.example.yaml..."
        cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
        echo "Created: ingest_helper/config.yaml"
        CONFIG_CREATED=true
    else
        echo "WARNING: config.example.yaml not found. Create config.yaml manually."
        CONFIG_CREATED=false
    fi
else
    echo "config.yaml already exists."
    CONFIG_CREATED=false
fi

echo ""
echo "=============================================="
echo "Ingest helper installation complete!"
echo "=============================================="

if [[ "${CONFIG_CREATED:-false}" == "true" ]]; then
    echo ""
    echo "IMPORTANT: Edit ingest_helper/config.yaml before running:"
    echo "  - supervisor_url: URL of your supervisor instance"
    echo "  - ui_url: URL of the web UI"
    echo "  - username/password: Your credentials"
    echo "  - watchers: Folders to watch and their project/storage root mappings"
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
