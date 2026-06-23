import csv
import io
import uuid
from datetime import date as date_type, datetime, timedelta, timezone
from typing import Optional

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from sms_deliverability.commio.campaign_map import CAMPAIGN_MAP, SLUG_TO_COMPANY, slugify
from sms_deliverability.commio.error_codes import describe
from sms_deliverability.commio import slack as slack_mod
from sms_deliverability.commio.db import (
    count_company_records,
    get_available_dates,
    get_companies,
    get_company_records,
    get_company_stats,
    get_conn,
    get_failure_breakdown,
)

bp = Blueprint("commio", __name__, template_folder="templates")

REQUIRED_HEADERS = ["delivery_status_code", "created", "campaign_id"]

_ALIASES: dict[str, str] = {}
for _canonical, _variants in {
    "created":              ["created", "created_at", "createdat", "date", "datetime", "timestamp"],
    "from_did":             ["from_did", "from", "fromdid", "sender", "from_number"],
    "to_did":               ["to_did", "to", "todid", "recipient", "to_number"],
    "msg_count":            ["msg_count", "msgcount", "count", "segments", "message_count", "msg count"],
    "delivery_status_code": ["delivery_status_code", "deliverystatuscode", "status_code", "statuscode", "status", "delivery status code"],
    "campaign_id":          ["campaign_id", "campaignid", "campaign id", "campaignsid", "campaign_sid"],
    "carrier":              ["carrier", "carriername", "carrier_name", "network"],
    "direction":            ["direction", "msg_direction", "message_direction"],
}.items():
    for _v in _variants:
        _ALIASES[_v] = _canonical
    _ALIASES[_canonical.lower()] = _canonical


def _remap_fieldnames(fieldnames: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw in fieldnames:
        normalized = raw.strip().lower()
        canonical = _ALIASES.get(normalized)
        if canonical:
            mapping[raw] = canonical
    return mapping


def _normalize_row(row: dict, remap: dict[str, str]) -> dict[str, str]:
    return {remap.get(k, k): v for k, v in row.items()}


def _today() -> str:
    return date_type.today().isoformat()


def _rate_pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator * 100, 2)


