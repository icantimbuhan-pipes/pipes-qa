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
                slack_sent     INTEGER DEFAULT 0
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
                answered_at   TEXT NOT NULL
            )
        """)
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_qa_answers_session ON qa_answers(session_id)"
        )


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
    item_id: str, item_text: str, passed: bool, note: str
):
    with _conn() as con:
        con.execute(
            """INSERT INTO qa_answers
               (session_id,item_idx,section_title,item_id,item_text,passed,note,answered_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (session_id, item_idx, section_title, item_id, item_text,
             int(passed), note, datetime.now().isoformat()),
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
