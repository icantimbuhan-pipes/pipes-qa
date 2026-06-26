import csv
import io
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
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
from sms_deliverability.signalmash import slack as slack_mod
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
            # Normalize DLR code columns — handle plain "0", "201" and
            # parenthesized format "(000)", "(321)" from Signalmash exports.
            stripped = raw.strip().strip("()")
            try:
                out[raw] = str(int(stripped))  # "(000)" → "0", "(045)" → "45"
            except ValueError:
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

    report_date = date_param or (available_dates[0]["report_date"] if available_dates else "")
    label = report_date
    return ({"report_date": report_date} if report_date else {}, "day", label,
            report_date, "", weeks, months)


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
    with get_conn() as conn:
        available_dates = get_available_dates(conn)
    kw, view, label, selected_date, selected_month, weeks, months = _parse_view(available_dates)

    with get_conn() as conn:
        companies_raw = get_companies(conn, **kw)

    companies = []
    for c in companies_raw:
        total, delivered, failed = c["total"], c["delivered"], c["failed"]
        companies.append({
            "name": c["company_name"],
            "slug": slugify(c["company_name"]),
            "total": total, "delivered": delivered, "failed": failed,
            "delivered_rate": rate_pct(delivered, total),
            "failed_rate": rate_pct(failed, total),
        })

    return render_template(
        "signalmash/reports.html",
        companies=companies,
        available_dates=available_dates,
        selected_date=selected_date,
        selected_month=selected_month,
        view=view, label=label, weeks=weeks, months=months,
    )


# ── Per-company report ────────────────────────────────────────────────────────

@bp.route("/report/<slug>")
def report(slug: str):
    company_name = SLUG_TO_COMPANY.get(slug)
    if not company_name:
        abort(404)

    page = max(1, request.args.get("page", 1, type=int))
    per_page = 200
    offset = (page - 1) * per_page

    with get_conn() as conn:
        available_dates = get_available_dates(conn)
    kw, view, label, selected_date, selected_month, weeks, months = _parse_view(available_dates)

    with get_conn() as conn:
        stats        = get_company_stats(conn, company_name, **kw)
        failures     = get_failure_breakdown(conn, company_name, **kw)
        rows         = get_company_records(conn, company_name, limit=per_page, offset=offset, **kw)
        total_records = count_company_records(conn, company_name, **kw)

    shared = dict(
        company_name=company_name, slug=slug,
        available_dates=available_dates, selected_date=selected_date,
        selected_month=selected_month, view=view, label=label, weeks=weeks, months=months,
    )

    if stats is None or stats["total"] == 0:
        return render_template("signalmash/report.html",
            kpi=None, failures=[], rows=[], page=1, total_pages=1, total_records=0, **shared)

    total, delivered, failed = stats["total"], stats["delivered"], stats["failed"]
    kpi = {
        "total": total, "delivered": delivered, "failed": failed,
        "delivered_rate": rate_pct(delivered, total),
        "failed_rate": rate_pct(failed, total),
        "campaign_ids": (stats["campaign_ids"] or "").split(","),
    }
    total_pages = max(1, (total_records + per_page - 1) // per_page)
    return render_template("signalmash/report.html",
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


# ── Send to Slack ─────────────────────────────────────────────────────────────

@bp.route("/send-slack", methods=["POST"])
def send_slack():
    report_date = request.form.get("date", "").strip() or _today()

    with get_conn() as conn:
        companies_raw = get_companies(conn, report_date=report_date)

    if not companies_raw:
        flash(f"No data for {report_date} — nothing sent.", "error")
        return redirect(url_for("signalmash.reports", date=report_date))

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
            })
            failures_by_company[name] = [
                dict(row) for row in get_failure_breakdown(conn, name, report_date=report_date)
            ]

    payload = slack_mod.build_payload(report_date, companies, failures_by_company)
    success, message = slack_mod.send(payload)

    flash(message, "success" if success else "error")
    return redirect(url_for("signalmash.reports", date=report_date))


# ── Analysis ──────────────────────────────────────────────────────────────────

