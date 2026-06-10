#!/usr/bin/env bash
# ============================================================
# launch.sh — Shield Recall development launcher (macOS / Linux)
#
# Windows Recall features (registry, snapshot directory) run
# in dev-mode stubs on non-Windows platforms, so the full
# dashboard and PII pipeline can be exercised without a
# Windows host.
#
# Usage:
#   chmod +x launch.sh
#   ./launch.sh
#   ./launch.sh --debug    # enables hot-reload and verbose logging
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Python resolution ──────────────────────────────────────────────────────
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
  PYTHON="$VENV_PYTHON"
else
  PYTHON="${PYTHON:-python3}"
fi

# ── .env bootstrap ─────────────────────────────────────────────────────────
if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
  echo "⚠  .env not found — creating from .env.example"
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  echo "   Edit .env and set a strong SHIELD_RECALL_KEY before production use."
  echo
fi

# ── Dependency check ───────────────────────────────────────────────────────
if ! "$PYTHON" -c "import fastapi" 2>/dev/null; then
  echo "⚠  Dependencies not installed. Running: pip install -r requirements.txt"
  "$PYTHON" -m pip install -r requirements.txt --quiet
fi

# ── spaCy model check ──────────────────────────────────────────────────────
if ! "$PYTHON" -c "import spacy; spacy.load('en_core_web_lg')" 2>/dev/null; then
  echo "⚠  spaCy model 'en_core_web_lg' not found."
  read -r -p "   Download now? (~750 MB) [y/N]: " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    "$PYTHON" -m spacy download en_core_web_lg
  else
    echo "   Presidio NER layer will be disabled until the model is installed."
  fi
fi

# ── Launch ─────────────────────────────────────────────────────────────────
echo "============================================================"
echo "  🛡  Shield Recall — Enterprise Privacy Engine"
echo "============================================================"
echo "  Dashboard: http://127.0.0.1:8000"
echo "  Press Ctrl+C to stop."
echo

if [[ "${1:-}" == "--debug" ]]; then
  export DEBUG=true
  exec "$PYTHON" -m uvicorn main:app \
    --host 127.0.0.1 --port 8000 \
    --reload --log-level debug
else
  exec "$PYTHON" main.py
fi
