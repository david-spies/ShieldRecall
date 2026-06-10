"""
conftest.py — shared pytest fixtures available to all test modules.

Fixtures defined here are auto-discovered by pytest; no import needed in test files.
"""

import pytest
from pathlib import Path


# ── Temporary database path ──────────────────────────────────────────────────

@pytest.fixture(scope="function")
def tmp_db_path(tmp_path: Path) -> str:
    """Returns a fresh, isolated SQLite file path for each test function."""
    return str(tmp_path / "test_shield_recall.db")


# ── PrivacyEngine (module-scoped to load Presidio once per session) ──────────

@pytest.fixture(scope="module")
def privacy_engine():
    """
    Module-scoped PrivacyEngine. Presidio's spaCy model loads once and is
    reused across all tests in the same module, keeping the suite fast.
    """
    from pii_engine import PrivacyEngine
    return PrivacyEngine(entropy_threshold=4.0)


# ── EncryptedStorage with auto-cleanup ───────────────────────────────────────

@pytest.fixture(scope="function")
def storage(tmp_db_path: str):
    """Fresh EncryptedStorage for each test; the file is deleted when the test ends."""
    from database import EncryptedStorage
    return EncryptedStorage(db_path=tmp_db_path)


# ── Sample text corpus ───────────────────────────────────────────────────────

@pytest.fixture
def clean_prose() -> str:
    return "The board meeting is scheduled for Tuesday afternoon in Conference Room B."


@pytest.fixture
def pii_text() -> str:
    return (
        "Please invoice John Smith at john.smith@acme.com. "
        "His SSN is 123-45-6789 and card ending 4111111111111111. "
        "Call him at 555-867-5309."
    )


@pytest.fixture
def credential_text() -> str:
    return (
        "Logged into portal. api_key=sk-a3f9c2d8b1e7f4a6 "
        "password=Tr0ub4dor&3 "
        "stripe_secret=sk_live_ABCDEF1234567890abcdef1234567890"
    )


@pytest.fixture
def high_entropy_text() -> str:
    # 40-char base64-like blob that should trip the entropy scanner
    return "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