@bp.route("/analysis")
def analysis():
    from sms_deliverability.analysis_kb import (
        get_signalmash, delivery_status, SEVERITY_BADGE, STATUS_BADGE, SEVERITY_ORDER
    )

    period = request.args.get("period", "month")

    with get_conn() as conn:
        available_dates = get_available_dates(conn)

    if not available_dates:
        return render_template("signalmash/analysis.html",
            period=period, overall=None, companies=[], top_codes=[], action_items=[])

    all_dates = [r["report_date"] for r in available_dates]
    latest    = max(all_dates)

    if period == "month":
        month_str   = latest[:7]
        date_filter = {"report_date": latest}
        # Use full month data
        kw_companies = {"date_from": f"{month_str}-01", "date_to": latest}
        period_label = datetime.strptime(month_str, "%Y-%m").strftime("%B %Y")
    elif period == "3months":
        from datetime import timedelta
        cutoff = (date_type.fromisoformat(latest) - timedelta(days=90)).isoformat()
        kw_companies = {"date_from": cutoff, "date_to": latest}
        date_filter  = kw_companies
        period_label = f"Last 3 months (to {latest})"
    else:
        kw_companies = {}
        date_filter  = {}
        period_label = "All time"

    with get_conn() as conn:
        companies_raw = get_companies(conn, **kw_companies)

    companies = []
    all_failure_counts: dict[str, int] = {}

    with get_conn() as conn:
        for c in companies_raw:
            total, delivered, failed = c["total"], c["delivered"], c["failed"]
            rate = rate_pct(delivered, total)
            name = c["company_name"]

            failures_raw = get_failure_breakdown(conn, name, **kw_companies)
            agg_failures: dict[str, dict] = {}
            for f in failures_raw:
                code = f["dlr_code"]
                kb   = get_signalmash(code)
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

    companies.sort(key=lambda c: (
        {"critical": 0, "warning": 1, "healthy": 2}[c["status"]],
        -c["total"]
    ))

    total_all     = sum(c["total"] for c in companies)
    delivered_all = sum(c["delivered"] for c in companies)
    failed_all    = sum(c["failed"] for c in companies)
    overall_rate  = rate_pct(delivered_all, total_all)
    overall_status = delivery_status(overall_rate)

    top_codes = sorted(
        [{"code": k, "count": v,
          "pct": round(v * 100.0 / failed_all, 1) if failed_all else 0,
          **get_signalmash(k)}
         for k, v in all_failure_counts.items()],
        key=lambda x: -x["count"]
    )[:8]
    for tc in top_codes:
        tc["badge"] = SEVERITY_BADGE.get(tc["severity"], ("", ""))

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

    return render_template("signalmash/analysis.html",
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
    """Return (kpi, failures, action_items, period_label) for one company."""
    from sms_deliverability.analysis_kb import (
        get_signalmash, delivery_status, SEVERITY_BADGE, STATUS_BADGE, SEVERITY_ORDER
    )

    with get_conn() as conn:
        available_dates = get_available_dates(conn)

    all_dates = [r["report_date"] for r in available_dates] if available_dates else []
    if not all_dates:
        return None, [], [], ""

    latest = max(all_dates)

    if period == "month":
        month_str   = latest[:7]
        date_filter = {"date_from": f"{month_str}-01", "date_to": latest}
        period_label = date_type.fromisoformat(f"{month_str}-01").strftime("%B %Y")
    elif period == "3months":
        cutoff = (date_type.fromisoformat(latest) - timedelta(days=90)).isoformat()
        date_filter  = {"date_from": cutoff, "date_to": latest}
        period_label = f"Last 3 months (to {latest})"
    else:
        date_filter  = {}
        period_label = "All time"

    with get_conn() as conn:
        stats        = get_company_stats(conn, company_name, **date_filter)
        failures_raw = get_failure_breakdown(conn, company_name, **date_filter)

    if stats is None or stats["total"] == 0:
        return None, [], [], period_label

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
        code = f["dlr_code"]
        kb   = get_signalmash(code)
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

    return kpi, failures, action_items, period_label


@bp.route("/analysis/<slug>")
def company_analysis(slug: str):
    company_name = SLUG_TO_COMPANY.get(slug)
    if not company_name:
        abort(404)

    period = request.args.get("period", "month")
    kpi, failures, action_items, period_label = _build_company_analysis_data(company_name, period)

    return render_template("signalmash/company_analysis.html",
        company_name=company_name, slug=slug,
        period=period, period_label=period_label,
        kpi=kpi, failures=failures, action_items=action_items,
    )


@bp.route("/analysis/<slug>/send-slack", methods=["POST"])
def company_analysis_slack(slug: str):
    company_name = SLUG_TO_COMPANY.get(slug)
    if not company_name:
        abort(404)

    period = request.form.get("period", "month")
    kpi, failures, _, period_label = _build_company_analysis_data(company_name, period)

    if kpi is None:
        flash("No data for this period.", "error")
        return redirect(url_for("signalmash.company_analysis", slug=slug, period=period))

    payload = slack_mod.build_company_payload(company_name, period_label, kpi, failures)
    success, message = slack_mod.send(payload)
    flash(message, "success" if success else "error")
    return redirect(url_for("signalmash.company_analysis", slug=slug, period=period))
