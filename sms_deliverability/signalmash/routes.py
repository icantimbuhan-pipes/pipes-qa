import csv
import io
import uuid
from datetime import date as date_type
from datetime import datetime, timezone
from typing import Optional

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from sms_deliverability.signalmash.campaign_map import CAMPAIGN_MAP, SLUG_TO_COMPANY, slugify
from sms_deliverability.signalmash.db import (
    count_company_records,
    get_available_dates,
    get_companies,
    get_company_records,
    get_company_stats,
    get_conn,
    get_failure_breakdown,
    init_db,
)
from sms_deliverability.signalmash.error_codes import DELIVERED_CODE, describe
from sms_deliverability.telgorithm.metrics import rate_pct

bp = Blueprint("signalmash", __name__, template_folder="templates")

REQUIRED_HEADERS = {"monthnum", "day", "year", "from_number", "operator", "mobility", "campaignid"}

# Header aliases (normalize to lowercase canonical)
_ALIASES: dict[str, str] = {
    "monthnum": "monthnum", "month_num": "monthnum", "month": "monthnum",
    "day": "day",
    "year": "year",
    "from_number": "from_number", "fromnumber": "from_number", "from": "from_number",
    "operator": "operator",
    "mobility": "mobility",
    "campaignid": "campaignid", "campaign_id": "campaignid",
    "campaignsid": "campaignid", "campaign sid": "campaignid",
}


def _remap(fieldnames: list[str]) -> dict[str, str]:
    """Map raw header → canonical name or keep as-is for DLR columns."""
    out: dict[str, str] = {}
    for raw in fieldnames:
        normalized = raw.strip().lower()
        canonical = _ALIASES.get(normalized)
        if canonical:
            out[raw] = canonical
        else:
            # Keep potential DLR numeric columns (e.g. "0", "201")
            out[raw] = raw.strip()
    return out


def _is_dlr_col(col: str) -> bool:
    try:
        int(col)
        return True
    except ValueError:
        return False


def _today() -> str:
    return date_type.today().isoformat()


def _get_date_filter() -> Optional[str]:
    d = request.args.get("date", "").strip()
    return d if d else None


def _build_date(monthnum: str, day: str, year: str) -> str:
    try:
        return f"{int(year):04d}-{int(monthnum):02d}-{int(day):02d}"
    except (ValueError, TypeError):
        return _today()


# ── Upload ────────────────────────────────────────────────────────────────────

@bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("signalmash/upload.html", today=_today())

    file = request.files.get("csv_file")
    if not file or file.filename == "":
        flash("No file selected.", "error")
        return render_template("signalmash/upload.html", today=_today())

    if not file.filename.lower().endswith(".csv"):
        flash("File must be a .csv file.", "error")
        return render_template("signalmash/upload.html", today=_today())

    try:
        content = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("Could not decode file — ensure it is UTF-8 encoded.", "error")
        return render_template("signalmash/upload.html", today=_today())

    reader = csv.DictReader(io.StringIO(content))
    raw_fieldnames = reader.fieldnames or []
    remap = _remap(raw_fieldnames)
    recognized_fixed = {v for v in remap.values() if v in REQUIRED_HEADERS}
    missing = REQUIRED_HEADERS - recognized_fixed
    if missing:
        found = ", ".join(raw_fieldnames) or "(none)"
        flash(f"Missing required columns: {', '.join(sorted(missing))}. Found: {found}", "error")
        return render_template("signalmash/upload.html", today=_today())

    dlr_cols = [raw for raw, canonical in remap.items() if _is_dlr_col(canonical)]

    batch_id = str(uuid.uuid4())
    imported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    insert_rows: list[tuple] = []
    for raw_row in reader:
        row = {remap.get(k, k): v for k, v in raw_row.items()}
        report_date = _build_date(
            row.get("monthnum", ""), row.get("day", ""), row.get("year", "")
        )
        from_number = row.get("from_number", "").strip()
        operator    = row.get("operator", "").strip()
        mobility    = row.get("mobility", "").strip()
        campaign_id = row.get("campaignid", "").strip()
        company     = CAMPAIGN_MAP.get(campaign_id)

        for dlr_raw in dlr_cols:
            dlr_code = remap.get(dlr_raw, dlr_raw).strip()
            raw_val  = raw_row.get(dlr_raw, "").strip()
            try:
                count = int(raw_val)
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

    if not insert_rows:
        flash("CSV has no non-zero delivery records.", "error")
        return render_template("signalmash/upload.html", today=_today())

    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO signalmash_records
                (report_date, from_number, operator, mobility, campaign_id, company_name,
                 dlr_code, dlr_description, count, batch_id, imported_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, insert_rows)
        conn.commit()

    dates = sorted({r[0] for r in insert_rows})
    mapped = sum(1 for r in insert_rows if r[5] is not None)
    flash(
        f"Imported {len(insert_rows):,} DLR records for {', '.join(dates)} "
        f"({mapped:,} matched to a company).",
        "success",
    )
    return redirect(url_for("signalmash.reports", date=dates[-1]))