def _avg_per_minute(total: int, first_ts: Optional[str], last_ts: Optional[str]) -> Optional[float]:
    if not total or not first_ts or not last_ts or first_ts == last_ts:
        return None
    fmts = [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in fmts:
        try:
            t0 = datetime.strptime(first_ts.strip(), fmt)
            t1 = datetime.strptime(last_ts.strip(), fmt)
            minutes = (t1 - t0).total_seconds() / 60
            return round(total / minutes, 2) if minutes > 0 else None
        except ValueError:
            continue
    return None


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
            weeks[key] = {
                "start": ws.isoformat(),
                "end": we.isoformat(),
                "count": 0,
                "label": f"{ws.strftime('%b %d')} – {we.strftime('%b %d')}",
            }
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


def _parse_view(available_dates: list) -> tuple[dict, str, str, str, str, list, list]:
    """
    Returns (kw, view, label, selected_date, selected_month, weeks, months).
    kw is passed directly to db functions (**kw).
    """
    view = request.args.get("view", "day")
    date_param = request.args.get("date", "").strip()
    month_param = request.args.get("month", "").strip()

    weeks = _dates_to_weeks(available_dates)
    months = _dates_to_months(available_dates)

    if view == "month":
        month = month_param or (date_param[:7] if len(date_param) >= 7 else "")
        if not month and months:
            month = months[0]["month"]
        return (
            {"month": month} if month else {},
            "month", month, "", month,
            weeks, months,
        )

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
        return (
            {"date_from": ws.isoformat(), "date_to": we.isoformat()},
            "week", label, ws.isoformat(), "",
            weeks, months,
        )

    # day (default)
    if not date_param and available_dates:
        date_param = available_dates[0]["report_date"]
    return (
        {"report_date": date_param} if date_param else {},
        "day", date_param, date_param, "",
        weeks, months,
    )


# ── Upload ────────────────────────────────────────────────────────────────────

@bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("commio/upload.html", today=_today())

    file = request.files.get("csv_file")
    if not file or file.filename == "":
        flash("No file selected.", "error")
        return render_template("commio/upload.html", today=_today())

    if not file.filename.lower().endswith(".csv"):
        flash("File must be a .csv file.", "error")
        return render_template("commio/upload.html", today=_today())

    report_date = request.form.get("report_date", "").strip() or _today()

    try:
        content = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("Could not read file — ensure it is UTF-8 encoded.", "error")
        return render_template("commio/upload.html", today=_today())

    reader = csv.DictReader(io.StringIO(content))
    raw_fieldnames = reader.fieldnames or []
    remap = _remap_fieldnames(raw_fieldnames)
    recognized = set(remap.values())
    missing = [h for h in REQUIRED_HEADERS if h not in recognized]
    if missing:
        found = ", ".join(raw_fieldnames) if raw_fieldnames else "(none)"
        flash(
            f"Missing required columns: {', '.join(missing)}. "
            f"Columns found in your CSV: {found}",
            "error",
        )
        return render_template("commio/upload.html", today=_today())

    batch_id = str(uuid.uuid4())
    imported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    rows = []
    for raw_row in reader:
        row = _normalize_row(raw_row, remap)
        campaign_id = row.get("campaign_id", "").strip()
        status_code = row.get("delivery_status_code", "").strip()
        rows.append((
            row.get("created", ""),
            row.get("from_did", ""),
            row.get("to_did", ""),
            row.get("msg_count", ""),
            status_code,
            describe(status_code),
            campaign_id,
            row.get("carrier", ""),
            row.get("direction", ""),
            batch_id,
            imported_at,
            CAMPAIGN_MAP.get(campaign_id),
            report_date,
        ))

    if not rows:
        flash("CSV has no data rows.", "error")
        return render_template("commio/upload.html", today=_today())

    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO commio_records
                (created, from_did, to_did, msg_count,
                 delivery_status_code, status_description,
                 campaign_id, carrier, direction,
                 batch_id, imported_at, company_name, report_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    mapped = sum(1 for r in rows if r[-2] is not None)
    flash(
        f"Imported {len(rows):,} records for {report_date} "
        f"({mapped:,} matched to a company).",
        "success",
    )
    return redirect(url_for("commio.reports", view="day", date=report_date))


# ── Company reports list ──────────────────────────────────────────────────────

@bp.route("/reports")
def reports():
    with get_conn() as conn:
        available_dates = get_available_dates(conn)
        kw, view, label, selected_date, selected_month, weeks, months = _parse_view(available_dates)
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
            "delivered_rate": _rate_pct(delivered, total),
            "failed_rate": _rate_pct(failed, total),
            "avg_per_min": _avg_per_minute(total, c["first_ts"], c["last_ts"]),
        })

    return render_template(
        "commio/reports.html",
        companies=companies,
        available_dates=available_dates,
        view=view,
        label=label,
        selected_date=selected_date,
        selected_month=selected_month,
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

    with get_conn() as conn:
        available_dates = get_available_dates(conn)
        kw, view, label, selected_date, selected_month, weeks, months = _parse_view(available_dates)
        stats = get_company_stats(conn, company_name, **kw)
        failures = get_failure_breakdown(conn, company_name, **kw)
        offset = (page - 1) * per_page
        rows = get_company_records(conn, company_name, limit=per_page, offset=offset, **kw)
        total_records = count_company_records(conn, company_name, **kw)

    ctx = dict(
        company_name=company_name, slug=slug,
        available_dates=available_dates,
        view=view, label=label,
        selected_date=selected_date, selected_month=selected_month,
        weeks=weeks, months=months,
        page=page, total_records=total_records,
    )

    if stats is None or stats["total"] == 0:
        return render_template("commio/report.html", kpi=None, failures=[], rows=[], total_pages=1, **ctx)

    total = stats["total"]
    delivered = stats["delivered"]
    failed = stats["failed"]
    kpi = {
        "total": total,
        "delivered": delivered,
        "failed": failed,
        "delivered_rate": _rate_pct(delivered, total),
        "failed_rate": _rate_pct(failed, total),
        "avg_per_min": _avg_per_minute(total, stats["first_ts"], stats["last_ts"]),
        "campaign_ids": (stats["campaign_ids"] or "").split(","),
    }
    total_pages = max(1, (total_records + per_page - 1) // per_page)
    return render_template("commio/report.html", kpi=kpi, failures=failures, rows=rows, total_pages=total_pages, **ctx)


# ── CSV Download ──────────────────────────────────────────────────────────────

@bp.route("/report/<slug>/download")
def download_csv(slug: str):
    company_name = SLUG_TO_COMPANY.get(slug)
    if not company_name:
        abort(404)

    with get_conn() as conn:
        available_dates = get_available_dates(conn)
        kw, _, label, _, _, _, _ = _parse_view(available_dates)
        label = label or "all-time"
        stats = get_company_stats(conn, company_name, **kw)
        failures = get_failure_breakdown(conn, company_name, **kw)
        rows = get_company_records(conn, company_name, limit=100_000, offset=0, **kw)

    buf = io.StringIO()
    w = csv.writer(buf)

    w.writerow(["COMMIO SMS DELIVERABILITY REPORT — KPI SUMMARY"])
    w.writerow(["Company", company_name])
    w.writerow(["Period", label])
    w.writerow([])

    if stats and stats["total"]:
        total = stats["total"]
        delivered = stats["delivered"]
        failed = stats["failed"]
        w.writerow(["Metric", "Value"])
        w.writerow(["Total Messages", total])
        w.writerow(["Delivered (200)", delivered])
        w.writerow(["Failed", failed])
        w.writerow(["Delivered Rate", f"{_rate_pct(delivered, total)}%"])
        w.writerow(["Failed Rate", f"{_rate_pct(failed, total)}%"])
        apm = _avg_per_minute(total, stats["first_ts"], stats["last_ts"])
        w.writerow(["Avg SMS / min", f"{apm:.1f}" if apm else "—"])
        w.writerow(["Campaign IDs", stats["campaign_ids"] or ""])
    else:
        w.writerow(["No data for this period."])

    w.writerow([])
    w.writerow(["FAILURE BREAKDOWN"])
    w.writerow(["Carrier", "Status Code", "Description", "Failed Count", "% of Failures"])
    total_failed = stats["failed"] if stats else 0
    for f in failures:
        pct = f"{f['cnt'] / total_failed * 100:.1f}%" if total_failed else "—"
        w.writerow([f["carrier"], f["status_code"], f["error"], f["cnt"], pct])

    w.writerow([])
    w.writerow(["MESSAGE RECORDS"])
    w.writerow(["Created", "From DID", "To DID", "Msg Count",
                "Status Code", "Status Description", "Campaign ID", "Carrier", "Direction"])
    for row in rows:
        w.writerow([
            row["created"], row["from_did"], row["to_did"],
            row["msg_count"], row["delivery_status_code"], row["status_description"],
            row["campaign_id"], row["carrier"], row["direction"],
        ])

    filename = f"commio_{slugify(company_name)}_{label}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Send to Slack ─────────────────────────────────────────────────────────────

@bp.route("/send-slack", methods=["POST"])
def send_slack():
    view        = request.form.get("view", "day")
    date_param  = request.form.get("date", "").strip()
    month_param = request.form.get("month", "").strip()

    with get_conn() as conn:
        available_dates = get_available_dates(conn)

    # Build kw from form values
    from datetime import timedelta
    if view == "month" and month_param:
        kw = {"month": month_param}
        label = month_param
    elif view == "week" and date_param:
        try:
            from datetime import date as _d
            d = _d.fromisoformat(date_param)
        except ValueError:
            from datetime import date as _d
            d = _d.today()
        ws = d - timedelta(days=d.weekday())
        we = ws + timedelta(days=6)
        kw = {"date_from": ws.isoformat(), "date_to": we.isoformat()}
        label = f"{ws.strftime('%b %d')} – {we.strftime('%b %d, %Y')}"
    else:
        kw = {"report_date": date_param} if date_param else {}
        label = date_param or "all-time"

    with get_conn() as conn:
        companies_raw = get_companies(conn, **kw)

    if not companies_raw:
        flash(f"No data for {label} — nothing sent.", "error")
        return redirect(url_for("commio.reports", view=view, date=date_param, month=month_param))

    companies = []
    failures_by_company: dict[str, list] = {}
    with get_conn() as conn:
        for c in companies_raw:
            total = c["total"]
            delivered = c["delivered"]
            failed = c["failed"]
            name = c["company_name"]
            companies.append({
                "name": name,
                "total": total,
                "delivered": delivered,
                "failed": failed,
                "delivered_rate": _rate_pct(delivered, total),
                "failed_rate": _rate_pct(failed, total),
                "avg_per_min": _avg_per_minute(total, c["first_ts"], c["last_ts"]),
            })
            failures_by_company[name] = [
                dict(r) for r in get_failure_breakdown(conn, name, **kw)
            ]

    payload = slack_mod.build_payload(label, companies, failures_by_company)
    success, message = slack_mod.send(payload)

    flash(message, "success" if success else "error")
    return redirect(url_for("commio.reports", view=view, date=date_param, month=month_param))


# ── Campaign Checker ──────────────────────────────────────────────────────────

@bp.route("/campaigns")
def campaigns():
    from sms_deliverability.telgorithm.campaign_map import CAMPAIGN_MAP as TEL_MAP
    from sms_deliverability.signalmash.campaign_map import CAMPAIGN_MAP as SIG_MAP

    query = request.args.get("q", "").strip()
    q_lower = query.lower()

    # Build unified cross-provider matrix keyed by campaign ID
    all_ids: dict[str, dict] = {}

    def _register(cid: str, name: str, provider: str) -> None:
        if cid not in all_ids:
            all_ids[cid] = {
                "id": cid,
                "company": name,
                "in_telgorithm": False,
                "in_signalmash": False,
                "in_commio": False,
                "conflict": False,
            }
        entry = all_ids[cid]
        entry[f"in_{provider}"] = True
        if entry["company"] != name:
            entry["conflict"] = True

    for cid, name in TEL_MAP.items():
        _register(cid, name, "telgorithm")
    for cid, name in SIG_MAP.items():
        _register(cid, name, "signalmash")
    for cid, name in CAMPAIGN_MAP.items():
        _register(cid, name, "commio")

    rows = sorted(all_ids.values(), key=lambda r: (r["company"], r["id"]))

    # Apply search filter
    if q_lower:
        rows = [r for r in rows if q_lower in r["id"].lower() or q_lower in r["company"].lower()]

    # Summary stats
    complete = sum(1 for r in rows if r["in_telgorithm"] and r["in_signalmash"] and r["in_commio"])
    incomplete = len(rows) - complete
    conflicts = sum(1 for r in rows if r["conflict"])

    # Unmapped campaign IDs found in Commio DB uploads
    with get_conn() as conn:
        unmapped_rows = conn.execute("""
            SELECT campaign_id, COUNT(*) AS total
              FROM commio_records
             WHERE (company_name IS NULL OR company_name = '')
               AND campaign_id IS NOT NULL
               AND campaign_id != ''
             GROUP BY campaign_id
             ORDER BY total DESC
        """).fetchall()

    unmapped = [dict(r) for r in unmapped_rows]
    if q_lower:
        unmapped = [u for u in unmapped if q_lower in u["campaign_id"].lower()]

    return render_template(
        "commio/campaigns.html",
        rows=rows,
        unmapped=unmapped,
        query=query,
        total_ids=len(rows),
        complete=complete,
        incomplete=incomplete,
        conflicts=conflicts,
    )
