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

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Sets up the metaFirst supervisor backend.

Options:
  --seed          Seed demo data (even if database exists)
  --no-seed       Do not seed demo data
  --non-interactive  Skip all prompts (use defaults)
  -h, --help      Show this help message

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

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.11 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Found Python $PYTHON_VERSION"

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

# Create venv if missing
VENV_DIR="$REPO_ROOT/supervisor/venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment at supervisor/venv..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists at supervisor/venv"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

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
