import importlib
from datetime import datetime
from typing import Optional

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from portal.db import (
    create_session, finish_session, get_answers, get_session,
    list_sessions, mark_slack_sent, save_answer,
)
from runner.interactive import CHECKLISTS
from runner.report import send_slack_report

bp = Blueprint("daily_qa", __name__, template_folder="templates")

PROVIDER_MAP = {
    "heavy_khomp":         "providers.heavy_khomp",
    "heavy_khomp_dynamic": "providers.heavy_khomp_dynamic",
    "lite_khomp":          "providers.lite_khomp",
    "tbi_khomp":           "providers.tbi_khomp",
    "tbi_fs":              "providers.tbi_fs",
    "signalmash_khomp":    "providers.signalmash_khomp",
    "signalmash_fs":       "providers.signalmash_fs",
    "accident_office":     "providers.accident_office",
    "sms_signalmash":      "providers.sms_signalmash",
    "sms_ai_signalmash":   "providers.sms_ai_signalmash",
}


def _flat_items(checklist) -> list:
    """Flatten checklist sections+items into a list of dicts for wizard use."""
    items = []
    for sec in checklist:
        for idx, item in enumerate(sec.items):
            items.append({
                "section_title":         sec.title,
                "section_trigger_call":  getattr(sec, "trigger_call_at_start", False),
                "section_instruction":   getattr(sec, "start_instruction", "") or "",
                "section_provider_key":  getattr(sec, "provider_key", "") or "",
                "item_id":               item.id,
                "item_text":             item.text,
                "item_note":             getattr(item, "note", "") or "",
                "item_bullets":          getattr(item, "bullets", []) or [],
                "item_trigger_call":     getattr(item, "trigger_call", False),
                "item_call_instruction": getattr(item, "call_instruction", "") or "",
                "item_sub_calls": [
                    {
                        "instruction": s.instruction,
                        "note":        getattr(s, "note", "") or "",
                    }
                    for s in getattr(item, "sub_calls", [])
                ],
                "item_provider_key":     getattr(item, "provider_key", "") or "",
                "is_first_in_section":   idx == 0,
            })
    return items


def _load_checklist(key: str):
    entry = next((cl for cl in CHECKLISTS if cl["key"] == key), None)
    if not entry:
        return None, None
    mod = importlib.import_module(entry["module"])
    return entry, getattr(mod, entry["attr"])


