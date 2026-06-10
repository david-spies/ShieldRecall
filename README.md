![Shield Recall](docs/banner.svg)

![version](https://img.shields.io/badge/Shield_Recall-v1.0.0-3EB489?style=flat-square&labelColor=0a0c0f&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTEyIDJMNCA2djZjMCA1LjUgMy44IDEwLjcgOCAxMiA0LjItMS4zIDgtNi41IDgtMTJWNmwtOC00eiIgZmlsbD0iIzNFQjQ4OSIvPjwvc3ZnPg==&logoColor=3EB489)
![python](https://img.shields.io/badge/python-3.11%2B-3EB489?style=flat-square&labelColor=0a0c0f&logo=python&logoColor=3EB489)
![fastapi](https://img.shields.io/badge/FastAPI-0.111-3EB489?style=flat-square&labelColor=0a0c0f&logo=fastapi&logoColor=3EB489)
![license](https://img.shields.io/badge/license-MIT-3EB489?style=flat-square&labelColor=0a0c0f)
![windows 11](https://img.shields.io/badge/platform-Windows_11-e05555?style=flat-square&labelColor=0a0c0f&logo=windows&logoColor=e05555)
![zero-trust](https://img.shields.io/badge/zero--trust-enabled-3EB489?style=flat-square&labelColor=0a0c0f&logo=springsecurity&logoColor=3EB489)
![local-only](https://img.shields.io/badge/storage-local--only-3EB489?style=flat-square&labelColor=0a0c0f&logo=databricks&logoColor=3EB489)
![AES-256](https://img.shields.io/badge/encryption-AES--256_ready-3EB489?style=flat-square&labelColor=0a0c0f&logo=letsencrypt&logoColor=3EB489)
![presidio](https://img.shields.io/badge/PII_engine-Presidio_NLP-3EB489?style=flat-square&labelColor=0a0c0f&logo=microsoftazure&logoColor=3EB489)
![loopback](https://img.shields.io/badge/network-loopback_only-3EB489?style=flat-square&labelColor=0a0c0f&logo=cisco&logoColor=3EB489)
![spacy](https://img.shields.io/badge/spaCy-NER-3EB489?style=flat-square&labelColor=0a0c0f&logo=spacy&logoColor=3EB489)
![sqlite](https://img.shields.io/badge/SQLite-WAL_mode-3EB489?style=flat-square&labelColor=0a0c0f&logo=sqlite&logoColor=3EB489)
![htmx](https://img.shields.io/badge/HTMX-1.9-3EB489?style=flat-square&labelColor=0a0c0f&logo=htmx&logoColor=3EB489)
![jinja2](https://img.shields.io/badge/Jinja2-templates-3EB489?style=flat-square&labelColor=0a0c0f&logo=jinja&logoColor=3EB489)
![pyinstaller](https://img.shields.io/badge/PyInstaller-Windows_exe-3EB489?style=flat-square&labelColor=0a0c0f&logo=python&logoColor=3EB489)
![pytest](https://img.shields.io/badge/tests-pytest-3EB489?style=flat-square&labelColor=0a0c0f&logo=pytest&logoColor=3EB489)
![ruff](https://img.shields.io/badge/linter-ruff-3EB489?style=flat-square&labelColor=0a0c0f&logo=ruff&logoColor=3EB489)
![mypy](https://img.shields.io/badge/types-mypy-3EB489?style=flat-square&labelColor=0a0c0f&logo=python&logoColor=3EB489)
![code style](https://img.shields.io/badge/code_style-ruff_format-3EB489?style=flat-square&labelColor=0a0c0f)
![admin](https://img.shields.io/badge/requires-admin_on_Windows-d4a020?style=flat-square&labelColor=0a0c0f&logo=windowsterminal&logoColor=d4a020)
![recall shielded](https://img.shields.io/badge/Windows_Recall-SHIELDED-3EB489?style=flat-square&labelColor=0a0c0f&logo=windowsdefender&logoColor=3EB489)
![snapshots](https://img.shields.io/badge/snapshots-monitored-3EB489?style=flat-square&labelColor=0a0c0f&logo=amazonclouddirectory&logoColor=3EB489)
![kill switch](https://img.shields.io/badge/kill_switch-registry_level-e05555?style=flat-square&labelColor=0a0c0f&logo=windowsdefender&logoColor=e05555)
# 🛡️ Shield Recall

**Enterprise privacy engine for Windows 11 Recall.**

Shield Recall monitors Windows 11's Recall feature in real time, intercepts and redacts sensitive data before it is permanently indexed, gives you a live count of snapshots on disk, and puts a one-click kill switch over the entire Recall subsystem via the Windows Group Policy registry.

---

## Contents

1. [What Shield Recall does](#what-shield-recall-does)
2. [Architecture overview](#architecture-overview)
3. [Quick start](#quick-start)
4. [Running in production](#running-in-production)
5. [Dashboard reference](#dashboard-reference)
6. [Interpreting the metrics](#interpreting-the-metrics)
7. [Scenario playbook](#scenario-playbook)
8. [Configuration reference](#configuration-reference)
9. [Project structure](#project-structure)
10. [Testing](#testing)
11. [Security notes](#security-notes)
12. [Packaging as an executable](#packaging-as-an-executable)

---

## What Shield Recall does

Windows 11 Recall continuously screenshots your desktop and uses on-device AI to make that history searchable. Everything visible on screen — passwords typed into a browser, financial documents, private messages, medical records — can end up permanently stored in a local database that any process running as you can query.

Shield Recall sits between the OS and that database as a **zero-trust middleware layer**:

| Layer | What it stops |
|---|---|
| **Microsoft Presidio NER** | SSNs, credit cards, email addresses, phone numbers, person names |
| **Credential regex** | `password=`, `api_key:`, `STRIPE_SECRET=`, `Bearer …`, etc. |
| **Shannon entropy scanner** | High-randomness strings (raw tokens, hex secrets, base64 blobs) |
| **Kill switch** | Writes the official Group Policy registry DWORD that disables Recall entirely |

All processing is **local-only**. No data leaves your machine.

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────┐
│                Windows desktop activity stream              │
└───────────────────────────┬─────────────────────────────────┘
                            │  Win32 / UI Automation
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           Capture worker  (background asyncio task)         │
│   get_active_window_info()  →  raw text per window frame    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              PrivacyEngine.sanitize_text()                  │
│  1. Presidio NER          2. Credential regex               │
│  3. Entropy scan     →    clean_text + RedactionSummary     │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│         EncryptedStorage (SQLite WAL, AES-256 ready)        │
│  secure_timeline table    activity_log table                │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│            FastAPI  (127.0.0.1 loopback only)               │
│  HTMX dashboard   REST JSON API   HTMX partials             │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick start

### Prerequisites

- Python 3.11+
- Windows 11 (for live Recall integration; the app runs in dev mode on macOS/Linux)
- Administrator rights (only required for the kill switch; the dashboard works without them)

### 1 — Clone and install

```bash
git clone https://github.com/your-org/shield-recall.git
cd shield-recall
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

### 2 — Download the spaCy language model

Presidio requires a spaCy model for named-entity recognition:

```bash
python -m spacy download en_core_web_lg
```

### 3 — Configure

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

Edit `.env` and set a strong 32-character `SHIELD_RECALL_KEY`. Everything else can stay at its default for a first run.

### 4 — Run

```bash
python main.py
```

Open **http://127.0.0.1:8000** in your browser.

> **To unlock the kill switch**, run the terminal as Administrator before launching:
> ```
> # In an elevated PowerShell:
> python main.py
> ```

---

## Running in production

### Option A — uvicorn directly (recommended for long-running use)

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

Single worker only — the in-memory activity feed is not shared across processes.

### Option B — Windows Task Scheduler (auto-start on login)

1. Open Task Scheduler → Create Basic Task.
2. Trigger: **At log on**.
3. Action: Start a program → `pythonw.exe` with arguments `main.py`, start in the project directory.
4. Check **Run with highest privileges** to enable the kill switch.

### Option C — Compile to a single .exe

```bash
pip install pyinstaller
pyinstaller --uac-admin --onefile --name ShieldRecall main.py
```

`--uac-admin` embeds a UAC elevation manifest so Windows will always prompt for admin rights on launch, unlocking registry control.

---

## Dashboard reference

### Header badges

| Badge | Meaning |
|---|---|
| **Admin elevated** (green) | Process has admin rights; kill switch is functional |
| **User mode — registry locked** (amber) | No admin rights; kill switch toggle will return an error |
| **Recall active** (red pulse) | Recall is currently enabled at the OS level |
| **Recall shielded** (green pulse) | The Group Policy key has been set; Recall is disabled |

### Stat cards

| Card | What it shows |
|---|---|
| **Recall snapshots on disk** | Live file count in `%USERPROFILE%\AppData\Local\CoreAIPlatform\CaptureRegions`. Auto-refreshes every 2 seconds via HTMX polling. |
| **PII items redacted** | Cumulative count of PII tokens removed by the engine since the database was last wiped. |
| **High-risk captures** | Capture events with a risk score ≥ 0.7 — these had multiple high-severity items (SSNs, credit cards, API keys) in a single frame. |

### Kill switch section

The toggle and the **Kill Recall now** button do the same thing: they POST to `/api/recall/toggle`, which reads the current registry value, flips it, and writes it back. The section replaces itself in-place via HTMX `hx-swap="outerHTML"` so the entire toggle UI reflects the new state without a page reload.

**Purge snapshots** deletes all `.bin`/`.dat` files from the snapshot directory. It does not require admin rights (the files are in your user profile). A confirmation dialog is shown before any deletion.

### Audit query store

The search form sends requests to `/api/search` on every keystroke (debounced 250 ms). Results show:

- The capturing application and window title
- The risk score badge (colour-coded low / medium / high)
- The sanitized text with `[REDACTED_*]` tokens highlighted in red

You can filter by application name and minimum risk level simultaneously.

---

## Interpreting the metrics

### Snapshot count

| Count | Interpretation |
|---|---|
| **0** | Recall has never been activated on this machine, or snapshots have been purged |
| **1–80** (green) | Normal operating range for a Recall-enabled system |
| **81–150** (amber) | Elevated — Recall has been running for an extended session; consider purging |
| **150+** (red) | High accumulation — significant visual history on disk; purge and/or disable Recall |

The count updates every 2 seconds. If Recall is disabled via the kill switch, the count will stop growing but existing files remain until you click **Purge snapshots**.

### Risk score

Each capture event is scored 0.0–1.0 based on what was found:

| Score range | Colour | Meaning |
|---|---|---|
| 0.0 | — | Nothing detected; clean capture |
| 0.01–0.29 | Green | Low-risk PII (person names only) |
| 0.30–0.69 | Amber | Medium risk (emails, phone numbers) |
| 0.70–1.0 | Red | High risk — SSNs, credit cards, API keys, or multiple categories |

A high-risk event means Shield Recall did its job: it caught something serious and redacted it before it hit the database in cleartext. However, a persistent stream of high-risk events from the same application suggests that application is handling sensitive data frequently and warrants closer review.

### Shannon entropy

Entropy measures randomness in a string (bits per character).

| Entropy value | Likely content |
|---|---|
| < 3.5 | Normal English prose |
| 3.5–4.0 | Code, structured data, identifiers |
| 4.0–4.5 | Borderline — may be a short credential |
| > 4.5 | Very likely a password, token, or key |

The default threshold of 4.0 balances sensitivity against false positives. Lower it to catch more; raise it if you see normal identifiers being incorrectly redacted.

### Activity trace

The activity feed is colour-coded by severity:

| Colour | Level | Meaning |
|---|---|---|
| Green | INFO | Normal operation (engine start, routine scans) |
| Amber | WARNING | PII found and redacted, or partial purge errors |
| Red | CRITICAL | Kill switch toggle failed (usually missing admin rights) |

---

## Scenario playbook

### Scenario 1 — You notice a sudden spike in snapshot count

**Symptom:** Snapshot counter jumps from ~40 to 200+ within minutes.
**Cause:** Recall was running during an intensive screen session (video call, document editing, browser research).
**Response:**
1. Click **Purge snapshots** to delete the existing files.
2. If you don't want Recall accumulating further: click **Kill Recall now** (requires admin).
3. Check the audit query store for any high-risk captures during that period by filtering `min_risk ≥ 0.7`.

---

### Scenario 2 — High-risk captures appearing from a password manager

**Symptom:** Multiple `risk 0.90` entries in the timeline attributed to `1Password.exe` or `KeePass.exe`.
**Cause:** Recall is screenshotting the unlocked vault view. Shield Recall is catching and redacting the credentials before they are stored — but the raw screenshot may still exist on disk.
**Response:**
1. Purge snapshots immediately.
2. Disable Recall entirely — password managers should never be captured.
3. Consider adding your password manager to Windows' exclude-from-Recall list (Settings → Privacy & Security → Recall & Snapshots → Excluded apps).

---

### Scenario 3 — Kill switch button is greyed out / returns an error

**Symptom:** Clicking **Kill Recall now** shows a red error banner: *"Administrator privileges required."*
**Cause:** Shield Recall was launched without elevated rights. The registry path `HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsAI` requires admin to write.
**Response:**
1. Close the current instance.
2. Right-click your terminal / IDE → **Run as Administrator**.
3. Relaunch `python main.py`.
4. The header badge will now show **Admin elevated** (green).

---

### Scenario 4 — False positives: normal text being redacted

**Symptom:** Audit results show `[REDACTED_HIGH_ENTROPY_SECRET]` replacing what you know is a normal product code or identifier.
**Cause:** The entropy threshold is too low for your use case.
**Response:**
1. Open `.env` and raise `ENTROPY_THRESHOLD` from `4.0` to `4.5` or `5.0`.
2. Restart the app (`python main.py`).
3. Re-run a test to confirm the identifier now passes through.

---

### Scenario 5 — Database is growing large

**Symptom:** `secure_recall.db` is several hundred MB.
**Cause:** The timeline has accumulated thousands of capture events over days/weeks.
**Response:**
1. In the **Danger zone** section, click **Wipe local timeline DB**.
2. This only removes the sanitized text log — it does not affect the Recall snapshot directory.
3. Alternatively, use the REST API: `curl -X DELETE http://127.0.0.1:8000/api/timeline`

---

### Scenario 6 — You want to verify the kill switch actually worked

**Symptom:** Unsure whether the registry key was successfully written.
**Response:**
1. Open an elevated PowerShell and run:
   ```powershell
   Get-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsAI" -Name TurnOffWindowsRecall
   ```
2. Expected output when shielded: `TurnOffWindowsRecall : 1`
3. Alternatively, hit the JSON health endpoint:
   ```bash
   curl http://127.0.0.1:8000/health
   ```
   Look for `"recall_active": false`.

---

### Scenario 7 — Deploying on a machine without internet access

**Symptom:** `pip install` fails or spaCy model download is blocked.
**Response:**
1. On an internet-connected machine: `pip download -r requirements.txt -d ./packages`
2. Copy the `packages/` directory to the air-gapped machine.
3. Install offline: `pip install --no-index --find-links=./packages -r requirements.txt`
4. For the spaCy model, download the `.whl` from https://github.com/explosion/spacy-models/releases and install it directly: `pip install en_core_web_lg-*.whl`

---

## Configuration reference

All settings can be set in `.env` or as environment variables. Environment variables take precedence.

| Variable | Default | Description |
|---|---|---|
| `SHIELD_RECALL_KEY` | `ShieldRecall_DefaultKey_32Bytes!!` | 32-byte AES encryption key. **Change this in production.** |
| `APP_NAME` | `ShieldRecall` | Display name in the dashboard header |
| `DEBUG` | `false` | Enables FastAPI debug mode and verbose logging |
| `LOCAL_DB_PATH` | `secure_recall.db` | Path to the SQLite database file |
| `HOST` | `127.0.0.1` | Bind address. Do not change to `0.0.0.0` — this would expose the dashboard on the network |
| `PORT` | `8000` | HTTP port |
| `CAPTURE_INTERVAL_SECONDS` | `5` | Seconds between capture worker iterations |
| `ENTROPY_THRESHOLD` | `4.0` | Shannon entropy floor for secret detection. Range: 3.5–5.5 |
| `MAX_ACTIVITY_LOG` | `100` | Maximum in-memory activity entries |

---

## Project structure

```
shield-recall/
├── main.py               # FastAPI app, routes, capture worker
├── config.py             # Pydantic settings (reads .env)
├── pii_engine.py         # Presidio + regex + entropy redaction pipeline
├── database.py           # SQLite encrypted storage layer
├── os_control.py         # Windows registry, snapshot counting, Win32 helpers
├── requirements.txt
├── .env.example          # Copy to .env and configure
├── .gitignore
├── templates/
│   └── index.html        # Jinja2 + HTMX dashboard template
├── static/
│   ├── css/
│   │   └── dashboard.css
│   └── js/
│       └── dashboard.js
└── tests/
    ├── test_pii_engine.py
    └── test_database.py
```

---

## Testing

```bash
# Install pytest (already in dev dependencies)
pip install pytest

# Run all tests
pytest tests/ -v

# Run only PII engine tests
pytest tests/test_pii_engine.py -v

# Run with coverage
pip install pytest-cov
pytest tests/ --cov=. --cov-report=term-missing
```

Tests are intentionally split into two files:
- `test_pii_engine.py` — pure Python, no OS dependencies, fast
- `test_database.py` — uses `tmp_path` fixture for isolated SQLite files, no cleanup needed

---

## Security notes

**Encryption key management**
The default key in `.env.example` is a placeholder. In production, derive the key from Windows Hello / DPAPI so it is tied to the device and the authenticated user, not to a file on disk:

```python
import ctypes, ctypes.wintypes

def get_dpapi_key(label: bytes = b"ShieldRecall") -> bytes:
    """Encrypt the key blob with DPAPI so it is only usable by the current user on this machine."""
    # Use CryptProtectData / CryptUnprotectData via ctypes
    ...
```

**Loopback-only binding**
The server binds to `127.0.0.1` by default. Never change `HOST` to `0.0.0.0` — doing so would expose the kill switch and the full redacted audit history to every device on your network.

**SQLCipher at-rest encryption**
The database schema is ready for SQLCipher. Uncomment the `pysqlcipher3` line in `requirements.txt`, compile it against a local SQLCipher build, and replace the `sqlite3` import in `database.py` with `from pysqlcipher3 import dbapi2 as sqlite3`. The `PRAGMA key=` call should use the `ENCRYPTION_KEY` from settings.

**Admin privilege scope**
Shield Recall only requests elevated privileges for two operations:
1. Writing the `TurnOffWindowsRecall` registry DWORD under `HKLM`
2. UAC prompt at launch when compiled with `--uac-admin`

All other operations (reading the snapshot directory, querying the DB, serving the dashboard) run at standard user privilege level.

---

## Packaging as an executable

```bash
pip install pyinstaller
pyinstaller \
  --uac-admin \
  --onefile \
  --name ShieldRecall \
  --add-data "templates;templates" \
  --add-data "static;static" \
  main.py
```

The resulting `dist/ShieldRecall.exe` is fully self-contained. Copy it alongside a `.env` file to any Windows 11 machine and run it. No Python installation required.

---

## License

MIT — see `LICENSE` for details.
