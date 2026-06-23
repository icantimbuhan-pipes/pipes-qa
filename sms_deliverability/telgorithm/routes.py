import csv
import io
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from sms_deliverability.telgorithm.campaign_map import CAMPAIGN_MAP, SLUG_TO_COMPANY, slugify
from sms_deliverability.telgorithm import slack as slack_mod
from sms_deliverability.telgorithm.db import (
    count_all_records,
    count_company_records,
    get_all_records,
    get_available_dates,
    get_companies,
    get_company_records,
    get_company_stats,
    get_conn,
    get_failure_breakdown,
)
from sms_deliverability.telgorithm.metrics import avg_per_minute, rate_pct

bp = Blueprint("telgorithm", __name__, template_folder="templates")

CANONICAL_HEADERS = [
    "CreatedOn", "From", "To", "TextSegmentCount", "Status",
    "ErrorCode", "ErrorDescription", "Campaign ID", "RecipientCarrierName", "Text",
]

_ALIASES: dict[str, str] = {}
for _canonical, _variants in {
    "CreatedOn":            ["createdon", "created on", "created_on", "date", "datetime"],
    "From":                 ["from", "fromnumber", "from number", "sender"],
    "To":                   ["to", "tonumber", "to number", "recipient"],
    "TextSegmentCount":     ["textsegmentcount", "text segment count", "text_segment_count", "segments", "segmentcount"],
    "Status":               ["status", "messagestatus", "message status", "deliverystatus"],
    "ErrorCode":            ["errorcode", "error code", "error_code", "errorsid"],
    "ErrorDescription":     ["errordescription", "error description", "error_description", "errormessage", "error message"],
    "Campaign ID":          ["campaign id", "campaignid", "campaign_id", "campaignID", "campaignsid", "campaign sid", "campaign_sid"],
    "RecipientCarrierName": ["recipientcarriername", "recipient carrier name", "recipient_carrier_name", "carriername", "carrier name", "carrier"],
    "Text":                 ["text", "body", "message", "messagebody"],
}.items():
    for _v in _variants:
        _ALIASES[_v] = _canonical
    _ALIASES[_canonical.lower()] = _canonical

_SUBSTRING_FALLBACKS: list[tuple[str, str]] = [
    ("campaign", "Campaign ID"),
    ("carrier",  "RecipientCarrierName"),
    ("segment",  "TextSegmentCount"),
    ("created",  "CreatedOn"),
    ("error desc", "ErrorDescription"),
    ("errorcode", "ErrorCode"),
]


