#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# install_supervisor.sh
# Sets up the metaFirst supervisor backend and optionally seeds demo data.
# Run from the repository root: ./scripts/install_supervisor.sh
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
SEED_DATA=auto
NON_INTERACTIVE=false
MIN_PYTHON_VERSION="3.11"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Sets up the metaFirst supervisor backend.

Options:
  --seed             Seed demo data (even if database exists)
  --no-seed          Do not seed demo data
  --non-interactive  Skip all prompts (use defaults)
  -h, --help         Show this help message

Environment variables:
  PYTHON_BIN         Path to Python binary (default: auto-detect python3.13/3.12/3.11/python3)

By default, demo data is seeded if the database does not exist.

Run from the repository root:
  ./scripts/install_supervisor.sh
EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --seed)
            SEED_DATA=yes
            shift
            ;;
        --no-seed)
            SEED_DATA=no
            shift
            ;;
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
echo "metaFirst Supervisor Installation"
echo "=============================================="

# Validate we're in the repo root
if [[ ! -f "$REPO_ROOT/supervisor/pyproject.toml" ]]; then
    echo "ERROR: Must run from repository root (could not find supervisor/pyproject.toml)"
    echo "Usage: ./scripts/install_supervisor.sh"
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

# Check Node.js (warn if missing, don't fail)
NODE_AVAILABLE=false
if command -v node &> /dev/null && command -v npm &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "Found Node.js $NODE_VERSION"
    NODE_AVAILABLE=true
else
    echo "WARNING: Node.js/npm not found. The web UI requires Node.js 18+."
    echo "         Backend API will work without it."
fi

echo ""
echo "Setting up supervisor backend..."
echo "----------------------------------------------"

# -----------------------------------------------------------------------------
# Virtual environment setup with broken venv detection
# -----------------------------------------------------------------------------

VENV_DIR="$REPO_ROOT/supervisor/venv"
VENV_CREATED=false

setup_venv() {
    if [[ -d "$VENV_DIR" ]]; then
        echo "Virtual environment exists at supervisor/venv"

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
                VENV_CREATED=true
            fi
        fi
    else
        echo "Creating virtual environment at supervisor/venv..."
        "$PYTHON_BIN" -m venv "$VENV_DIR"
        VENV_CREATED=true
    fi
}

setup_venv

# Activate venv
source "$VENV_DIR/bin/activate"

# Verify pip works
if ! python -m pip --version &> /dev/null; then
    echo "ERROR: pip is not working in the virtual environment."
    echo "Try deleting supervisor/venv and running this script again."
    exit 1
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -e "$REPO_ROOT/supervisor[dev]"

echo "Dependencies installed."

# Check if database exists
DB_PATH="$REPO_ROOT/supervisor/supervisor.db"
DB_EXISTS=false
if [[ -f "$DB_PATH" ]]; then
    DB_EXISTS=true
fi

# Determine whether to seed
DO_SEED=false
if [[ "$SEED_DATA" == "yes" ]]; then
    DO_SEED=true
elif [[ "$SEED_DATA" == "no" ]]; then
    DO_SEED=false
elif [[ "$SEED_DATA" == "auto" ]]; then
    if [[ "$DB_EXISTS" == "false" ]]; then
        DO_SEED=true
    elif [[ "$NON_INTERACTIVE" == "false" ]]; then
        echo ""
        read -p "Database exists. Re-seed demo data? (y/N): " response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            DO_SEED=true
        fi
    fi
fi

if [[ "$DO_SEED" == "true" ]]; then
    echo ""
    echo "Seeding demo data..."
    python "$REPO_ROOT/demo/seed.py"
    echo "Demo data seeded."
else
    echo "Skipping demo data seeding."
fi

echo ""
echo "=============================================="
echo "Supervisor installation complete!"
echo "=============================================="
echo ""
echo "To start the backend API:"
echo "  cd $REPO_ROOT/supervisor"
echo "  source venv/bin/activate"
echo "  uvicorn supervisor.main:app --reload --port 8000"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"

if [[ "$NODE_AVAILABLE" == "true" ]]; then
    echo ""
    echo "To start the web UI (in a new terminal):"
    echo "  cd $REPO_ROOT/supervisor-ui"
    echo "  npm install"
    echo "  npm run dev"
    echo ""
    echo "UI will be available at: http://localhost:5173"
else
    echo ""
    echo "To start the web UI, first install Node.js 18+, then:"
    echo "  cd $REPO_ROOT/supervisor-ui"
    echo "  npm install"
    echo "  npm run dev"
fi

echo ""
echo "Demo users: alice, bob, carol, david, eve (password: demo123)"
