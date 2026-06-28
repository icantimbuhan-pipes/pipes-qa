import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path("data/portal_qa.db")


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _migrate(con):
    """Add columns that may not exist in older DBs."""
    for sql in [
        "ALTER TABLE qa_answers  ADD COLUMN latency_note TEXT DEFAULT ''",
        "ALTER TABLE qa_sessions ADD COLUMN draft_text   TEXT DEFAULT ''",
    ]:
        try:
            con.execute(sql)
        except Exception:
            pass  # column already exists


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS qa_sessions (
                id             TEXT PRIMARY KEY,
                checklist_key  TEXT NOT NULL,
                checklist_name TEXT NOT NULL,
                report_type    TEXT DEFAULT 'daily',
                started_at     TEXT NOT NULL,
                finished_at    TEXT,
                slack_sent     INTEGER DEFAULT 0,
                draft_text     TEXT DEFAULT ''
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS qa_answers (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id    TEXT NOT NULL REFERENCES qa_sessions(id),
                item_idx      INTEGER NOT NULL,
                section_title TEXT NOT NULL,
                item_id       TEXT NOT NULL,
                item_text     TEXT NOT NULL,
                passed        INTEGER NOT NULL,
                note          TEXT DEFAULT '',
                latency_note  TEXT DEFAULT '',
                answered_at   TEXT NOT NULL
            )
        """)
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_qa_answers_session ON qa_answers(session_id)"
        )
        _migrate(con)


def create_session(checklist_key: str, checklist_name: str, report_type: str = "daily") -> str:
    session_id = str(uuid.uuid4())
    with _conn() as con:
        con.execute(
            "INSERT INTO qa_sessions(id,checklist_key,checklist_name,report_type,started_at) VALUES(?,?,?,?,?)",
            (session_id, checklist_key, checklist_name, report_type, datetime.now().isoformat()),
        )
    return session_id


def save_answer(
    session_id: str, item_idx: int, section_title: str,
    item_id: str, item_text: str, passed: bool, note: str,
    latency_note: str = "",
):
    with _conn() as con:
        con.execute(
            """INSERT INTO qa_answers
               (session_id,item_idx,section_title,item_id,item_text,passed,note,latency_note,answered_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (session_id, item_idx, section_title, item_id, item_text,
             int(passed), note, latency_note, datetime.now().isoformat()),
        )


def save_draft(session_id: str, draft_text: str):
    with _conn() as con:
        con.execute(
            "UPDATE qa_sessions SET draft_text=? WHERE id=?",
            (draft_text, session_id),
        )


def get_session(session_id: str) -> Optional[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM qa_sessions WHERE id=?", (session_id,)
        ).fetchone()


def get_answers(session_id: str):
    with _conn() as con:
        return con.execute(
            "SELECT * FROM qa_answers WHERE session_id=? ORDER BY item_idx",
            (session_id,),
        ).fetchall()


def list_sessions(limit: int = 20):
    with _conn() as con:
        return con.execute(
            "SELECT * FROM qa_sessions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


def finish_session(session_id: str):
    with _conn() as con:
        con.execute(
            "UPDATE qa_sessions SET finished_at=? WHERE id=?",
            (datetime.now().isoformat(), session_id),
        )


def mark_slack_sent(session_id: str):
    with _conn() as con:
        con.execute("UPDATE qa_sessions SET slack_sent=1 WHERE id=?", (session_id,))


# ── Provider Configs ───────────────────────────────────────────────────────────

def init_provider_configs():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS provider_configs (
                id           TEXT PRIMARY KEY,
                key          TEXT UNIQUE NOT NULL,
                name         TEXT NOT NULL,
                api_url      TEXT DEFAULT 'https://leads.pipes.ai/api/lead',
                api_key      TEXT DEFAULT '',
                first_name   TEXT DEFAULT '',
                last_name    TEXT DEFAULT '',
                state        TEXT DEFAULT 'FL',
                postal_code  TEXT DEFAULT '32004',
                extra_json   TEXT DEFAULT '{}',
                created_at   TEXT NOT NULL,
                updated_at   TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS qa_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL DEFAULT '',
                updated_at TEXT
            )
        """)


def save_provider_config(id: str, key: str, name: str, api_url: str,
                         api_key: str, first_name: str, last_name: str,
                         state: str, postal_code: str, extra_json: str = "{}"):
    now = datetime.now().isoformat()
    with _conn() as con:
        existing = con.execute(
            "SELECT id FROM provider_configs WHERE key=?", (key,)
        ).fetchone()
        if existing:
            con.execute(
                """UPDATE provider_configs
                   SET name=?, api_url=?, api_key=?, first_name=?, last_name=?,
                       state=?, postal_code=?, extra_json=?, updated_at=?
                   WHERE key=?""",
                (name, api_url, api_key, first_name, last_name,
                 state, postal_code, extra_json, now, key),
            )
        else:
            con.execute(
                """INSERT INTO provider_configs
                   (id, key, name, api_url, api_key, first_name, last_name,
                    state, postal_code, extra_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (id, key, name, api_url, api_key, first_name, last_name,
                 state, postal_code, extra_json, now),
            )


def get_provider_config(key: str) -> Optional[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM provider_configs WHERE key=?", (key,)
        ).fetchone()


def list_provider_configs():
    with _conn() as con:
        return con.execute(
            "SELECT * FROM provider_configs ORDER BY name"
        ).fetchall()


def delete_provider_config(key: str):
    with _conn() as con:
        con.execute("DELETE FROM provider_configs WHERE key=?", (key,))


def get_qa_setting(key: str, default: str = "") -> str:
    with _conn() as con:
        row = con.execute(
            "SELECT value FROM qa_settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default


def save_qa_settings(settings: dict):
    now = datetime.now().isoformat()
    with _conn() as con:
        for k, v in settings.items():
            con.execute(
                """INSERT INTO qa_settings(key, value, updated_at) VALUES(?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (k, v, now),
            )


def get_all_qa_settings() -> dict:
    with _conn() as con:
        rows = con.execute("SELECT key, value FROM qa_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


# ── Custom Checklists ───────────────────────────────────────────────────────────

def init_custom_checklists():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS custom_checklists (
                id               TEXT PRIMARY KEY,
                key              TEXT UNIQUE NOT NULL,
                name             TEXT NOT NULL,
                report_type      TEXT DEFAULT 'daily',
                default_provider TEXT DEFAULT 'heavy_khomp',
                sections_json    TEXT NOT NULL DEFAULT '[]',
                created_at       TEXT NOT NULL,
                updated_at       TEXT
            )
        """)


def save_custom_checklist(id: str, key: str, name: str, report_type: str,
                          default_provider: str, sections_json: str):
    now = datetime.now().isoformat()
    with _conn() as con:
        existing = con.execute(
            "SELECT id FROM custom_checklists WHERE id=?", (id,)
        ).fetchone()
        if existing:
            con.execute(
                """UPDATE custom_checklists
                   SET key=?, name=?, report_type=?, default_provider=?,
                       sections_json=?, updated_at=?
                   WHERE id=?""",
                (key, name, report_type, default_provider, sections_json, now, id),
            )
        else:
            con.execute(
                """INSERT INTO custom_checklists
                   (id, key, name, report_type, default_provider, sections_json, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (id, key, name, report_type, default_provider, sections_json, now),
            )


def get_custom_checklist(checklist_id: str) -> Optional[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM custom_checklists WHERE id=?", (checklist_id,)
        ).fetchone()


def get_custom_checklist_by_key(key: str) -> Optional[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM custom_checklists WHERE key=?", (key,)
        ).fetchone()


def list_custom_checklists():
    with _conn() as con:
        return con.execute(
            "SELECT * FROM custom_checklists ORDER BY created_at DESC"
        ).fetchall()


def delete_custom_checklist(checklist_id: str):
    with _conn() as con:
        con.execute("DELETE FROM custom_checklists WHERE id=?", (checklist_id,))


# ── QA Test Runs ──────────────────────────────────────────────────────────────

def init_qa_test_runs():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS qa_test_runs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                feature_name TEXT NOT NULL DEFAULT '',
                result       TEXT NOT NULL DEFAULT 'UNKNOWN',
                findings     TEXT NOT NULL DEFAULT '',
                backend      TEXT NOT NULL DEFAULT '',
                created_at   TEXT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_qa_runs_created ON qa_test_runs(created_at)")


def save_qa_run(feature_name: str, result: str, findings: str, backend: str) -> int:
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO qa_test_runs(feature_name, result, findings, backend, created_at)
               VALUES(?,?,?,?,?)""",
            (feature_name, result, findings, backend, datetime.now().isoformat()),
        )
        return cur.lastrowid


def list_qa_runs(limit: int = 200):
    with _conn() as con:
        return con.execute(
            """SELECT id, feature_name, result, backend, created_at
               FROM qa_test_runs ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()


def get_qa_run(run_id: int) -> Optional[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM qa_test_runs WHERE id=?", (run_id,)
        ).fetchone()


def delete_qa_run(run_id: int):
    with _conn() as con:
        con.execute("DELETE FROM qa_test_runs WHERE id=?", (run_id,))


# ── DNC Log ────────────────────────────────────────────────────────────────────

def init_dnc_log():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS dnc_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                phone         TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'pending',
                source        TEXT NOT NULL DEFAULT 'manual',
                slack_channel TEXT DEFAULT '',
                created_at    TEXT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_dnc_phone ON dnc_log(phone)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_dnc_created ON dnc_log(created_at)")


def log_dnc(phone: str, status: str, source: str = "manual", slack_channel: str = "") -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO dnc_log(phone, status, source, slack_channel, created_at) VALUES(?,?,?,?,?)",
            (phone, status, source, slack_channel, datetime.now().isoformat()),
        )


def list_dnc_log(limit: int = 100):
    with _conn() as con:
        return con.execute(
            "SELECT * FROM dnc_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
