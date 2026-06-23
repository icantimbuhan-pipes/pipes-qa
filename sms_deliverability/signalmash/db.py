import sqlite3
from pathlib import Path
from typing import Optional

# Signalmash uses a separate DB file to keep it isolated from Telgorithm
DB_PATH = Path(__file__).parent.parent.parent / "data" / "sms_signalmash.db"


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
            CREATE TABLE IF NOT EXISTS signalmash_records (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date      TEXT,    -- YYYY-MM-DD (built from monthnum/day/year)
                from_number      TEXT,
                operator         TEXT,    -- carrier name
                mobility         TEXT,
                campaign_id      TEXT,
                company_name     TEXT,
                dlr_code         TEXT,    -- numeric code: "0", "201", etc.
                dlr_description  TEXT,    -- human-readable from error_codes
                count            INTEGER, -- messages with this code in this row
                batch_id         TEXT,
                imported_at      TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_company_date  ON signalmash_records(company_name, report_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_report_date   ON signalmash_records(report_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_dlr_code      ON signalmash_records(dlr_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_operator       ON signalmash_records(operator)")
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
        SELECT report_date, SUM(count) AS record_count
          FROM signalmash_records
         WHERE report_date IS NOT NULL
         GROUP BY report_date
         ORDER BY report_date DESC
    """).fetchall()


def get_companies(conn: sqlite3.Connection, **kw) -> list[sqlite3.Row]:
    clause, params = _date_clause(**kw)
    return conn.execute(f"""
        SELECT
            company_name,
            SUM(count)                                                             AS total,
            SUM(CASE WHEN dlr_code = '0' THEN count ELSE 0 END)                   AS delivered,
            SUM(CASE WHEN dlr_code != '0' THEN count ELSE 0 END)                  AS failed
        FROM signalmash_records
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
            SUM(count)                                                             AS total,
            SUM(CASE WHEN dlr_code = '0' THEN count ELSE 0 END)                   AS delivered,
            SUM(CASE WHEN dlr_code != '0' THEN count ELSE 0 END)                  AS failed,
            GROUP_CONCAT(DISTINCT campaign_id)                                     AS campaign_ids
        FROM signalmash_records
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
            COALESCE(NULLIF(trim(operator), ''), 'Unknown')   AS carrier,
            dlr_description                                    AS error,
            dlr_code,
            SUM(count)                                         AS cnt
        FROM signalmash_records
        WHERE company_name = ? AND dlr_code != '0' {clause}
        GROUP BY carrier, dlr_code
        ORDER BY cnt DESC
    """, [company_name] + params).fetchall()


def get_company_records(
    conn: sqlite3.Connection,
    company_name: str,
    limit: int = 200,
    offset: int = 0,
    **kw,
) -> list[sqlite3.Row]:
    clause, params = _date_clause(**kw)
    return conn.execute(
        f"SELECT * FROM signalmash_records WHERE company_name = ? {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        [company_name] + params + [limit, offset],
    ).fetchall()


def count_company_records(
    conn: sqlite3.Connection,
    company_name: str,
    **kw,
) -> int:
    clause, params = _date_clause(**kw)
    return conn.execute(
        f"SELECT COUNT(*) FROM signalmash_records WHERE company_name = ? {clause}",
        [company_name] + params,
    ).fetchone()[0]
