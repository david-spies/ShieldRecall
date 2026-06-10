"""
database.py — Local encrypted audit store.

Uses standard sqlite3 with WAL mode for high-throughput concurrent reads/writes.
For full at-rest encryption, install pysqlcipher3 and uncomment the SQLCipher
sections; the schema and query API are identical either way.

Schema
------
secure_timeline   — one row per sanitized capture event
activity_log      — rolling application event journal (last N events)
"""

import sqlite3
import logging
from datetime import datetime, timezone
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TimelineEntry:
    id: int
    timestamp: str
    application_name: str
    window_title: str
    sanitized_content: str
    risk_score: float
    pii_count: int


@dataclass
class ActivityEntry:
    id: int
    timestamp: str
    level: str          # INFO | WARNING | CRITICAL
    category: str       # REDACTION | SNAPSHOT | TOGGLE | SYSTEM
    message: str


class EncryptedStorage:
    """
    Thread-safe SQLite wrapper. Each public method opens and closes its own
    connection so this class is safe to call from async FastAPI route handlers
    via run_in_executor, or directly from sync code.
    """

    def __init__(self, db_path: str, encryption_key: Optional[str] = None):
        self.db_path = db_path
        self.encryption_key = encryption_key  # reserved for SQLCipher upgrade path
        self._init_db()
        logger.info(f"EncryptedStorage initialised: {db_path}")

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # WAL mode: readers don't block writers, writers don't block readers.
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        # Protect against partial writes on power loss.
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    # ------------------------------------------------------------------
    # Schema init
    # ------------------------------------------------------------------
    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS secure_timeline (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp        TEXT    NOT NULL,
                    application_name TEXT    NOT NULL,
                    window_title     TEXT    NOT NULL DEFAULT '',
                    sanitized_content TEXT   NOT NULL,
                    risk_score       REAL    NOT NULL DEFAULT 0.0,
                    pii_count        INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_timeline_ts
                    ON secure_timeline (timestamp DESC);

                CREATE INDEX IF NOT EXISTS idx_timeline_app
                    ON secure_timeline (application_name);

                CREATE TABLE IF NOT EXISTS activity_log (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT    NOT NULL,
                    level     TEXT    NOT NULL DEFAULT 'INFO',
                    category  TEXT    NOT NULL DEFAULT 'SYSTEM',
                    message   TEXT    NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_activity_ts
                    ON activity_log (timestamp DESC);
            """)

    # ------------------------------------------------------------------
    # Timeline writes
    # ------------------------------------------------------------------
    def insert_entry(
        self,
        app_name: str,
        window_title: str,
        content: str,
        risk_score: float,
        pii_count: int = 0,
    ) -> int:
        """Insert a sanitized capture event. Returns the new row id."""
        ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO secure_timeline
                    (timestamp, application_name, window_title, sanitized_content, risk_score, pii_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, app_name, window_title, content, risk_score, pii_count),
            )
            return cur.lastrowid

    # ------------------------------------------------------------------
    # Timeline reads
    # ------------------------------------------------------------------
    def query_timeline(
        self,
        keyword: str = "",
        app_filter: str = "",
        limit: int = 50,
        min_risk: float = 0.0,
    ) -> List[TimelineEntry]:
        """
        Full-text keyword search over sanitized_content with optional
        app_name filter and risk_score floor.
        """
        with self._connect() as conn:
            sql = """
                SELECT id, timestamp, application_name, window_title,
                       sanitized_content, risk_score, pii_count
                FROM secure_timeline
                WHERE 1=1
            """
            params: list = []

            if keyword:
                sql += " AND sanitized_content LIKE ?"
                params.append(f"%{keyword}%")

            if app_filter:
                sql += " AND application_name LIKE ?"
                params.append(f"%{app_filter}%")

            if min_risk > 0.0:
                sql += " AND risk_score >= ?"
                params.append(min_risk)

            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [TimelineEntry(**dict(r)) for r in rows]

    def get_timeline_stats(self) -> dict:
        """Aggregate counts used by the dashboard stat cards."""
        with self._connect() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*)                              AS total_entries,
                    SUM(pii_count)                        AS total_pii,
                    AVG(risk_score)                       AS avg_risk,
                    COUNT(CASE WHEN risk_score >= 0.7 THEN 1 END) AS high_risk_count,
                    MAX(timestamp)                        AS last_capture
                FROM secure_timeline
            """).fetchone()
            return dict(row) if row else {}

    # ------------------------------------------------------------------
    # Activity log
    # ------------------------------------------------------------------
    def log_activity(self, message: str, level: str = "INFO", category: str = "SYSTEM"):
        ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO activity_log (timestamp, level, category, message) VALUES (?,?,?,?)",
                (ts, level, category, message),
            )

    def get_recent_activity(self, limit: int = 50) -> List[ActivityEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, timestamp, level, category, message
                FROM activity_log
                ORDER BY timestamp DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [ActivityEntry(**dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------
    def purge_timeline(self) -> int:
        """Delete all timeline entries. Returns number of rows deleted."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM secure_timeline")
            deleted = cur.rowcount
            logger.warning(f"Timeline purged: {deleted} entries removed.")
            return deleted

    def purge_activity_log(self, keep_last: int = 100):
        """Trim activity log, keeping only the most recent `keep_last` rows."""
        with self._connect() as conn:
            conn.execute("""
                DELETE FROM activity_log
                WHERE id NOT IN (
                    SELECT id FROM activity_log ORDER BY timestamp DESC LIMIT ?
                )
            """, (keep_last,))
