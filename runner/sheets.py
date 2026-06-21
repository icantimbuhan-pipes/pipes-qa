"""
Google Sheets reader — public CSV export.
Sheet must be "Anyone with the link can view" (no API keys needed).
"""
import csv
import io
from datetime import date, datetime
from typing import Optional

import httpx

SHEET_ID = "1_Jbh36IsSnwLOHhRHMnUPvc-NngTk23hoIOug3DZPCQ"
GID = "0"
_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    f"/export?format=csv&gid={GID}"
)


def _pct(value: str) -> str:
    """Normalise a cell value to '6.32%' format."""
    v = value.strip()
    if not v:
        return v
    try:
        # Raw decimal from Sheets (e.g. 0.0632) → percentage string
        f = float(v)
        if f < 1:
            return f"{f * 100:.2f}%"
        return f"{f:.2f}%"
    except ValueError:
        # Already formatted (e.g. '6.32%')
        return v


def fetch_khomp_classification(target_date: Optional[date] = None) -> Optional[str]:
    """
    Reads the Khomp Classification sheet and returns the most recent row
    that has Short/Long/Timeout data.  If *target_date* is given, tries
    that date first; falls back to the most recent non-empty row.

    Returns: '06/18/2026 | Short : 6.32% | Long : 0.03% | Timeout : 1.35%'
    or None on error / no data.
    """
    try:
        r = httpx.get(_CSV_URL, timeout=10, follow_redirects=True)
        r.raise_for_status()
    except Exception:
        return None

    rows = list(csv.reader(io.StringIO(r.text)))
    if len(rows) < 2:
        return None

    best: tuple[date, str, str, str, str] | None = None  # (date_obj, date_str, short, long, timeout)

    for row in rows[1:]:  # skip header row
        if len(row) < 4:
            continue
        date_str = row[0].strip()
        short_raw = row[1].strip()
        long_raw  = row[2].strip()
        to_raw    = row[3].strip()

        if not date_str or not short_raw:
            continue

        try:
            row_date = datetime.strptime(date_str, "%m/%d/%Y").date()
        except ValueError:
            continue

        short   = _pct(short_raw)
        long_   = _pct(long_raw)
        timeout = _pct(to_raw)

        if target_date and row_date == target_date:
            return f"{date_str} | Short : {short} | Long : {long_} | Timeout : {timeout}"

        if best is None or row_date > best[0]:
            best = (row_date, date_str, short, long_, timeout)

    if best:
        _, date_str, short, long_, timeout = best
        return f"{date_str} | Short : {short} | Long : {long_} | Timeout : {timeout}"

    return None
