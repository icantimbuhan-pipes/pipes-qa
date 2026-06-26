"""
Bulk import script for 3-month Telgorithm CSV and Signalmash XLSX.
Run from project root: python3 scripts/import_bulk.py
"""
import csv
import io
import sys
import os
import uuid
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TELGO_FILE  = "data/Telgo april to June/thm-outbound-messages 8.csv"
SIGNAL_FILE = "data/Signalmash YTD /872_MDR_20260101_20260624_DAY_DLR_ERR_SORTED.xlsx"


# ── Telgorithm ────────────────────────────────────────────────────────────────

def import_telgorithm():
    from sms_deliverability.telgorithm.db import get_conn, init_db
    from sms_deliverability.telgorithm.campaign_map import CAMPAIGN_MAP
    from sms_deliverability.telgorithm.routes import _remap_fieldnames, _normalize_row

    init_db()

    print(f"Reading {TELGO_FILE}...")
    with open(TELGO_FILE, encoding="utf-8-sig") as f:
        content = f.read()

    reader = csv.DictReader(io.StringIO(content))
    raw_fieldnames = reader.fieldnames or []
    remap = _remap_fieldnames(raw_fieldnames)
    print("  Column map sample:", {k: v for k, v in list(remap.items())[:6]})

    # Check for critical missing columns
    recognized = set(remap.values())
    required = {"CreatedOn", "From", "To", "Status", "Campaign ID", "RecipientCarrierName"}
    missing = required - recognized
    if missing:
        print(f"  WARNING: missing columns: {missing}")

    batch_id = str(uuid.uuid4())
    imported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    rows = []
    skipped = 0
    for raw_row in reader:
        row = _normalize_row(raw_row, remap)
        created_on = row.get("CreatedOn", "").strip()

        # Parse report_date from CreatedOn: "05/23/2026 16:57:21" → "2026-05-23"
        report_date = ""
        if created_on:
            try:
                dt = datetime.strptime(created_on, "%m/%d/%Y %H:%M:%S")
                report_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                try:
                    dt = datetime.strptime(created_on, "%Y-%m-%d %H:%M:%S")
                    report_date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    report_date = created_on[:10]

        campaign_id = row.get("Campaign ID", "").strip()
        rows.append((
            created_on,
            row.get("From", ""),
            row.get("To", ""),
            row.get("TextSegmentCount", ""),
            row.get("Status", ""),
            row.get("ErrorCode", ""),
            row.get("ErrorDescription", ""),
            campaign_id,
            row.get("RecipientCarrierName", ""),
            row.get("Text", ""),
            batch_id,
            imported_at,
            CAMPAIGN_MAP.get(campaign_id),
            report_date,
        ))

    print(f"  Parsed {len(rows):,} rows ({skipped} skipped)")

    # Insert in chunks of 5000
    chunk_size = 5000
    total_inserted = 0
    with get_conn() as conn:
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i + chunk_size]
            conn.executemany(
                """
                INSERT INTO telgorithm_records
                    (created_on, from_number, to_number, text_segment_count, status,
                     error_code, error_description, campaign_id, recipient_carrier_name,
                     text, batch_id, imported_at, company_name, report_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                chunk,
            )
            total_inserted += len(chunk)
            print(f"  Inserted {total_inserted:,}/{len(rows):,}...", end="\r")
        conn.commit()

    mapped = sum(1 for r in rows if r[-2] is not None)
    dates = sorted({r[-1] for r in rows if r[-1]})
    print(f"\n  Done: {total_inserted:,} records, {mapped:,} matched to a company")
    print(f"  Dates: {dates[0]} → {dates[-1]}" if dates else "  No dates parsed")


# ── Signalmash ────────────────────────────────────────────────────────────────

def import_signalmash():
    import openpyxl
    from sms_deliverability.signalmash.db import get_conn, init_db
    from sms_deliverability.signalmash.campaign_map import CAMPAIGN_MAP
    from sms_deliverability.signalmash.error_codes import describe
    from sms_deliverability.signalmash.routes import _remap, _is_dlr_col, _build_date

    init_db()

    REQUIRED_HEADERS = {"monthnum", "day", "year", "from_number", "operator", "mobility", "campaignid"}

    print(f"\nReading {SIGNAL_FILE}...")
    wb = openpyxl.load_workbook(SIGNAL_FILE, read_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    raw_fieldnames = [str(h) if h is not None else "" for h in next(rows_iter)]
    print(f"  Columns ({len(raw_fieldnames)}): {raw_fieldnames[:10]}...")

    remap = _remap(raw_fieldnames)
    recognized_fixed = {v for v in remap.values() if v in REQUIRED_HEADERS}
    missing = REQUIRED_HEADERS - recognized_fixed
    if missing:
        print(f"  WARNING missing columns: {missing}")

    dlr_cols_raw = [raw for raw, canonical in remap.items() if _is_dlr_col(canonical)]
    print(f"  DLR columns: {len(dlr_cols_raw)}: {[remap[c] for c in dlr_cols_raw[:8]]}...")

    batch_id = str(uuid.uuid4())
    imported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    insert_rows = []
    row_num = 0
    for xlsx_row in rows_iter:
        row_num += 1
        raw_row = {raw_fieldnames[i]: (str(xlsx_row[i]) if xlsx_row[i] is not None else "") for i in range(len(raw_fieldnames))}
        row = {remap.get(k, k): v for k, v in raw_row.items()}

        report_date = _build_date(row.get("monthnum", ""), row.get("day", ""), row.get("year", ""))
        from_number = row.get("from_number", "").strip()
        operator    = row.get("operator", "").strip()
        mobility    = row.get("mobility", "").strip()
        campaign_id = row.get("campaignid", "").strip()
        company     = CAMPAIGN_MAP.get(campaign_id)

        for dlr_raw in dlr_cols_raw:
            dlr_code = remap.get(dlr_raw, dlr_raw).strip()
            raw_val  = raw_row.get(dlr_raw, "").strip()
            try:
                count = int(float(raw_val)) if raw_val else 0
            except (ValueError, TypeError):
                count = 0
            if count <= 0:
                continue
            insert_rows.append((
                report_date, from_number, operator, mobility,
                campaign_id, company,
                dlr_code, describe(dlr_code),
                count, batch_id, imported_at,
            ))

        if row_num % 5000 == 0:
            print(f"  Processed {row_num:,} xlsx rows → {len(insert_rows):,} DLR records...", end="\r")

    wb.close()
    print(f"\n  Parsed {row_num:,} rows → {len(insert_rows):,} non-zero DLR records")

    if not insert_rows:
        print("  Nothing to insert.")
        return

    chunk_size = 5000
    total_inserted = 0
    with get_conn() as conn:
        for i in range(0, len(insert_rows), chunk_size):
            chunk = insert_rows[i:i + chunk_size]
            conn.executemany("""
                INSERT INTO signalmash_records
                    (report_date, from_number, operator, mobility, campaign_id, company_name,
                     dlr_code, dlr_description, count, batch_id, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, chunk)
            total_inserted += len(chunk)
            print(f"  Inserted {total_inserted:,}/{len(insert_rows):,}...", end="\r")
        conn.commit()

    mapped = sum(1 for r in insert_rows if r[5] is not None)
    dates = sorted({r[0] for r in insert_rows})
    print(f"\n  Done: {total_inserted:,} DLR records, {mapped:,} matched to company")
    print(f"  Dates: {dates[0]} → {dates[-1]}" if dates else "  No dates parsed")


if __name__ == "__main__":
    import_telgorithm()
    import_signalmash()
    print("\nAll imports complete.")
