import importlib
import json as _json
import os
from datetime import datetime
from typing import Optional

import httpx
from dotenv import dotenv_values
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from portal.db import (
    create_session, finish_session, get_answers, get_session,
    get_custom_checklist_by_key, list_custom_checklists,
    get_provider_config, get_all_qa_settings,
    list_sessions, mark_slack_sent, save_answer, save_draft,
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

# Item IDs where the user enters latency measurements
LATENCY_ITEM_IDS = {"retell_connecting", "retell_scheduling", "amd_detection", "retell_stop_dnc"}


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
                "show_latency":          item.id in LATENCY_ITEM_IDS,
            })
    return items


def _load_checklist(key: str):
    # Try built-in first
    entry = next((cl for cl in CHECKLISTS if cl["key"] == key), None)
    if entry:
        mod = importlib.import_module(entry["module"])
        return entry, getattr(mod, entry["attr"])
    # Fall back to custom checklists stored in DB
    from portal.checklist_builder.routes import json_to_checklist
    custom = get_custom_checklist_by_key(key)
    if custom:
        custom = dict(custom)
        entry = {
            "key":              custom["key"],
            "name":             custom["name"],
            "report_type":      custom.get("report_type", "daily"),
            "default_provider": custom.get("default_provider", "heavy_khomp"),
        }
        return entry, json_to_checklist(custom.get("sections_json", "[]"))
    return None, None


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


def _parse_trigger_response(resp_json: dict, resp_text: str) -> str:
    """Extract rejection reason from a trigger API response, or '' if accepted."""
    accepted_values = {"accepted", "success", "ok", ""}
    for field in ("reason", "message", "error", "rejection_reason", "status_message"):
        val = str(resp_json.get(field, "")).lower().strip()
        if val and val not in accepted_values:
            return val
    status = str(resp_json.get("status", "")).lower().strip()
    if status and status not in accepted_values:
        return status
    # Fallback: scan raw text for known rejection keywords
    txt = resp_text.lower()
    for kw in ("already dnc", "duplicate", "invalid", "rejected", "blacklist", "paused"):
        if kw in txt:
            return txt[:120].strip()
    return ""


# ── Routes ─────────────────────────────────────────────────────────────────────

@bp.route("/")
def pick():
    preset = request.args.get("preset", "")
    recent = list_sessions(8)

    # Merge built-ins + custom checklists for the pick page
    all_checklists = list(CHECKLISTS)
    for cc in list_custom_checklists():
        cc = dict(cc)
        all_checklists.append({
            "key":             cc["key"],
            "name":            cc["name"],
            "desc":            f"Custom • {cc.get('default_provider', '').replace('_', ' ').title()}",
            "active":          True,
            "report_type":     cc.get("report_type", "daily"),
            "default_provider": cc.get("default_provider", "heavy_khomp"),
            "custom":          True,
        })

    return render_template("daily_qa/pick.html", checklists=all_checklists, preset=preset, recent=recent)


