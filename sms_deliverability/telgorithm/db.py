import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent / "data" / "sms_deliverability.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Keep writes fast; readers never block writers
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")   # 32 MB page cache
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telgorithm_records (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                created_on             TEXT,
                from_number            TEXT,
                to_number              TEXT,
                text_segment_count     TEXT,
                status                 TEXT,
                error_code             TEXT,
                error_description      TEXT,
                campaign_id            TEXT,
                recipient_carrier_name TEXT,
                text                   TEXT,
                batch_id               TEXT,
                imported_at            TEXT,
                company_name           TEXT,
                report_date            TEXT    -- YYYY-MM-DD, set by user on upload
            )
        """)

        # Idempotent migrations for existing DBs
        for col, definition in [
            ("company_name", "TEXT"),
            ("report_date",  "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE telgorithm_records ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass  # already exists

        # Back-fill report_date from imported_at for rows that predate this column
        conn.execute("""
            UPDATE telgorithm_records
               SET report_date = substr(imported_at, 1, 10)
             WHERE report_date IS NULL AND imported_at IS NOT NULL
        """)

        # Indexes — make daily-filtered queries instant even at millions of rows
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tel_company_date
            ON telgorithm_records(company_name, report_date)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tel_report_date
            ON telgorithm_records(report_date)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tel_status
            ON telgorithm_records(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tel_campaign
            ON telgorithm_records(campaign_id)
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
    """Distinct report dates, newest first."""
    return conn.execute("""
        SELECT report_date, COUNT(*) AS record_count
          FROM telgorithm_records
         WHERE report_date IS NOT NULL
         GROUP BY report_date
         ORDER BY report_date DESC
    """).fetchall()


def get_all_records(
    conn: sqlite3.Connection,
    limit: int = 100,
    offset: int = 0,
    report_date: Optional[str] = None,
) -> list[sqlite3.Row]:
    clause, params = _date_clause(report_date)
    return conn.execute(
        f"SELECT * FROM telgorithm_records WHERE 1=1 {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()


def count_all_records(conn: sqlite3.Connection, report_date: Optional[str] = None) -> int:
    clause, params = _date_clause(report_date)
    return conn.execute(
        f"SELECT COUNT(*) FROM telgorithm_records WHERE 1=1 {clause}",
        params,
    ).fetchone()[0]


def get_companies(conn: sqlite3.Connection, **kw) -> list[sqlite3.Row]:
    clause, params = _date_clause(**kw)
    return conn.execute(f"""
        SELECT
            company_name,
            COUNT(*)                                                              AS total,
            SUM(CASE WHEN lower(status) = 'delivered' THEN 1 ELSE 0 END)         AS delivered,
            SUM(CASE WHEN lower(status) != 'delivered' THEN 1 ELSE 0 END)        AS failed,
            MIN(created_on)                                                       AS first_ts,
            MAX(created_on)                                                       AS last_ts
        FROM telgorithm_records
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
            COUNT(*)                                                              AS total,
            SUM(CASE WHEN lower(status) = 'delivered' THEN 1 ELSE 0 END)         AS delivered,
            SUM(CASE WHEN lower(status) != 'delivered' THEN 1 ELSE 0 END)        AS failed,
            MIN(created_on)                                                       AS first_ts,
            MAX(created_on)                                                       AS last_ts,
            GROUP_CONCAT(DISTINCT campaign_id)                                    AS campaign_ids
        FROM telgorithm_records
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
            COALESCE(NULLIF(trim(recipient_carrier_name), ''), 'Unknown')         AS carrier,
            COALESCE(
                NULLIF(trim(error_description), ''),
                NULLIF(trim(error_code), ''),
                'Unknown'
            )                                                                     AS error,
            COUNT(*)                                                              AS cnt
        FROM telgorithm_records
        WHERE company_name = ?
          AND lower(status) != 'delivered' {clause}
        GROUP BY carrier, error
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
        f"SELECT * FROM telgorithm_records WHERE company_name = ? {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        [company_name] + params + [limit, offset],
    ).fetchall()


def count_company_records(
    conn: sqlite3.Connection,
    company_name: str,
    **kw,
) -> int:
    clause, params = _date_clause(**kw)
    return conn.execute(
        f"SELECT COUNT(*) FROM telgorithm_records WHERE company_name = ? {clause}",
        [company_name] + params,
    ).fetchone()[0]
