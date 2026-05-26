#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Ensure uv is available ─────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo ""
    echo "  ERROR: 'uv' is not installed."
    echo ""
    echo "  Install it with one of:"
    echo "    Linux/Mac:  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "    Windows:    powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\""
    echo "    pip:        pip install uv"
    echo ""
    echo "  Then re-run this script."
    exit 1
fi

echo "==> Syncing dependencies..."
uv sync --quiet

echo "==> Running migrations..."
uv run python manage.py migrate --run-syncdb

# ── Optional: seed test data on first run ──────────────────────────────────
if [ ! -f ".seeded" ]; then
    echo "==> Seeding test data (first run)..."
    uv run python manage.py seed && touch .seeded
fi

echo ""
echo "==> StudentGig is running at http://127.0.0.1:8000"
echo ""
echo "    Home       http://127.0.0.1:8000/"
echo "    Register   http://127.0.0.1:8000/accounts/register/"
echo "    Login      http://127.0.0.1:8000/accounts/login/"
echo "    Admin      http://127.0.0.1:8000/admin/    (admin / admin)"
echo ""
echo "    Test accounts (from seed):"
echo "      student1 / pass1234   KYC verified — has listings and contracts"
echo "      student2 / pass1234   KYC pending  — use 'Simulate KYC' button"
echo "      client1  / pass1234   KYC verified — has bids and contracts"
echo ""

uv run python manage.py runserver 8000