@bp.route("/start", methods=["POST"])
def start():
    key = request.form.get("checklist_key", "")
    entry, _ = _load_checklist(key)
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

    item         = items[n]
    passed       = request.form.get("passed") == "1"
    note         = request.form.get("note",         "").strip()
    latency_note = request.form.get("latency_note", "").strip()

    save_answer(
        session_id=session_id,
        item_idx=n,
        section_title=item["section_title"],
        item_id=item["item_id"],
        item_text=item["item_text"],
        passed=passed,
        note=note,
        latency_note=latency_note,
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


@bp.route("/session/<session_id>/draft", methods=["GET", "POST"])
def draft(session_id: str):
    session = get_session(session_id)
    if not session:
        flash("Session not found.", "error")
        return redirect(url_for("daily_qa.pick"))

    answers = get_answers(session_id)

    if request.method == "POST":
        action     = request.form.get("action", "save")
        draft_text = request.form.get("draft_text", "").strip()
        save_draft(session_id, draft_text)

        if action == "send":
            env     = dotenv_values(".env")
            webhook = env.get("SLACK_WEBHOOK_URL") or os.environ.get("SLACK_WEBHOOK_URL", "")
            if not webhook:
                flash("SLACK_WEBHOOK_URL not set in .env.", "error")
                return redirect(url_for("daily_qa.draft", session_id=session_id))
            try:
                httpx.post(webhook, json={"text": draft_text}, timeout=15)
                mark_slack_sent(session_id)
                flash("Report sent to Slack.", "success")
            except Exception as exc:
                flash(f"Slack send failed: {exc}", "error")
                return redirect(url_for("daily_qa.draft", session_id=session_id))
            return redirect(url_for("daily_qa.summary", session_id=session_id))

        flash("Draft saved.", "success")
        return redirect(url_for("daily_qa.draft", session_id=session_id))

    # GET — compute provider statuses from answers for dropdown pre-fill
    from portal.daily_qa.report_builder import (
        _find, _result, _latency_lines,
        _now_eastern, _fetch_khomp_classification,
    )
    import json as _json2

    dt = _now_eastern()

    def _ms(result):
        """Map a _result() dict to {value, note} for the dropdown."""
        if result is None:
            return {"value": "not_tested", "note": ""}
        if result["all_pass"]:
            return {"value": "working", "note": ""}
        seen, notes = set(), []
        for r in result["failing"]:
            n = r.get("note", "").strip()
            if n and n not in seen and "ongoing issue with outbound" not in n.lower():
                seen.add(n)
                notes.append(n)
        if notes:
            return {"value": "custom", "note": "; ".join(notes)}
        return {"value": "ongoing", "note": ""}

    thinq    = _result(_find(answers, "Account Used", "AMD Detection", "Auto-Connect"))
    tbi_k    = _result(_find(answers, "TBI Khomp"))
    tbi_fs   = _result(_find(answers, "TBI Freeswitch"))
    sig_k    = _result(_find(answers, "Signalmash Khomp"))
    sig_fs   = _result(_find(answers, "Signalmash Freeswitch"))
    thinq_fs = _result(_find(answers, "ThinQ FS", "ThinQ Freeswitch", "Heavy FS"))
    retell   = _result(_find(answers, "RetellAI"))
    sms      = _result(_find(answers, "SMS Only"))
    sms_ai   = _result(_find(answers, "SMS with AI"))
    kp       = _result(_find(answers, "Keypress Actions"))
    dyn      = _result(_find(answers, "Dynamic Inserts"))

    # Retell special mapping
    if retell is None:
        retell_val, retell_note = "not_tested", ""
    elif retell["all_pass"]:
        retell_val, retell_note = "responsive", ""
    else:
        retell_val = "issues"
        retell_note = "; ".join(dict.fromkeys(
            r.get("note","").strip() for r in retell["failing"] if r.get("note","").strip()
        ))

    ps = {
        "ob_khomp_thinq": _ms(thinq),
        "ob_khomp_tbi":   _ms(tbi_k),
        "ob_khomp_sig":   _ms(sig_k),
        "ob_fs_thinq":    _ms(thinq_fs),
        "ob_fs_tbi":      _ms(tbi_fs),
        "ob_fs_sig":      _ms(sig_fs),
        "ib_thinq":       _ms(thinq),
        "ib_tbi":         _ms(tbi_k),
        "ib_sig":         _ms(sig_k),
        "f_kp":    {"value": "working" if (kp     is None or kp["all_pass"])     else "issues", "note": ""},
        "f_sms":   {"value": "working" if (sms    is None or sms["all_pass"])    else "issues", "note": ""},
        "f_ai_sms":{"value": "working" if (sms_ai is None or sms_ai["all_pass"]) else "issues", "note": ""},
        "f_dyn":   {"value": "working" if (dyn    is None or dyn["all_pass"])    else "issues", "note": ""},
        "f_retell":{"value": retell_val, "note": retell_note},
    }

    # Latency from saved answers
    lat_lines = _latency_lines(answers)
    lat_prefill = "\n".join(
        l.split(" ")[0] for l in lat_lines  # extract just the number
    ) if lat_lines else ""

    # Khomp classification
    try:
        khomp_class = _fetch_khomp_classification()
    except Exception:
        khomp_class = ""

    return render_template(
        "daily_qa/draft.html",
        session=session,
        session_id=session_id,
        provider_statuses=_json2.dumps(ps),
        lat_prefill=lat_prefill,
        khomp_class=khomp_class,
        date_str=dt.strftime("%m/%d/%Y"),
        time_str=dt.strftime("%I:%M %p"),
    )


@bp.route("/session/<session_id>/send-slack", methods=["POST"])
def send_slack(session_id: str):
    """Legacy direct send — kept for backward compat but now redirects to draft."""
    return redirect(url_for("daily_qa.draft", session_id=session_id))


@bp.route("/trigger-call", methods=["POST"])
def trigger_call():
    from datetime import date as _date
    from dotenv import dotenv_values
    from providers.base import fire

    data         = request.get_json(silent=True) or {}
    provider_key = data.get("provider_key", "")

    if provider_key not in PROVIDER_MAP:
        return jsonify({"ok": False, "error": f"Unknown provider: {provider_key}"}), 400

    try:
        # Load DB config for this provider (overrides env vars)
        db_cfg  = get_provider_config(provider_key)
        db_cfg  = dict(db_cfg) if db_cfg else {}
        qa      = get_all_qa_settings()
        env     = dotenv_values(".env")

        def _v(qa_key, env_key, default=""):
            return qa.get(qa_key) or env.get(env_key, "") or default

        if db_cfg.get("api_key"):
            # Use DB config — build params directly
            import json as _j
            extra = {}
            try:
                extra = _j.loads(db_cfg.get("extra_json") or "{}")
            except Exception:
                pass

            params = {
                "phone_number":      _v("phone_number",   "QA_PHONE_NUMBER",   "5122227114"),
                "ip_address":        _v("ip_address",     "QA_IP_ADDRESS",     "79.116.129.221"),
                "tcpa_consent":      "1",
                "tcpa_consent_date": _date.today().isoformat(),
                "email":             _v("email",           "QA_EMAIL",          "qa@pipes.ai"),
                "jornaya_leadid":    _v("jornaya_leadid",  "QA_JORNAYA_LEADID", ""),
                "api_key":           db_cfg["api_key"],
                "first_name":        db_cfg.get("first_name", "QA Test"),
                "last_name":         db_cfg.get("last_name",  "User"),
                "state":             db_cfg.get("state",      "FL"),
                "postal_code":       db_cfg.get("postal_code","32004"),
                **extra,
            }
            api_url = db_cfg.get("api_url") or "https://leads.pipes.ai/api/lead"
            import httpx as _hx
            r      = _hx.post(api_url, data=params, timeout=30)
            result = {"ok": True, "http_code": r.status_code, "response": r.text}
        else:
            # Fall back to existing provider module (reads env vars)
            mod    = importlib.import_module(PROVIDER_MAP[provider_key])
            result = mod.trigger()

        resp_text = result.get("response", "")
        try:
            resp_json = _json.loads(resp_text)
        except Exception:
            resp_json = {}

        rejection = _parse_trigger_response(resp_json, resp_text)
        accepted  = result.get("http_code") == 200 and not rejection

        return jsonify({
            "ok":        True,
            "accepted":  accepted,
            "rejection": rejection,
            "http_code": result.get("http_code"),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