def _remap_fieldnames(fieldnames: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw in fieldnames:
        normalized = raw.strip().lower()
        canonical = _ALIASES.get(normalized)
        if canonical is None:
            for keyword, fallback_canonical in _SUBSTRING_FALLBACKS:
                if keyword in normalized:
                    canonical = fallback_canonical
                    break
        if canonical:
            mapping[raw] = canonical
    return mapping


def _normalize_row(row: dict, remap: dict[str, str]) -> dict[str, str]:
    return {remap.get(k, k): v for k, v in row.items()}


def _today() -> str:
    return date_type.today().isoformat()


def _dates_to_weeks(dates: list) -> list:
    weeks: dict[str, dict] = {}
    for row in dates:
        try:
            d = date_type.fromisoformat(row["report_date"])
        except (ValueError, TypeError):
            continue
        ws = d - timedelta(days=d.weekday())
        we = ws + timedelta(days=6)
        key = ws.isoformat()
        if key not in weeks:
            weeks[key] = {"start": ws.isoformat(), "end": we.isoformat(), "count": 0,
                          "label": f"{ws.strftime('%b %d')} – {we.strftime('%b %d')}"}
        weeks[key]["count"] += row["record_count"]
    return sorted(weeks.values(), key=lambda w: w["start"], reverse=True)


def _dates_to_months(dates: list) -> list:
    months: dict[str, dict] = {}
    for row in dates:
        try:
            month = row["report_date"][:7]
        except (TypeError, AttributeError):
            continue
        if month not in months:
            months[month] = {"month": month, "count": 0}
        months[month]["count"] += row["record_count"]
    return sorted(months.values(), key=lambda m: m["month"], reverse=True)


def _parse_view(available_dates: list) -> tuple:
    view = request.args.get("view", "day")
    date_param = request.args.get("date", "").strip()
    month_param = request.args.get("month", "").strip()
    weeks = _dates_to_weeks(available_dates)
    months = _dates_to_months(available_dates)

    if view == "month":
        month = month_param or (date_param[:7] if len(date_param) >= 7 else "")
        if not month and months:
            month = months[0]["month"]
        return ({"month": month} if month else {}, "month", month, "", month, weeks, months)

    if view == "week":
        if date_param:
            try:
                d = date_type.fromisoformat(date_param)
            except ValueError:
                d = date_type.today()
        elif available_dates:
            try:
                d = date_type.fromisoformat(available_dates[0]["report_date"])
            except (ValueError, TypeError):
                d = date_type.today()
        else:
            d = date_type.today()
        ws = d - timedelta(days=d.weekday())
        we = ws + timedelta(days=6)
        label = f"{ws.strftime('%b %d')} – {we.strftime('%b %d, %Y')}"
        return ({"date_from": ws.isoformat(), "date_to": we.isoformat()}, "week", label,
                ws.isoformat(), "", weeks, months)

    # day
    report_date = date_param or (available_dates[0]["report_date"] if available_dates else "")
    label = report_date
    return ({"report_date": report_date} if report_date else {}, "day", label,
            report_date, "", weeks, months)


# ── Upload ────────────────────────────────────────────────────────────────────

@bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("telgorithm/upload.html", today=_today())

    file = request.files.get("csv_file")
    if not file or file.filename == "":
        flash("No file selected.", "error")
        return render_template("telgorithm/upload.html", today=_today())

    if not file.filename.lower().endswith(".csv"):
        flash("File must be a .csv file.", "error")
        return render_template("telgorithm/upload.html", today=_today())

    report_date = request.form.get("report_date", "").strip() or _today()

    try:
        content = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("Could not read file — ensure it is UTF-8 encoded.", "error")
        return render_template("telgorithm/upload.html", today=_today())

    reader = csv.DictReader(io.StringIO(content))
    raw_fieldnames = reader.fieldnames or []
    remap = _remap_fieldnames(raw_fieldnames)
    recognized = set(remap.values())
    missing = set(CANONICAL_HEADERS) - recognized
    if missing:
        found_headers = ", ".join(raw_fieldnames) if raw_fieldnames else "(none)"
        flash(
            f"Missing required columns: {', '.join(sorted(missing))}. "
            f"Columns found in your CSV: {found_headers}",
            "error",
        )
        return render_template("telgorithm/upload.html", today=_today())

    batch_id = str(uuid.uuid4())
    imported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    rows = []
    for raw_row in reader:
        row = _normalize_row(raw_row, remap)
        campaign_id = row.get("Campaign ID", "").strip()
        rows.append((
            row.get("CreatedOn", ""),
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

    if not rows:
        flash("CSV has no data rows.", "error")
        return render_template("telgorithm/upload.html", today=_today())

    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO telgorithm_records
                (created_on, from_number, to_number, text_segment_count, status,
                 error_code, error_description, campaign_id, recipient_carrier_name,
                 text, batch_id, imported_at, company_name, report_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    mapped = sum(1 for r in rows if r[-2] is not None)  # company_name is index -2
    flash(
        f"Imported {len(rows):,} records for {report_date} ({mapped:,} matched to a company).",
        "success",
    )
    return redirect(url_for("telgorithm.reports", date=report_date))


# ── Raw records ───────────────────────────────────────────────────────────────

@bp.route("/records")
def records():
    report_date = _get_date_filter()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 100
    offset = (page - 1) * per_page

    with get_conn() as conn:
        available_dates = get_available_dates(conn)
        total = count_all_records(conn, report_date=report_date)
        rows = get_all_records(conn, limit=per_page, offset=offset, report_date=report_date)

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "telgorithm/records.html",
        rows=rows,
        total=total,
        page=page,
        total_pages=total_pages,
        available_dates=available_dates,
        selected_date=report_date,
    )


# ── Company reports list ──────────────────────────────────────────────────────

@bp.route("/reports")
def reports():
    with get_conn() as conn:
        available_dates = get_available_dates(conn)
    kw, view, label, selected_date, selected_month, weeks, months = _parse_view(available_dates)

    with get_conn() as conn:
        companies_raw = get_companies(conn, **kw)

    companies = []
    for c in companies_raw:
        total = c["total"]
        delivered = c["delivered"]
        failed = c["failed"]
        companies.append({
            "name": c["company_name"],
            "slug": slugify(c["company_name"]),
            "total": total,
            "delivered": delivered,
            "failed": failed,
            "delivered_rate": rate_pct(delivered, total),
            "failed_rate": rate_pct(failed, total),
            "avg_per_min": avg_per_minute(total, c["first_ts"], c["last_ts"]),
        })

    return render_template(
        "telgorithm/reports.html",
        companies=companies,
        available_dates=available_dates,
        selected_date=selected_date,
        selected_month=selected_month,
        view=view,
        label=label,
        weeks=weeks,
        months=months,
    )


# ── Per-company report ────────────────────────────────────────────────────────

@bp.route("/report/<slug>")
def report(slug: str):
    company_name = SLUG_TO_COMPANY.get(slug)
    if not company_name:
        abort(404)

    page = max(1, request.args.get("page", 1, type=int))
    per_page = 100
    offset = (page - 1) * per_page

    with get_conn() as conn:
        available_dates = get_available_dates(conn)
    kw, view, label, selected_date, selected_month, weeks, months = _parse_view(available_dates)

    with get_conn() as conn:
        stats = get_company_stats(conn, company_name, **kw)
        failures = get_failure_breakdown(conn, company_name, **kw)
        rows = get_company_records(conn, company_name, limit=per_page, offset=offset, **kw)
        total_records = count_company_records(conn, company_name, **kw)

    shared = dict(
        company_name=company_name, slug=slug,
        available_dates=available_dates, selected_date=selected_date,
        selected_month=selected_month, view=view, label=label,
        weeks=weeks, months=months,
    )

    if stats is None or stats["total"] == 0:
        return render_template("telgorithm/report.html",
            kpi=None, failures=[], rows=[], page=1, total_pages=1, total_records=0, **shared)

    total = stats["total"]
    delivered = stats["delivered"]
    failed = stats["failed"]
    kpi = {
        "total": total,
        "delivered": delivered,
        "failed": failed,
        "delivered_rate": rate_pct(delivered, total),
        "failed_rate": rate_pct(failed, total),
        "avg_per_min": avg_per_minute(total, stats["first_ts"], stats["last_ts"]),
        "campaign_ids": (stats["campaign_ids"] or "").split(","),
    }
    total_pages = max(1, (total_records + per_page - 1) // per_page)
    return render_template("telgorithm/report.html",
        kpi=kpi, failures=failures, rows=rows,
        page=page, total_pages=total_pages, total_records=total_records, **shared)


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
        rows     = get_company_records(conn, company_name, limit=100_000, offset=0, report_date=report_date)

    buf = io.StringIO()
    w = csv.writer(buf)

    label = report_date or "all-time"

    # ── Section 1: KPI Summary ────────────────────────────────────────────────
    w.writerow(["SMS DELIVERABILITY REPORT — KPI SUMMARY"])
    w.writerow(["Company", company_name])
    w.writerow(["Date", label])
    w.writerow([])

    if stats and stats["total"]:
        total     = stats["total"]
        delivered = stats["delivered"]
        failed    = stats["failed"]
        w.writerow(["Metric", "Value"])
        w.writerow(["Total Messages",  total])
        w.writerow(["Delivered",       delivered])
        w.writerow(["Failed",          failed])
        w.writerow(["Delivered Rate",  f"{rate_pct(delivered, total)}%"])
        w.writerow(["Failed Rate",     f"{rate_pct(failed, total)}%"])
        apm = avg_per_minute(total, stats["first_ts"], stats["last_ts"])
        w.writerow(["Avg SMS / min",   f"{apm:.1f}" if apm else "—"])
        w.writerow(["Campaign IDs",    stats["campaign_ids"] or ""])
    else:
        w.writerow(["No data for this period."])

    w.writerow([])

    # ── Section 2: Failure Breakdown ─────────────────────────────────────────
    w.writerow(["FAILURE BREAKDOWN"])
    w.writerow(["Carrier", "Error", "Failed Count", "% of Failures"])
    total_failed = stats["failed"] if stats else 0
    for f in failures:
        pct = f"{f['cnt'] / total_failed * 100:.1f}%" if total_failed else "—"
        w.writerow([f["carrier"], f["error"], f["cnt"], pct])

    w.writerow([])

    # ── Section 3: Message Records ────────────────────────────────────────────
    w.writerow(["MESSAGE RECORDS"])
    w.writerow(["Created On", "From", "To", "Segments", "Status",
                "Error Code", "Error Description", "Campaign ID", "Carrier", "Text"])
    for row in rows:
        w.writerow([
            row["created_on"], row["from_number"], row["to_number"],
            row["text_segment_count"], row["status"],
            row["error_code"], row["error_description"],
            row["campaign_id"], row["recipient_carrier_name"], row["text"],
        ])

    filename = f"telgorithm_{slugify(company_name)}_{label}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Send to Slack ─────────────────────────────────────────────────────────────

@bp.route("/send-slack", methods=["POST"])
def send_slack():
    report_date = request.form.get("date", "").strip() or _today()

    with get_conn() as conn:
        companies_raw = get_companies(conn, report_date=report_date)

    if not companies_raw:
        flash(f"No data for {report_date} — nothing sent.", "error")
        return redirect(url_for("telgorithm.reports", date=report_date))

    companies = []
    failures_by_company: dict[str, list] = {}

    with get_conn() as conn:
        for c in companies_raw:
            total     = c["total"]
            delivered = c["delivered"]
            failed    = c["failed"]
            name      = c["company_name"]
            companies.append({
                "name":           name,
                "total":          total,
                "delivered":      delivered,
                "failed":         failed,
                "delivered_rate": rate_pct(delivered, total),
                "failed_rate":    rate_pct(failed, total),
                "avg_per_min":    avg_per_minute(total, c["first_ts"], c["last_ts"]),
            })
            failures_by_company[name] = [
                dict(row) for row in get_failure_breakdown(conn, name, report_date=report_date)
            ]

    payload = slack_mod.build_payload(report_date, companies, failures_by_company)
    success, message = slack_mod.send(payload)

    flash(message, "success" if success else "error")
    return redirect(url_for("telgorithm.reports", date=report_date))