def _build_results_dict(session, answers) -> dict:
    """Build the dict format expected by runner/report.py send_slack_report."""
    sections: dict = {}
    for ans in answers:
        title = ans["section_title"]
        if title not in sections:
            sections[title] = {"title": title, "items": []}
        sections[title]["items"].append({
            "id":     ans["item_id"],
            "text":   ans["item_text"],
            "passed": bool(ans["passed"]),
            "note":   ans["note"] or "",
        })

    all_items    = [i for s in sections.values() for i in s["items"]]
    passed_count = sum(1 for i in all_items if i["passed"])

    return {
        "checklist":      session["checklist_name"],
        "checklist_key":  session["checklist_key"],
        "provider":       session["checklist_name"],
        "provider_key":   session["checklist_key"].replace("-", "_"),
        "started_at":     session["started_at"],
        "finished_at":    session["finished_at"] or datetime.now().isoformat(),
        "sections":       list(sections.values()),
        "passed":         passed_count,
        "total":          len(all_items),
        "monitoring":     {},
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@bp.route("/")
def pick():
    preset = request.args.get("preset", "")
    recent = list_sessions(8)
    return render_template("daily_qa/pick.html", checklists=CHECKLISTS, preset=preset, recent=recent)


@bp.route("/start", methods=["POST"])
def start():
    key   = request.form.get("checklist_key", "")
    entry = next((cl for cl in CHECKLISTS if cl["key"] == key), None)
    if not entry:
        flash("Unknown checklist.", "error")
        return redirect(url_for("daily_qa.pick"))
    session_id = create_session(key, entry["name"], entry.get("report_type", "daily"))
    return redirect(url_for("daily_qa.step", session_id=session_id, n=0))


@bp.route("/session/<session_id>/step/<int:n>", methods=["GET"])
def step(session_id: str, n: int):
    session = get_session(session_id)
    if not session:
        flash("Session not found.", "error")
        return redirect(url_for("daily_qa.pick"))

    entry, checklist = _load_checklist(session["checklist_key"])
    if not checklist:
        flash("Checklist not found.", "error")
        return redirect(url_for("daily_qa.pick"))

    items = _flat_items(checklist)
    total = len(items)

    # Skip already-answered items
    answered_idxs = {a["item_idx"] for a in get_answers(session_id)}
    while n < total and n in answered_idxs:
        n += 1

    if n >= total:
        finish_session(session_id)
        return redirect(url_for("daily_qa.summary", session_id=session_id))

    item         = items[n]
    default_pkey = entry["default_provider"]
    provider_key = item["item_provider_key"] or item["section_provider_key"] or default_pkey

    return render_template(
        "daily_qa/step.html",
        session=session,
        item=item,
        item_num=n,
        total=total,
        answered=len(answered_idxs),
        provider_key=provider_key,
    )


@bp.route("/session/<session_id>/step/<int:n>", methods=["POST"])
def answer(session_id: str, n: int):
    session = get_session(session_id)
    if not session:
        return redirect(url_for("daily_qa.pick"))

    entry, checklist = _load_checklist(session["checklist_key"])
    if not checklist:
        return redirect(url_for("daily_qa.pick"))

    items = _flat_items(checklist)
    if n >= len(items):
        return redirect(url_for("daily_qa.summary", session_id=session_id))

    item   = items[n]
    passed = request.form.get("passed") == "1"
    note   = request.form.get("note", "").strip()

    save_answer(
        session_id=session_id,
        item_idx=n,
        section_title=item["section_title"],
        item_id=item["item_id"],
        item_text=item["item_text"],
        passed=passed,
        note=note,
    )

    next_n = n + 1
    if next_n >= len(items):
        finish_session(session_id)
        return redirect(url_for("daily_qa.summary", session_id=session_id))

    return redirect(url_for("daily_qa.step", session_id=session_id, n=next_n))


@bp.route("/session/<session_id>/summary")
def summary(session_id: str):
    session = get_session(session_id)
    if not session:
        flash("Session not found.", "error")
        return redirect(url_for("daily_qa.pick"))

    answers          = get_answers(session_id)
    entry, checklist = _load_checklist(session["checklist_key"])
    total_items      = len(_flat_items(checklist)) if checklist else 0

    passed = sum(1 for a in answers if a["passed"])
    total  = len(answers)

    # Group answers by section for display
    sections: dict = {}
    for ans in answers:
        t = ans["section_title"]
        if t not in sections:
            sections[t] = []
        sections[t].append(ans)

    in_progress = total < total_items
    next_n      = total  # first unanswered index

    return render_template(
        "daily_qa/summary.html",
        session=session,
        sections=sections,
        passed=passed,
        total=total,
        total_items=total_items,
        all_good=(passed == total and not in_progress),
        in_progress=in_progress,
        next_n=next_n,
    )


@bp.route("/session/<session_id>/send-slack", methods=["POST"])
def send_slack(session_id: str):
    session = get_session(session_id)
    if not session:
        return redirect(url_for("daily_qa.pick"))

    answers = get_answers(session_id)
    results = _build_results_dict(session, answers)

    try:
        sent = send_slack_report(results)
        if sent:
            mark_slack_sent(session_id)
            flash("Slack report sent.", "success")
        else:
            flash("SLACK_WEBHOOK_URL not set in .env.", "error")
    except Exception as exc:
        flash(f"Slack send failed: {exc}", "error")

    return redirect(url_for("daily_qa.summary", session_id=session_id))


@bp.route("/trigger-call", methods=["POST"])
def trigger_call():
    data         = request.get_json(silent=True) or {}
    provider_key = data.get("provider_key", "")
    mod_path     = PROVIDER_MAP.get(provider_key)
    if not mod_path:
        return jsonify({"ok": False, "error": f"Unknown provider: {provider_key}"}), 400
    try:
        mod    = importlib.import_module(mod_path)
        result = mod.trigger()
        return jsonify({"ok": True, "result": result})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
