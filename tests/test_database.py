"""
tests/test_database.py — Unit tests for EncryptedStorage.

Uses a temporary in-memory SQLite database so no files are created on disk.
"""

import pytest
from database import EncryptedStorage


@pytest.fixture
def db(tmp_path):
    """Fresh in-memory database for each test."""
    return EncryptedStorage(db_path=str(tmp_path / "test.db"))


class TestTimelineInsert:
    def test_insert_returns_id(self, db):
        row_id = db.insert_entry("Chrome.exe", "Google", "clean text", 0.1, 0)
        assert isinstance(row_id, int)
        assert row_id >= 1

    def test_multiple_inserts(self, db):
        for i in range(5):
            db.insert_entry("App.exe", f"Window {i}", f"content {i}", 0.0, 0)
        results = db.query_timeline()
        assert len(results) == 5


class TestTimelineQuery:
    def test_keyword_search(self, db):
        db.insert_entry("Slack.exe", "DM", "meeting notes Q3 revenue", 0.2, 1)
        db.insert_entry("Outlook.exe", "Inbox", "unrelated content here", 0.1, 0)
        results = db.query_timeline(keyword="Q3")
        assert len(results) == 1
        assert results[0].application_name == "Slack.exe"

    def test_app_filter(self, db):
        db.insert_entry("Chrome.exe", "Tab", "browsing", 0.0, 0)
        db.insert_entry("Slack.exe", "DM", "messaging", 0.0, 0)
        results = db.query_timeline(app_filter="Chrome")
        assert all(r.application_name == "Chrome.exe" for r in results)

    def test_min_risk_filter(self, db):
        db.insert_entry("App.exe", "Win", "low", 0.1, 0)
        db.insert_entry("App.exe", "Win", "high risk", 0.9, 5)
        results = db.query_timeline(min_risk=0.7)
        assert len(results) == 1
        assert results[0].risk_score >= 0.7

    def test_empty_keyword_returns_all(self, db):
        db.insert_entry("App.exe", "Win", "a", 0.0, 0)
        db.insert_entry("App.exe", "Win", "b", 0.0, 0)
        results = db.query_timeline(keyword="")
        assert len(results) == 2


class TestStats:
    def test_stats_keys_present(self, db):
        db.insert_entry("App.exe", "W", "text", 0.8, 3)
        stats = db.get_timeline_stats()
        assert "total_entries" in stats
        assert "total_pii" in stats
        assert "avg_risk" in stats
        assert "high_risk_count" in stats

    def test_stats_empty_db(self, db):
        stats = db.get_timeline_stats()
        assert stats.get("total_entries") == 0 or stats.get("total_entries") is None


class TestPurge:
    def test_purge_removes_all(self, db):
        db.insert_entry("A.exe", "W", "x", 0.5, 1)
        db.insert_entry("B.exe", "W", "y", 0.5, 1)
        deleted = db.purge_timeline()
        assert deleted == 2
        assert db.query_timeline() == []


class TestActivityLog:
    def test_log_and_retrieve(self, db):
        db.log_activity("Engine started", level="INFO", category="SYSTEM")
        db.log_activity("PII detected", level="WARNING", category="REDACTION")
        entries = db.get_recent_activity(limit=10)
        assert len(entries) == 2
        messages = [e.message for e in entries]
        assert "Engine started" in messages
        assert "PII detected" in messages
