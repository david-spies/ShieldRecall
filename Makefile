# ============================================================
# Makefile — Shield Recall developer tasks
# ============================================================

PYTHON   ?= python
VENV_DIR  = .venv
VENV_PY   = $(VENV_DIR)/bin/python
PIP       = $(VENV_PY) -m pip

.PHONY: all venv install model run debug test lint typecheck clean build help

all: help

# ── Setup ──────────────────────────────────────────────────────────────────

venv:
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "✓ .venv created. Run: source .venv/bin/activate"

install: venv
	@echo "Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "✓ Dependencies installed."

model:
	@echo "Downloading spaCy en_core_web_lg model (~750 MB)..."
	$(VENV_PY) -m spacy download en_core_web_lg
	@echo "✓ Model ready."

# ── Run ────────────────────────────────────────────────────────────────────

run:
	@echo "Starting Shield Recall on http://127.0.0.1:8000"
	$(VENV_PY) main.py

debug:
	DEBUG=true $(VENV_PY) -m uvicorn main:app \
	  --host 127.0.0.1 --port 8000 \
	  --reload --log-level debug

# ── Test ───────────────────────────────────────────────────────────────────

test:
	$(VENV_PY) -m pytest tests/ -v

test-fast:
	$(VENV_PY) -m pytest tests/test_pii_engine.py tests/test_database.py -v

coverage:
	$(VENV_PY) -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html
	@echo "HTML report: htmlcov/index.html"

# ── Code quality ───────────────────────────────────────────────────────────

lint:
	$(VENV_PY) -m ruff check .

format:
	$(VENV_PY) -m ruff format .

typecheck:
	$(VENV_PY) -m mypy main.py config.py pii_engine.py database.py os_control.py

# ── Build ──────────────────────────────────────────────────────────────────

build:
	@echo "Building Windows executable with PyInstaller..."
	$(VENV_PY) -m PyInstaller \
	  --uac-admin \
	  --onefile \
	  --name ShieldRecall \
	  --add-data "templates;templates" \
	  --add-data "static;static" \
	  main.py
	@echo "✓ dist/ShieldRecall.exe ready."

# ── Cleanup ────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .mypy_cache .ruff_cache
	rm -f secure_recall.db secure_recall.db-wal secure_recall.db-shm

distclean: clean
	rm -rf $(VENV_DIR) dist/ build/ *.spec

# ── Help ───────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Shield Recall — developer commands"
	@echo ""
	@echo "  Setup:"
	@echo "    make install    Create .venv and install all dependencies"
	@echo "    make model      Download spaCy NER model (required for Presidio)"
	@echo ""
	@echo "  Run:"
	@echo "    make run        Start the dashboard (http://127.0.0.1:8000)"
	@echo "    make debug      Hot-reload dev server with verbose logging"
	@echo ""
	@echo "  Test:"
	@echo "    make test       Full test suite"
	@echo "    make test-fast  PII + DB tests only (no network, fast)"
	@echo "    make coverage   Generate HTML coverage report"
	@echo ""
	@echo "  Quality:"
	@echo "    make lint       Ruff linter"
	@echo "    make format     Ruff formatter"
	@echo "    make typecheck  mypy static type check"
	@echo ""
	@echo "  Build:"
	@echo "    make build      Compile dist/ShieldRecall.exe (Windows)"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean      Remove caches and DB files"
	@echo "    make distclean  Remove .venv, dist/, build/ too"
	@echo ""
