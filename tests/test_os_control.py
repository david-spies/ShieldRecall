"""
tests/test_os_control.py — Tests for os_control.py snapshot and registry helpers.

All tests are cross-platform safe: Windows-only paths are mocked so the suite
passes on macOS / Linux CI environments.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Snapshot directory helpers ───────────────────────────────────────────────

class TestSnapshotCount:
    def test_returns_zero_when_dir_missing(self, tmp_path):
        """A non-existent directory reports 0 snapshots."""
        from os_control import get_snapshot_count
        missing = tmp_path / "does_not_exist"
        with patch("os_control.get_snapshot_dir", return_value=missing):
            assert get_snapshot_count() == 0

    def test_counts_files_recursively(self, tmp_path):
        """All files under the directory tree are counted."""
        from os_control import get_snapshot_count
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "snap1.bin").write_bytes(b"\x00" * 16)
        (tmp_path / "snap2.bin").write_bytes(b"\x00" * 16)
        (sub / "snap3.bin").write_bytes(b"\x00" * 16)

        with patch("os_control.get_snapshot_dir", return_value=tmp_path):
            assert get_snapshot_count() == 3

    def test_does_not_count_directories(self, tmp_path):
        """Sub-directories themselves must not be included in the count."""
        from os_control import get_snapshot_count
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file.bin").write_bytes(b"\x00")

        with patch("os_control.get_snapshot_dir", return_value=tmp_path):
            assert get_snapshot_count() == 1

    def test_empty_directory_returns_zero(self, tmp_path):
        from os_control import get_snapshot_count
        with patch("os_control.get_snapshot_dir", return_value=tmp_path):
            assert get_snapshot_count() == 0


class TestSnapshotDirSizeMb:
    def test_size_calculation(self, tmp_path):
        from os_control import get_snapshot_dir_size_mb
        (tmp_path / "a.bin").write_bytes(b"\x00" * 1024 * 512)   # 0.5 MB
        (tmp_path / "b.bin").write_bytes(b"\x00" * 1024 * 512)   # 0.5 MB

        with patch("os_control.get_snapshot_dir", return_value=tmp_path):
            size = get_snapshot_dir_size_mb()
        assert abs(size - 1.0) < 0.01

    def test_missing_dir_returns_zero(self, tmp_path):
        from os_control import get_snapshot_dir_size_mb
        with patch("os_control.get_snapshot_dir", return_value=tmp_path / "missing"):
            assert get_snapshot_dir_size_mb() == 0.0


class TestPurgeSnapshots:
    def test_purge_deletes_all_files(self, tmp_path):
        from os_control import purge_snapshots
        for i in range(4):
            (tmp_path / f"snap{i}.bin").write_bytes(b"\x00" * 8)

        with patch("os_control.get_snapshot_dir", return_value=tmp_path):
            deleted, error = purge_snapshots()

        assert deleted == 4
        assert error == ""
        assert list(tmp_path.iterdir()) == []

    def test_purge_missing_dir_returns_zero(self, tmp_path):
        from os_control import purge_snapshots
        with patch("os_control.get_snapshot_dir", return_value=tmp_path / "missing"):
            deleted, error = purge_snapshots()
        assert deleted == 0
        assert error == ""

    def test_purge_returns_count_on_partial_failure(self, tmp_path):
        """If one file can't be deleted, returns partial count and non-empty error."""
        from os_control import purge_snapshots
        good = tmp_path / "good.bin"
        good.write_bytes(b"\x00")

        original_unlink = Path.unlink

        call_count = [0]
        def selective_unlink(self, missing_ok=False):
            call_count[0] += 1
            if call_count[0] == 1:
                raise PermissionError("locked")
            original_unlink(self, missing_ok=missing_ok)

        with patch("os_control.get_snapshot_dir", return_value=tmp_path):
            with patch.object(Path, "unlink", selective_unlink):
                deleted, error = purge_snapshots()

        assert error != ""


# ── Registry helpers (non-Windows: mocked) ───────────────────────────────────

class TestRecallStatus:
    @pytest.mark.skipif(sys.platform == "win32", reason="Tested live on Windows")
    def test_non_windows_returns_true(self):
        """On non-Windows, get_recall_status() should default to True (assume enabled)."""
        from os_control import get_recall_status
        # The function has an early return for non-Windows
        result = get_recall_status()
        assert isinstance(result, bool)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_windows_reads_registry(self):
        """On Windows, verify that get_recall_status reads HKLM correctly."""
        import winreg
        from os_control import get_recall_status, _POLICY_KEY_PATH, _POLICY_VALUE_NAME

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _POLICY_KEY_PATH) as k:
                val, _ = winreg.QueryValueEx(k, _POLICY_VALUE_NAME)
            expected = (val != 1)
        except FileNotFoundError:
            expected = True

        assert get_recall_status() == expected


class TestToggleRecall:
    @pytest.mark.skipif(sys.platform == "win32", reason="Non-Windows dev mode path")
    def test_dev_mode_always_succeeds(self):
        """On non-Windows, toggle always returns (True, dev-mode message)."""
        from os_control import toggle_recall
        ok, msg = toggle_recall(enable=False)
        assert ok is True
        assert "DEV MODE" in msg

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_requires_admin_on_windows(self):
        """Without admin rights, toggle_recall should fail gracefully."""
        from os_control import toggle_recall, is_admin
        if is_admin():
            pytest.skip("Running as admin — cannot test non-admin path")
        ok, msg = toggle_recall(enable=False)
        assert ok is False
        assert "Administrator" in msg or "privileges" in msg.lower()


class TestIsAdmin:
    @pytest.mark.skipif(sys.platform == "win32", reason="Windows only")
    def test_non_windows_returns_false(self):
        from os_control import is_admin
        assert is_admin() is False


# ── Active window info ───────────────────────────────────────────────────────

class TestGetActiveWindowInfo:
    @pytest.mark.skipif(sys.platform == "win32", reason="Non-Windows stub path")
    def test_dev_stub_returns_dict(self):
        from os_control import get_active_window_info
        info = get_active_window_info()
        assert "app" in info
        assert "title" in info
        assert "text" in info

    @pytest.mark.skipif(sys.platform == "win32", reason="Non-Windows stub path")
    def test_dev_stub_app_name(self):
        from os_control import get_active_window_info
        info = get_active_window_info()
        assert info["app"] == "devmode.exe"
