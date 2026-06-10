"""
main.py — ShieldRecall FastAPI application.

Startup sequence
----------------
1. Load config / validate encryption key
2. Initialise EncryptedStorage (creates DB + schema if absent)
3. Warm up PrivacyEngine (lazy Presidio init happens on first text chunk)
4. Spin up the background capture worker coroutine
5. Serve the HTMX dashboard on http://127.0.0.1:8000

Endpoints
---------
GET  /                       — Dashboard (Jinja2 + HTMX)
GET  /api/telemetry           — JSON snapshot of all live metrics
GET  /api/telemetry/counter   — HTMX partial: live snapshot counter
GET  /api/telemetry/activity  — HTMX partial: recent activity feed
POST /api/recall/toggle       — Enable / disable Windows Recall via registry
POST /api/recall/purge        — Delete all snapshot files on disk
POST /api/search              — HTMX partial: search sanitized timeline
GET  /api/stats               — JSON aggregate stats (for future API clients)
DELETE /api/timeline          — Wipe the local encrypted timeline DB
GET  /health                  — Health check (used by watchdog / systemd)
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import settings
from database import EncryptedStorage
from os_control import (
    get_active_window_info,
    get_recall_status,
    get_snapshot_count,
    get_snapshot_dir_size_mb,
    is_admin,
    purge_snapshots,
    toggle_recall,
)
from pii_engine import PrivacyEngine

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("shield_recall")

# ---------------------------------------------------------------------------
# Global singletons
# ---------------------------------------------------------------------------
privacy_engine = PrivacyEngine(entropy_threshold=settings.ENTROPY_THRESHOLD)
db = EncryptedStorage(settings.LOCAL_DB_PATH, encryption_key=settings.ENCRYPTION_KEY)

# In-memory rolling activity feed (augments DB log for live UI updates)
_activity_feed: list[dict] = []


def _push_activity(message: str, level: str = "INFO", category: str = "SYSTEM"):
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "level": level,
        "category": category,
        "message": message,
    }
    _activity_feed.insert(0, entry)
    if len(_activity_feed) > settings.MAX_ACTIVITY_LOG:
        _activity_feed.pop()
    db.log_activity(message, level=level, category=category)


# ---------------------------------------------------------------------------
# Background capture worker
# ---------------------------------------------------------------------------
async def _capture_worker():
    """
    Periodic worker that:
      1. Reads the active window text stream via Win32 UI Automation
      2. Runs it through the PII engine
      3. Persists the sanitized entry to the encrypted local DB
      4. Emits activity log events for any redactions

    In production on Windows, get_active_window_info() returns live data.
    On non-Windows platforms it returns a dev-mode stub so the pipeline
    can be exercised end-to-end without a Windows host.
    """
    logger.info("Capture worker started.")
    _push_activity("ShieldRecall capture engine online.", category="SYSTEM")

    while True:
        try:
            window = get_active_window_info()
            raw_text = window.get("text", "")

            # Only process windows with non-empty text content
            if raw_text.strip():
                clean_text, summary = privacy_engine.sanitize_text(raw_text)

                db.insert_entry(
                    app_name=window.get("app", "unknown.exe"),
                    window_title=window.get("title", ""),
                    content=clean_text,
                    risk_score=summary.risk_score,
                    pii_count=summary.total,
                )

                if summary.total > 0:
                    _push_activity(
                        f"{summary.total} PII item(s) redacted in "
                        f"{window.get('app', 'unknown')} "
                        f"[risk={summary.risk_score:.2f}]",
                        level="WARNING" if summary.risk_score >= 0.5 else "INFO",
                        category="REDACTION",
                    )
                    logger.info(
                        "Redacted %d PII items from %s (risk %.2f)",
                        summary.total,
                        window.get("app"),
                        summary.risk_score,
                    )

            # Log snapshot count change
            count = get_snapshot_count()
            if count > 0:
                _push_activity(
                    f"Snapshot directory: {count} file(s) on disk.",
                    category="SNAPSHOT",
                )

        except Exception as exc:
            logger.error("Capture worker error: %s", exc, exc_info=True)

        await asyncio.sleep(settings.CAPTURE_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(_capture_worker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Helper: build template context
# ---------------------------------------------------------------------------
def _base_context(request: Request) -> dict:
    return {
        "request": request,
        "app_name": settings.APP_NAME,
        "is_admin": is_admin(),
        "recall_active": get_recall_status(),
        "snapshot_count": get_snapshot_count(),
        "snapshot_size_mb": get_snapshot_dir_size_mb(),
        "stats": db.get_timeline_stats(),
    }


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    ctx = _base_context(request)
    ctx["activity"] = _activity_feed[:20]
    return templates.TemplateResponse("index.html", ctx)


# ---------------------------------------------------------------------------
# Routes — Telemetry (HTMX polled partials)
# ---------------------------------------------------------------------------
@app.get("/api/telemetry", response_class=JSONResponse)
async def telemetry_json():
    """Full JSON snapshot of live metrics — useful for external monitoring."""
    count = get_snapshot_count()
    return {
        "snapshot_count": count,
        "snapshot_size_mb": get_snapshot_dir_size_mb(),
        "recall_active": get_recall_status(),
        "is_admin": is_admin(),
        "stats": db.get_timeline_stats(),
        "activity": _activity_feed[:10],
    }


@app.get("/api/telemetry/counter", response_class=HTMLResponse)
async def telemetry_counter():
    """
    HTMX partial — returns only the snapshot count span.
    Polled by the dashboard every 2 seconds via hx-trigger="every 2s".
    """
    count = get_snapshot_count()
    level_class = "val-red" if count > 150 else ("val-amber" if count > 80 else "val-teal")
    return HTMLResponse(
        f'<span class="snap-counter {level_class}" '
        f'id="snap-count" aria-live="polite">{count}</span>'
    )


@app.get("/api/telemetry/activity", response_class=HTMLResponse)
async def telemetry_activity():
    """HTMX partial — returns the recent activity list."""
    items = _activity_feed[:15]
    if not items:
        return HTMLResponse(
            '<li class="act-empty">No activity recorded yet.</li>'
        )

    color_map = {
        "CRITICAL": "#e05555",
        "WARNING":  "#d4a020",
        "INFO":     "#3EB489",
    }

    html = ""
    for item in items:
        color = color_map.get(item["level"], "#3EB489")
        html += (
            f'<li>'
            f'<span class="act-dot" style="background:{color}" aria-hidden="true"></span>'
            f'<span class="act-text">{item["message"]}</span>'
            f'<span class="act-time">{item["ts"]}</span>'
            f'</li>'
        )
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Routes — Recall Control
# ---------------------------------------------------------------------------
@app.post("/api/recall/toggle", response_class=HTMLResponse)
async def recall_toggle():
    """
    Flips the Windows Recall Group Policy registry key.
    Returns an HTMX partial that replaces the toggle section in-place.
    Requires admin privileges; returns a 403 error partial if not elevated.
    """
    current_status = get_recall_status()
    target_enable = not current_status

    success, message = toggle_recall(enable=target_enable)

    if not success:
        _push_activity(f"Toggle failed: {message}", level="CRITICAL", category="TOGGLE")
        return HTMLResponse(
            content=f"""
            <div class="error-banner" role="alert">
                <i class="ti ti-alert-triangle" aria-hidden="true"></i>
                {message}
            </div>
            """,
            status_code=403,
        )

    new_status = get_recall_status()
    action_label = "ENABLED" if new_status else "DISABLED &amp; SHIELDED"
    btn_class = "kill-btn active" if new_status else "kill-btn inactive"
    track_class = "toggle-track red-on" if new_status else "toggle-track"
    label_class = "toggle-label red-on" if new_status else "toggle-label on"
    label_text = "ENABLED" if new_status else "DISABLED"
    btn_icon = "ti-shield-x" if new_status else "ti-shield-check"
    btn_text = "Kill Recall now" if new_status else "Recall disabled"

    log_level = "WARNING" if new_status else "INFO"
    _push_activity(message, level=log_level, category="TOGGLE")

    return HTMLResponse(content=f"""
        <div class="sr-section" id="policy-controller">
            <div class="sr-section-title">
                <i class="ti ti-power" aria-hidden="true"></i> Recall kill switch
            </div>
            <div class="toggle-row">
                <div class="toggle-info">
                    <h3>Windows Recall OS flag</h3>
                    <p>Group Policy registry control</p>
                </div>
                <div style="display:flex;flex-direction:column;align-items:center;gap:2px">
                    <div class="{track_class}" id="recall-toggle"
                         hx-post="/api/recall/toggle"
                         hx-target="#policy-controller"
                         hx-swap="outerHTML"
                         role="switch" aria-checked="{str(new_status).lower()}"
                         aria-label="Windows Recall toggle" tabindex="0">
                        <div class="toggle-thumb"></div>
                    </div>
                    <div class="{label_class}" id="toggle-label">{label_text}</div>
                </div>
            </div>
            <div class="admin-note" id="kill-status">
                {message}
            </div>
            <div style="margin-top:10px;display:flex;gap:8px">
                <button class="{btn_class}"
                        hx-post="/api/recall/toggle"
                        hx-target="#policy-controller"
                        hx-swap="outerHTML"
                        aria-label="Toggle Recall kill switch">
                    <i class="ti {btn_icon}" aria-hidden="true"></i> {btn_text}
                </button>
            </div>
        </div>
    """)


@app.post("/api/recall/purge", response_class=JSONResponse)
async def recall_purge():
    """Delete all snapshot files from the Recall directory on disk."""
    deleted, error = purge_snapshots()
    msg = (
        f"Purged {deleted} snapshot file(s)."
        if not error
        else f"Partial purge: {deleted} deleted. {error}"
    )
    level = "WARNING" if error else "INFO"
    _push_activity(msg, level=level, category="SNAPSHOT")
    return {"deleted": deleted, "error": error, "message": msg}


# ---------------------------------------------------------------------------
# Routes — Audit Search
# ---------------------------------------------------------------------------
@app.post("/api/search", response_class=HTMLResponse)
async def search_timeline(
    query: str = Form(""),
    app_filter: str = Form(""),
    min_risk: float = Form(0.0),
):
    """
    HTMX partial — returns sanitized timeline rows matching the query.
    Triggered on keyup (debounced 200 ms) and form submit.
    """
    results = db.query_timeline(
        keyword=query,
        app_filter=app_filter,
        min_risk=min_risk,
        limit=50,
    )

    if not results:
        return HTMLResponse(
            '<p class="empty-state">No matching records found in the secure audit store.</p>'
        )

    html = "<ul class='result-list' aria-label='Search results'>"
    for row in results:
        risk_class = (
            "risk-high" if row.risk_score >= 0.7
            else "risk-med" if row.risk_score >= 0.3
            else "risk-low"
        )
        # Highlight [REDACTED_*] tokens in the displayed text
        display_text = row.sanitized_content
        import re
        display_text = re.sub(
            r"\[REDACTED[^\]]*\]",
            lambda m: f'<span class="redacted">{m.group(0)}</span>',
            display_text,
        )
        html += f"""
        <li class="sr-result">
            <div class="sr-result-header">
                <span class="sr-result-app">{row.application_name}</span>
                <span>{row.window_title}</span>
                <span class="risk-badge {risk_class}">risk {row.risk_score:.2f}</span>
                <span>{row.timestamp[:19].replace("T", " ")}</span>
            </div>
            <div class="sr-result-body">{display_text}</div>
        </li>
        """
    html += "</ul>"
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Routes — Stats + Maintenance
# ---------------------------------------------------------------------------
@app.get("/api/stats", response_class=JSONResponse)
async def api_stats():
    return db.get_timeline_stats()


@app.delete("/api/timeline", response_class=JSONResponse)
async def wipe_timeline():
    """Wipe all sanitized timeline entries from the local DB."""
    deleted = db.purge_timeline()
    _push_activity(f"Timeline wiped: {deleted} entries removed.", level="WARNING", category="SYSTEM")
    return {"deleted": deleted}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "recall_active": get_recall_status(),
        "snapshot_count": get_snapshot_count(),
    }


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
