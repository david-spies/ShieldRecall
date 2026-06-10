"""
tests/test_routes.py — Integration tests for the FastAPI endpoints.

Uses FastAPI's TestClient (synchronous wrapper around httpx) so no real
uvicorn server is needed. Windows-specific OS calls are mocked to keep
the suite cross-platform.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# ── Patch OS and DB before importing main ────────────────────────────────────
# We patch at the module level so the app starts cleanly without touching
# the real Windows registry or filesystem.

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("db")
    db_path = str(tmp / "test.db")

    with (
        patch("main.get_snapshot_count", return_value=42),
        patch("main.get_snapshot_dir_size_mb", return_value=1.5),
        patch("main.get_recall_status", return_value=True),
        patch("main.is_admin", return_value=True),
        patch("main.settings.LOCAL_DB_PATH", db_path),
        patch("main.db.db_path", db_path),
    ):
        from main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── Health check ─────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_json_structure(self, client):
        r = client.get("/health")
        data = r.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "recall_active" in data
        assert "snapshot_count" in data


# ── Dashboard page ────────────────────────────────────────────────────────────

class TestDashboard:
    def test_returns_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_contains_app_name(self, client):
        r = client.get("/")
        assert "ShieldRecall" in r.text or "Shield Recall" in r.text

    def test_contains_kill_switch(self, client):
        r = client.get("/")
        assert "recall/toggle" in r.text or "Kill Recall" in r.text


# ── Telemetry counter partial ─────────────────────────────────────────────────

class TestTelemetryCounter:
    def test_returns_html_span(self, client):
        with patch("main.get_snapshot_count", return_value=77):
            r = client.get("/api/telemetry/counter")
        assert r.status_code == 200
        assert "77" in r.text
        assert "<span" in r.text

    def test_high_count_gets_red_class(self, client):
        with patch("main.get_snapshot_count", return_value=200):
            r = client.get("/api/telemetry/counter")
        assert "val-red" in r.text

    def test_medium_count_gets_amber_class(self, client):
        with patch("main.get_snapshot_count", return_value=100):
            r = client.get("/api/telemetry/counter")
        assert "val-amber" in r.text

    def test_low_count_gets_teal_class(self, client):
        with patch("main.get_snapshot_count", return_value=10):
            r = client.get("/api/telemetry/counter")
        assert "val-teal" in r.text


# ── Telemetry JSON ────────────────────────────────────────────────────────────

class TestTelemetryJson:
    def test_returns_json(self, client):
        r = client.get("/api/telemetry")
        assert r.status_code == 200
        data = r.json()
        assert "snapshot_count" in data
        assert "recall_active" in data
        assert "is_admin" in data
        assert "stats" in data


# ── Recall toggle ─────────────────────────────────────────────────────────────

class TestRecallToggle:
    def test_toggle_success_returns_html(self, client):
        with (
            patch("main.get_recall_status", return_value=True),
            patch("main.toggle_recall", return_value=(True, "Registry updated")),
            patch("main.is_admin", return_value=True),
        ):
            r = client.post("/api/recall/toggle")
        assert r.status_code == 200
        assert "<div" in r.text  # returns HTML partial

    def test_toggle_no_admin_returns_403(self, client):
        with (
            patch("main.get_recall_status", return_value=True),
            patch("main.toggle_recall", return_value=(False, "Administrator privileges required")),
        ):
            r = client.post("/api/recall/toggle")
        assert r.status_code == 403
        assert "Administrator" in r.text or "Failed" in r.text or "error-banner" in r.text


# ── Purge snapshots ───────────────────────────────────────────────────────────

class TestPurgeSnapshots:
    def test_purge_returns_json(self, client):
        with patch("main.purge_snapshots", return_value=(15, "")):
            r = client.post("/api/recall/purge")
        assert r.status_code == 200
        data = r.json()
        assert data["deleted"] == 15
        assert data["error"] == ""

    def test_partial_purge_includes_error(self, client):
        with patch("main.purge_snapshots", return_value=(3, "2 files could not be deleted")):
            r = client.post("/api/recall/purge")
        data = r.json()
        assert data["deleted"] == 3
        assert data["error"] != ""


# ── Audit search ──────────────────────────────────────────────────────────────

class TestAuditSearch:
    def test_empty_query_returns_empty_state(self, client):
        r = client.post("/api/search", data={"query": "", "app_filter": "", "min_risk": "0"})
        assert r.status_code == 200
        # Empty query with no records should show empty-state message
        assert "empty" in r.text.lower() or "No matching" in r.text

    def test_search_with_results(self, client):
        # Seed the DB directly
        from main import db
        db.insert_entry("Slack.exe", "DM", "quarterly revenue discussion", 0.1, 0)
        r = client.post(
            "/api/search",
            data={"query": "quarterly", "app_filter": "", "min_risk": "0"},
        )
        assert r.status_code == 200
        assert "Slack.exe" in r.text or "quarterly" in r.text

    def test_search_no_match(self, client):
        r = client.post(
            "/api/search",
            data={"query": "xyzzy_not_a_real_word", "app_filter": "", "min_risk": "0"},
        )
        assert r.status_code == 200
        assert "No matching" in r.text


# ── Stats endpoint ────────────────────────────────────────────────────────────

class TestStatsEndpoint:
    def test_returns_json_with_keys(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        # May be empty DB — just check keys exist
        assert isinstance(data, dict)


# ── Timeline wipe ─────────────────────────────────────────────────────────────

class TestTimelineWipe:
    def test_delete_returns_count(self, client):
        from main import db
        db.insert_entry("App.exe", "Win", "data", 0.5, 1)
        r = client.delete("/api/timeline")
        assert r.status_code == 200
        data = r.json()
        assert "deleted" in data
        assert isinstance(data["deleted"], int)
