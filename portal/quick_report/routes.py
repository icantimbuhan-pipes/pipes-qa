import os

import httpx
from dotenv import dotenv_values
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

bp = Blueprint("quick_report", __name__, template_folder="templates")


def _get_context():
    from portal.daily_qa.report_builder import _fetch_khomp_classification, _now_eastern
    from datetime import datetime
    dt = _now_eastern()
    try:
        khomp_class = _fetch_khomp_classification()
    except Exception:
        khomp_class = ""
    return {
        "date_str":   dt.strftime("%m/%d/%Y"),
        "time_str":   dt.strftime("%I:%M %p"),
        "khomp_class": khomp_class,
    }


@bp.route("/")
def index():
    ctx = _get_context()
    return render_template("quick_report/index.html", **ctx)


@bp.route("/refresh")
def refresh():
    return jsonify(_get_context())


@bp.route("/send", methods=["POST"])
def send():
    draft_text = request.form.get("draft_text", "").strip()
    if not draft_text:
        flash("Draft is empty.", "error")
        return redirect(url_for("quick_report.index"))

    env     = dotenv_values(".env")
    webhook = env.get("SLACK_WEBHOOK_URL") or os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook:
        flash("SLACK_WEBHOOK_URL not set in .env.", "error")
        return redirect(url_for("quick_report.index"))

    try:
        httpx.post(webhook, json={"text": draft_text}, timeout=15)
        flash("Report sent to Slack.", "success")
    except Exception as exc:
        flash(f"Slack send failed: {exc}", "error")

    return redirect(url_for("quick_report.index"))
