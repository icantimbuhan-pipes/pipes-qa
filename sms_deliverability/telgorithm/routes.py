import csv
import io
import os
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from sms_deliverability.telgorithm.campaign_map import CAMPAIGN_MAP, SLUG_TO_COMPANY, slugify
from sms_deliverability.telgorithm import slack as slack_mod
from sms_deliverability.telgorithm.db import (
    count_all_records,
    count_company_records,
    get_all_records,
    get_available_dates,
    get_blocked_number_breakdown,
    get_companies,
    get_company_records,
    get_company_stats,
    get_conn,
    get_failed_message_samples,
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


# ── Analysis ──────────────────────────────────────────────────────────────────

@bp.route("/analysis")
def analysis():
    from sms_deliverability.analysis_kb import (
        get_telgorithm, delivery_status, SEVERITY_BADGE, STATUS_BADGE, SEVERITY_ORDER
    )

    period = request.args.get("period", "month")  # month | 3months | all

    with get_conn() as conn:
        available_dates = get_available_dates(conn)

    if not available_dates:
        return render_template("telgorithm/analysis.html",
            period=period, overall=None, companies=[], top_codes=[], action_items=[])

    # Build date filter
    all_dates = [r["report_date"] for r in available_dates]
    latest    = max(all_dates)

    if period == "month":
        month_str  = latest[:7]
        date_filter = {"date_from": f"{month_str}-01", "date_to": latest}
        period_label = datetime.strptime(month_str, "%Y-%m").strftime("%B %Y")
    elif period == "3months":
        cutoff = (datetime.strptime(latest, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
        date_filter = {"date_from": cutoff, "date_to": latest}
        period_label = f"Last 3 months (to {latest})"
    else:
        date_filter  = {}
        period_label = "All time"

    with get_conn() as conn:
        companies_raw = get_companies(conn, **date_filter)

    # Per-company KPI + failure breakdown
    companies = []
    all_failure_counts: dict[str, int] = {}

    with get_conn() as conn:
        for c in companies_raw:
            total, delivered, failed = c["total"], c["delivered"], c["failed"]
            rate = rate_pct(delivered, total)
            name = c["company_name"]

            failures_raw = get_failure_breakdown(conn, name, **date_filter)
            agg_failures: dict[str, dict] = {}
            for f in failures_raw:
                code = f["error"] if f["error"] else "UnknownError"
                kb   = get_telgorithm(code)
                cnt  = f["cnt"]
                if code in agg_failures:
                    agg_failures[code]["count"] += cnt
                else:
                    agg_failures[code] = {
                        "code":       code,
                        "label":      kb["label"],
                        "count":      cnt,
                        "severity":   kb["severity"],
                        "category":   kb["category"],
                        "root_cause": kb["root_cause"],
                        "action":     kb["action"],
                        "badge":      SEVERITY_BADGE.get(kb["severity"], ("", "")),
                    }
                all_failure_counts[code] = all_failure_counts.get(code, 0) + cnt
            failures = sorted(agg_failures.values(), key=lambda x: -x["count"])
            for f in failures:
                f["pct"] = round(f["count"] * 100.0 / failed, 1) if failed else 0

            status = delivery_status(rate)
            companies.append({
                "name":     name,
                "slug":     slugify(name),
                "total":    total,
                "delivered": delivered,
                "failed":   failed,
                "rate":     rate,
                "status":   status,
                "status_badge": STATUS_BADGE[status],
                "failures": failures[:5],
                "top_failure": failures[0] if failures else None,
            })

    # Sort: critical first, then by total desc
    companies.sort(key=lambda c: (
        {"critical": 0, "warning": 1, "healthy": 2}[c["status"]],
        -c["total"]
    ))

    # Overall KPI
    total_all     = sum(c["total"] for c in companies)
    delivered_all = sum(c["delivered"] for c in companies)
    failed_all    = sum(c["failed"] for c in companies)
    overall_rate  = rate_pct(delivered_all, total_all)
    overall_status = delivery_status(overall_rate)

    # Top failure codes across all companies
    top_codes = sorted(
        [{"code": k, "count": v,
          "pct": round(v * 100.0 / failed_all, 1) if failed_all else 0,
          **get_telgorithm(k)}
         for k, v in all_failure_counts.items()],
        key=lambda x: -x["count"]
    )[:8]
    for tc in top_codes:
        tc["badge"] = SEVERITY_BADGE.get(tc["severity"], ("", ""))

    # Action items: deduplicated actions ranked by total affected messages
    seen_actions: set[str] = set()
    action_items = []
    for tc in sorted(top_codes, key=lambda x: SEVERITY_ORDER.get(x["severity"], 99)):
        if tc["action"] and tc["action"] not in seen_actions:
            seen_actions.add(tc["action"])
            action_items.append({
                "code":     tc["code"],
                "label":    tc["label"],
                "severity": tc["severity"],
                "badge":    tc["badge"],
                "count":    tc["count"],
                "action":   tc["action"],
            })
        if len(action_items) >= 6:
            break

    return render_template("telgorithm/analysis.html",
        period=period,
        period_label=period_label,
        overall={
            "total": total_all, "delivered": delivered_all, "failed": failed_all,
            "rate": overall_rate, "status": overall_status,
            "status_badge": STATUS_BADGE[overall_status],
        },
        companies=companies,
        top_codes=top_codes,
        action_items=action_items,
    )


# ── Per-company analysis ──────────────────────────────────────────────────────

def _build_company_analysis_data(company_name: str, period: str):
    """Return (kpi, failures, action_items, period_label, blocked_numbers, content_patterns)."""
    from collections import defaultdict
    from sms_deliverability.analysis_kb import (
        get_telgorithm, delivery_status, SEVERITY_BADGE, STATUS_BADGE, SEVERITY_ORDER
    )

    with get_conn() as conn:
        available_dates = get_available_dates(conn)

    all_dates = [r["report_date"] for r in available_dates] if available_dates else []
    if not all_dates:
        return None, [], [], "", [], []

    latest = max(all_dates)

    if period == "month":
        month_str   = latest[:7]
        date_filter = {"date_from": f"{month_str}-01", "date_to": latest}
        period_label = datetime.strptime(month_str, "%Y-%m").strftime("%B %Y")
    elif period == "3months":
        cutoff = (datetime.strptime(latest, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
        date_filter  = {"date_from": cutoff, "date_to": latest}
        period_label = f"Last 3 months (to {latest})"
    else:
        date_filter  = {}
        period_label = "All time"

    with get_conn() as conn:
        stats           = get_company_stats(conn, company_name, **date_filter)
        failures_raw    = get_failure_breakdown(conn, company_name, **date_filter)
        blocked_raw     = get_blocked_number_breakdown(conn, company_name, **date_filter)
        content_raw     = get_failed_message_samples(conn, company_name, **date_filter)

    if stats is None or stats["total"] == 0:
        return None, [], [], period_label, [], []

    total, delivered, failed = stats["total"], stats["delivered"], stats["failed"]
    rate   = rate_pct(delivered, total)
    status = delivery_status(rate)

    kpi = {
        "total": total, "delivered": delivered, "failed": failed,
        "rate": rate, "status": status,
        "status_badge": STATUS_BADGE[status],
    }

    agg_failures: dict[str, dict] = {}
    for f in failures_raw:
        code = f["error"] if f["error"] else "UnknownError"
        kb   = get_telgorithm(code)
        cnt  = f["cnt"]
        if code in agg_failures:
            agg_failures[code]["count"] += cnt
        else:
            agg_failures[code] = {
                "code":       code,
                "label":      kb["label"],
                "count":      cnt,
                "severity":   kb["severity"],
                "category":   kb["category"],
                "root_cause": kb["root_cause"],
                "action":     kb["action"],
                "badge":      SEVERITY_BADGE.get(kb["severity"], ("", "")),
            }
    failures = sorted(agg_failures.values(), key=lambda x: -x["count"])
    for f in failures:
        f["pct"] = round(f["count"] * 100.0 / failed, 1) if failed else 0

    seen_actions: set[str] = set()
    action_items = []
    for f in sorted(failures, key=lambda x: SEVERITY_ORDER.get(x["severity"], 99)):
        if f["action"] and f["action"] not in seen_actions:
            seen_actions.add(f["action"])
            action_items.append({
                "code": f["code"], "label": f["label"],
                "severity": f["severity"], "badge": f["badge"],
                "count": f["count"], "action": f["action"],
            })

    # ── Aggregate blocked sender numbers ─────────────────────────────────────
    num_data: dict = defaultdict(lambda: {
        "total": 0, "carriers": defaultdict(int),
        "top_code": "", "top_code_desc": "", "top_code_count": 0,
    })
    for row in blocked_raw:
        n = row["from_number"]
        num_data[n]["total"] += row["blocked_count"]
        num_data[n]["carriers"][row["carrier"]] += row["blocked_count"]
        if row["blocked_count"] > num_data[n]["top_code_count"]:
            num_data[n]["top_code"]       = row["error_code"]
            num_data[n]["top_code_desc"]  = row["error_description"] or row["error_code"]
            num_data[n]["top_code_count"] = row["blocked_count"]

    blocked_numbers = []
    for num, data in sorted(num_data.items(), key=lambda x: -x[1]["total"])[:15]:
        top_carrier   = max(data["carriers"], key=data["carriers"].get) if data["carriers"] else "Unknown"
        carrier_count = len(data["carriers"])
        blocked_numbers.append({
            "number":        num,
            "blocked_count": data["total"],
            "top_carrier":   top_carrier,
            "carrier_count": carrier_count,
            "top_code":      data["top_code"],
            "top_code_desc": data["top_code_desc"],
            "needs_rotation": carrier_count >= 2,
        })

    # ── Message content patterns ──────────────────────────────────────────────
    content_patterns = [
        {
            "text":          row["text"],
            "fail_count":    row["fail_count"],
            "top_carrier":   row["top_carrier"],
            "top_error":     row["top_error_code"],
        }
        for row in content_raw if row["text"]
    ]

    return kpi, failures, action_items, period_label, blocked_numbers, content_patterns


@bp.route("/analysis/<slug>")
def company_analysis(slug: str):
    company_name = SLUG_TO_COMPANY.get(slug)
    if not company_name:
        abort(404)

    period = request.args.get("period", "month")
    kpi, failures, action_items, period_label, blocked_numbers, content_patterns = \
        _build_company_analysis_data(company_name, period)

    return render_template("telgorithm/company_analysis.html",
        company_name=company_name, slug=slug,
        period=period, period_label=period_label,
        kpi=kpi, failures=failures, action_items=action_items,
        blocked_numbers=blocked_numbers, content_patterns=content_patterns,
    )


def _generate_blocked_csv(company_name: str, period_label: str, blocked_numbers: list, content_patterns: list) -> str:
    """Generate CSV for blocked numbers + message content patterns."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([f"BLOCKED SENDER NUMBERS — {company_name}"])
    w.writerow([f"Period: {period_label}"])
    w.writerow([])
    w.writerow(["From Number", "Total Blocked", "Top Carrier", "Carriers Blocking", "Top Error Code", "Error Description", "Recommended Action"])
    for n in blocked_numbers:
        w.writerow([
            n["number"], n["blocked_count"], n["top_carrier"],
            n["carrier_count"], n["top_code"], n["top_code_desc"],
            "Replace number" if n["needs_rotation"] else "Monitor",
        ])
    if content_patterns:
        w.writerow([])
        w.writerow(["MESSAGE CONTENT PATTERNS (Failed Sends)"])
        w.writerow(["Message Text", "Failed Sends", "Top Carrier", "Top Error Code"])
        for p in content_patterns:
            w.writerow([p["text"], p["fail_count"], p["top_carrier"], p["top_error"]])
    return buf.getvalue()


def _upload_csv_to_slack(channel_id: str, bot_token: str, filename: str, csv_data: str, comment: str = "") -> tuple[bool, str]:
    """Upload a CSV file to Slack using the bot token."""
    try:
        resp = httpx.post(
            "https://slack.com/api/files.upload",
            headers={"Authorization": f"Bearer {bot_token}"},
            data={"channels": channel_id, "filename": filename, "filetype": "csv", "initial_comment": comment},
            files={"file": (filename, csv_data.encode("utf-8"), "text/csv")},
            timeout=30,
        )
        result = resp.json()
        if result.get("ok"):
            return True, f"CSV file uploaded to Slack: {filename}"
        return False, f"Slack file upload: {result.get('error', 'unknown error')}"
    except Exception as exc:
        return False, f"File upload failed: {exc}"


@bp.route("/analysis/<slug>/blocked-csv")
def blocked_csv_download(slug: str):
    company_name = SLUG_TO_COMPANY.get(slug)
    if not company_name:
        abort(404)
    period = request.args.get("period", "month")
    _, _, _, period_label, blocked_numbers, content_patterns = _build_company_analysis_data(company_name, period)
    csv_data = _generate_blocked_csv(company_name, period_label, blocked_numbers, content_patterns)
    filename = f"blocked_numbers_{slugify(company_name)}_{period}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/analysis/<slug>/send-slack", methods=["POST"])
def company_analysis_slack(slug: str):
    company_name = SLUG_TO_COMPANY.get(slug)
    if not company_name:
        abort(404)

    period = request.form.get("period", "month")
    kpi, failures, _, period_label, blocked_numbers, content_patterns = \
        _build_company_analysis_data(company_name, period)

    if kpi is None:
        flash("No data for this period.", "error")
        return redirect(url_for("telgorithm.company_analysis", slug=slug, period=period))

    payload = slack_mod.build_company_payload(company_name, period_label, kpi, failures)
    success, message = slack_mod.send(payload)
    flash(message, "success" if success else "error")

    # Upload blocked numbers + content CSV if channel ID and bot token are configured
    if success and blocked_numbers:
        channel_id = os.environ.get("SMS_SLACK_CHANNEL_ID", "").strip()
        bot_token  = os.environ.get("SLACK_BOT_TOKEN", "").strip()
        if channel_id and bot_token:
            csv_data = _generate_blocked_csv(company_name, period_label, blocked_numbers, content_patterns)
            filename = f"blocked_numbers_{slugify(company_name)}_{period}.csv"
            comment  = (
                f"📋 Blocked numbers + content analysis for *{company_name}* ({period_label}) — "
                f"{len(blocked_numbers)} numbers flagged"
                + (f", {len(content_patterns)} message templates" if content_patterns else "")
            )
            ok, msg  = _upload_csv_to_slack(channel_id, bot_token, filename, csv_data, comment)
            flash(msg, "success" if ok else "error")

    return redirect(url_for("telgorithm.company_analysis", slug=slug, period=period))