# ── Reports list ──────────────────────────────────────────────────────────────

@bp.route("/reports")
def reports():
    report_date = _get_date_filter()
    with get_conn() as conn:
        available_dates = get_available_dates(conn)
        if report_date is None and available_dates:
            report_date = available_dates[0]["report_date"]
        companies_raw = get_companies(conn, report_date=report_date)

    companies = []
    for c in companies_raw:
        total, delivered, failed = c["total"], c["delivered"], c["failed"]
        companies.append({
            "name": c["company_name"],
            "slug": slugify(c["company_name"]),
            "total": total,
            "delivered": delivered,
            "failed": failed,
            "delivered_rate": rate_pct(delivered, total),
            "failed_rate": rate_pct(failed, total),
        })

    return render_template(
        "signalmash/reports.html",
        companies=companies,
        available_dates=available_dates,
        selected_date=report_date,
    )


# ── Per-company report ────────────────────────────────────────────────────────

@bp.route("/report/<slug>")
def report(slug: str):
    company_name = SLUG_TO_COMPANY.get(slug)
    if not company_name:
        abort(404)

    report_date = _get_date_filter()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 200
    offset = (page - 1) * per_page

    with get_conn() as conn:
        available_dates = get_available_dates(conn)
        if report_date is None and available_dates:
            report_date = available_dates[0]["report_date"]
        stats        = get_company_stats(conn, company_name, report_date=report_date)
        failures     = get_failure_breakdown(conn, company_name, report_date=report_date)
        rows         = get_company_records(conn, company_name, limit=per_page, offset=offset, report_date=report_date)
        total_records = count_company_records(conn, company_name, report_date=report_date)

    if stats is None or stats["total"] == 0:
        return render_template(
            "signalmash/report.html",
            company_name=company_name, slug=slug,
            kpi=None, failures=[], rows=[],
            page=1, total_pages=1, total_records=0,
            available_dates=available_dates, selected_date=report_date,
        )

    total, delivered, failed = stats["total"], stats["delivered"], stats["failed"]
    kpi = {
        "total": total,
        "delivered": delivered,
        "failed": failed,
        "delivered_rate": rate_pct(delivered, total),
        "failed_rate": rate_pct(failed, total),
        "campaign_ids": (stats["campaign_ids"] or "").split(","),
    }

    total_pages = max(1, (total_records + per_page - 1) // per_page)
    return render_template(
        "signalmash/report.html",
        company_name=company_name, slug=slug,
        kpi=kpi, failures=failures, rows=rows,
        page=page, total_pages=total_pages, total_records=total_records,
        available_dates=available_dates, selected_date=report_date,
    )


# ── CSV Download ──────────────────────────────────────────────────────────────

@bp.route("/report/<slug>/download")
def download_csv(slug: str):
    company_name = SLUG_TO_COMPANY.get(slug)
    if not company_name:
        abort(404)

    report_date = request.args.get("date", "").strip() or None
    with get_conn() as conn:
        stats    = get_company_stats(conn, company_name, report_date=report_date)
        failures = get_failure_breakdown(conn, company_name, report_date=report_date)
        rows     = get_company_records(conn, company_name, limit=500_000, offset=0, report_date=report_date)

    buf = io.StringIO()
    w = csv.writer(buf)
    label = report_date or "all-time"

    w.writerow(["SMS DELIVERABILITY REPORT (SIGNALMASH) — KPI SUMMARY"])
    w.writerow(["Company", company_name])
    w.writerow(["Date", label])
    w.writerow([])
    if stats and stats["total"]:
        total, delivered, failed = stats["total"], stats["delivered"], stats["failed"]
        w.writerow(["Metric", "Value"])
        w.writerow(["Total Messages",  total])
        w.writerow(["Delivered SMS",   delivered])
        w.writerow(["Failed SMS",      failed])
        w.writerow(["Delivered Rate",  f"{rate_pct(delivered, total)}%"])
        w.writerow(["Failed Rate",     f"{rate_pct(failed, total)}%"])
        w.writerow(["Campaign IDs",    stats["campaign_ids"] or ""])
    else:
        w.writerow(["No data for this period."])
    w.writerow([])

    w.writerow(["FAILURE BREAKDOWN"])
    w.writerow(["Carrier (Operator)", "DLR Code", "Error Description", "Count", "% of Failures"])
    total_failed = stats["failed"] if stats else 0
    for f in failures:
        pct = f"{f['cnt'] / total_failed * 100:.1f}%" if total_failed else "—"
        w.writerow([f["carrier"], f["dlr_code"], f["error"], f["cnt"], pct])
    w.writerow([])

    w.writerow(["DLR RECORDS"])
    w.writerow(["Date", "From Number", "Operator", "Mobility", "Campaign ID", "DLR Code", "Description", "Count"])
    for row in rows:
        w.writerow([
            row["report_date"], row["from_number"], row["operator"],
            row["mobility"], row["campaign_id"],
            row["dlr_code"], row["dlr_description"], row["count"],
        ])

    filename = f"signalmash_{slugify(company_name)}_{label}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
