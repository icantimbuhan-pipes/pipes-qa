import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent / "data" / "sms_commio.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS commio_records (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                created              TEXT,
                from_did             TEXT,
                to_did               TEXT,
                msg_count            TEXT,
                delivery_status_code TEXT,
                status_description   TEXT,
                campaign_id          TEXT,
                carrier              TEXT,
                direction            TEXT,
                batch_id             TEXT,
                imported_at          TEXT,
                company_name         TEXT,
                report_date          TEXT    -- YYYY-MM-DD, set by user on upload
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_com_company_date
            ON commio_records(company_name, report_date)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_com_report_date
            ON commio_records(report_date)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_com_status_code
            ON commio_records(delivery_status_code)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_com_campaign
            ON commio_records(campaign_id)
        """)
        conn.commit()


# ── Shared WHERE builder ──────────────────────────────────────────────────────

def _date_clause(
    report_date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    month: Optional[str] = None,
) -> tuple[str, list]:
    if report_date:
        return "AND report_date = ?", [report_date]
    if date_from and date_to:
        return "AND report_date BETWEEN ? AND ?", [date_from, date_to]
    if month:
        return "AND report_date LIKE ?", [f"{month}-%"]
    return "", []


# ── Read helpers ──────────────────────────────────────────────────────────────

def get_available_dates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT report_date, COUNT(*) AS record_count
          FROM commio_records
         WHERE report_date IS NOT NULL
         GROUP BY report_date
         ORDER BY report_date DESC
    """).fetchall()


def get_companies(conn: sqlite3.Connection, **kw) -> list[sqlite3.Row]:
    clause, params = _date_clause(**kw)
    return conn.execute(f"""
        SELECT
            company_name,
            COUNT(*)                                                                   AS total,
            SUM(CASE WHEN delivery_status_code = '200' THEN 1 ELSE 0 END)             AS delivered,
            SUM(CASE WHEN delivery_status_code != '200' THEN 1 ELSE 0 END)            AS failed,
            MIN(created)                                                               AS first_ts,
            MAX(created)                                                               AS last_ts
        FROM commio_records
        WHERE company_name IS NOT NULL AND company_name != '' {clause}
        GROUP BY company_name
        ORDER BY company_name
    """, params).fetchall()


def get_company_stats(
    conn: sqlite3.Connection,
    company_name: str,
    **kw,
) -> Optional[sqlite3.Row]:
    clause, params = _date_clause(**kw)
    return conn.execute(f"""
        SELECT
            company_name,
            COUNT(*)                                                                   AS total,
            SUM(CASE WHEN delivery_status_code = '200' THEN 1 ELSE 0 END)             AS delivered,
            SUM(CASE WHEN delivery_status_code != '200' THEN 1 ELSE 0 END)            AS failed,
            MIN(created)                                                               AS first_ts,
            MAX(created)                                                               AS last_ts,
            GROUP_CONCAT(DISTINCT campaign_id)                                         AS campaign_ids
        FROM commio_records
        WHERE company_name = ? {clause}
    """, [company_name] + params).fetchone()


def get_failure_breakdown(
    conn: sqlite3.Connection,
    company_name: str,
    **kw,
) -> list[sqlite3.Row]:
    clause, params = _date_clause(**kw)
    return conn.execute(f"""
        SELECT
            COALESCE(NULLIF(trim(carrier), ''), 'Unknown')                             AS carrier,
            COALESCE(NULLIF(trim(status_description), ''), delivery_status_code, 'Unknown') AS error,
            delivery_status_code                                                        AS status_code,
            COUNT(*)                                                                    AS cnt
        FROM commio_records
        WHERE company_name = ?
          AND delivery_status_code != '200' {clause}
        GROUP BY carrier, delivery_status_code
        ORDER BY cnt DESC
    """, [company_name] + params).fetchall()


def get_company_records(
    conn: sqlite3.Connection,
    company_name: str,
    limit: int = 100,
    offset: int = 0,
    **kw,
) -> list[sqlite3.Row]:
    clause, params = _date_clause(**kw)
    return conn.execute(
        f"SELECT * FROM commio_records WHERE company_name = ? {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        [company_name] + params + [limit, offset],
    ).fetchall()


def count_company_records(
    conn: sqlite3.Connection,
    company_name: str,
    **kw,
) -> int:
    clause, params = _date_clause(**kw)
    return conn.execute(
        f"SELECT COUNT(*) FROM commio_records WHERE company_name = ? {clause}",
        [company_name] + params,
    ).fetchone()[0]
