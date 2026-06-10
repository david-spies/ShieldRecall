"""
os_control.py — Windows-specific Recall telemetry and registry control.

All Windows API calls are guarded so the module imports cleanly on Linux / macOS
for development. On non-Windows platforms every function returns a safe fallback.

Registry path
-------------
HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsAI
  TurnOffWindowsRecall  REG_DWORD   1 = disabled, 0 (or absent) = enabled

This is the official Group Policy key documented by Microsoft. Setting it to 1
is equivalent to enabling the "Turn off Saving Snapshots for Windows Recall"
policy in the Local Group Policy Editor.

Snapshot directory
------------------
%USERPROFILE%\\AppData\\Local\\CoreAIPlatform\\CaptureRegions
  Contains .bin / .dat files written by the Recall subsystem.
  File count ≈ concurrent snapshots on disk.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_IS_WINDOWS = sys.platform == "win32"

# Registry constants (only available on Windows)
if _IS_WINDOWS:
    import winreg
    import ctypes

_POLICY_KEY_PATH = r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI"
_POLICY_VALUE_NAME = "TurnOffWindowsRecall"


# ---------------------------------------------------------------------------
# Admin / privilege detection
# ---------------------------------------------------------------------------

def is_admin() -> bool:
    """Returns True when the process has Windows administrator privileges."""
    if not _IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Snapshot directory counting
# ---------------------------------------------------------------------------

def get_snapshot_dir() -> Path:
    raw = os.path.expandvars(
        r"%USERPROFILE%\AppData\Local\CoreAIPlatform\CaptureRegions"
    )
    return Path(raw)


def get_snapshot_count() -> int:
    """
    Counts files in the Recall snapshot directory.

    Returns 0 if the directory does not exist (Recall never activated or
    already fully purged).

    Uses glob rather than os.listdir to avoid FileNotFoundError / PermissionError
    when the OS is actively writing to the directory.
    """
    snap_dir = get_snapshot_dir()
    if not snap_dir.exists():
        return 0
    try:
        return sum(1 for f in snap_dir.glob("**/*") if f.is_file())
    except PermissionError:
        logger.warning("Permission denied reading snapshot directory — count unavailable.")
        return -1
    except Exception as e:
        logger.error(f"Error reading snapshot directory: {e}")
        return -1


def get_snapshot_dir_size_mb() -> float:
    """Total size in MB of all snapshot files on disk."""
    snap_dir = get_snapshot_dir()
    if not snap_dir.exists():
        return 0.0
    try:
        total_bytes = sum(
            f.stat().st_size for f in snap_dir.glob("**/*") if f.is_file()
        )
        return round(total_bytes / (1024 * 1024), 2)
    except Exception:
        return 0.0


def purge_snapshots() -> tuple[int, str]:
    """
    Deletes all files in the Recall snapshot directory.

    Returns (files_deleted, error_message).
    error_message is empty on success.

    Requires the process to have write permission to the directory.
    On most systems this requires running as the owning user; admin is
    NOT required for user-profile directories.
    """
    snap_dir = get_snapshot_dir()
    if not snap_dir.exists():
        return 0, ""

    deleted = 0
    errors = []
    for f in snap_dir.glob("**/*"):
        if f.is_file():
            try:
                f.unlink()
                deleted += 1
            except Exception as e:
                errors.append(str(e))

    if errors:
        return deleted, f"Partial purge — {len(errors)} file(s) could not be deleted."
    return deleted, ""


# ---------------------------------------------------------------------------
# Registry read / write
# ---------------------------------------------------------------------------

def get_recall_status() -> bool:
    """
    Returns True if Windows Recall is currently ENABLED (i.e. not blocked by policy).

    Logic:
      - If the registry key exists and TurnOffWindowsRecall == 1 → DISABLED (return False)
      - Otherwise (key missing or value == 0)                    → ENABLED  (return True)
    """
    if not _IS_WINDOWS:
        # Non-Windows dev environment: simulate enabled state
        return True

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            _POLICY_KEY_PATH,
            0,
            winreg.KEY_READ,
        ) as key:
            value, _ = winreg.QueryValueEx(key, _POLICY_VALUE_NAME)
            return value != 1
    except FileNotFoundError:
        # Key has never been written → Recall is in its default (enabled) state
        return True
    except Exception as e:
        logger.error(f"Registry read failed: {e}")
        return True  # Fail open: assume enabled so user knows to act


def toggle_recall(enable: bool) -> tuple[bool, str]:
    """
    Writes (or clears) the Group Policy registry DWORD that controls Recall.

    enable=True  → sets TurnOffWindowsRecall = 0  (Recall allowed)
    enable=False → sets TurnOffWindowsRecall = 1  (Recall blocked)

    Returns (success: bool, message: str).

    Requires elevated (Administrator) privileges to write to HKLM.
    """
    if not _IS_WINDOWS:
        action = "enabled" if enable else "disabled"
        logger.info(f"[DEV MODE] Recall would be {action} (non-Windows platform).")
        return True, f"[DEV MODE] Recall simulated as {action}."

    if not is_admin():
        msg = (
            "Administrator privileges required to modify HKLM registry. "
            "Restart Shield Recall as Administrator."
        )
        logger.warning(msg)
        return False, msg

    try:
        # CreateKeyEx is idempotent — safe to call even if the key exists
        winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE,
            _POLICY_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            _POLICY_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            registry_value = 0 if enable else 1
            winreg.SetValueEx(
                key,
                _POLICY_VALUE_NAME,
                0,
                winreg.REG_DWORD,
                registry_value,
            )

        action = "ENABLED" if enable else "DISABLED"
        msg = (
            f"Registry updated: {_POLICY_KEY_PATH}\\{_POLICY_VALUE_NAME} = {registry_value} "
            f"({action})"
        )
        logger.info(msg)
        return True, msg

    except PermissionError:
        msg = "PermissionError: run Shield Recall as Administrator to modify this key."
        logger.error(msg)
        return False, msg
    except Exception as e:
        msg = f"Unexpected registry error: {e}"
        logger.error(msg)
        return False, msg


# ---------------------------------------------------------------------------
# Active window capture (Win32 UI Automation)
# ---------------------------------------------------------------------------

def get_active_window_info() -> dict:
    """
    Returns {'app': str, 'title': str, 'text': str} for the currently focused window.

    On Windows, uses ctypes + Win32 API to read the foreground window title.
    Full text extraction (for PII scanning) requires pywin32 / UI Automation.
    Falls back to empty strings on any error or non-Windows platform.
    """
    if not _IS_WINDOWS:
        return {"app": "devmode.exe", "title": "Development Mode", "text": ""}

    result = {"app": "", "title": "", "text": ""}
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()

        # Window title
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        result["title"] = buf.value

        # Process name
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h_proc = kernel32.OpenProcess(0x0410, False, pid.value)
        if h_proc:
            name_buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.psapi.GetModuleFileNameExW(h_proc, None, name_buf, 260)
            kernel32.CloseHandle(h_proc)
            result["app"] = Path(name_buf.value).name or "unknown.exe"

    except Exception as e:
        logger.debug(f"get_active_window_info error: {e}")

    return result
