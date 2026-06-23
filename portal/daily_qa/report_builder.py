"""
Build the narrative-style report draft from QA session answers.
Matches the format Ian uses for Slack posts.
"""
from datetime import datetime, timezone, timedelta

import httpx

_KHOMP_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1_Jbh36IsSnwLOHhRHMnUPvc-NngTk23hoIOug3DZPCQ"
    "/export?format=csv&gid=0"
)

# Always report in US Eastern time regardless of server locale
try:
    from zoneinfo import ZoneInfo as _ZI
    _EASTERN = _ZI("America/New_York")
except Exception:
    _EASTERN = None


def _now_eastern() -> datetime:
    if _EASTERN:
        return datetime.now(_EASTERN)
    # Fallback: UTC-4 (EDT, summer)
    return datetime.now(timezone(timedelta(hours=-4)))


_WORKING = "Working (Transfer, End Call, DNC, Reschedule)"


def _fetch_khomp_classification() -> str:
    """
    Fetch yesterday's Khomp call classification from the public Google Sheet.
    Falls back to the most recent row if yesterday isn't found yet.
    Returns a formatted string like:
        06/21/2026 | Short : 4.70% | Long : 0.01% | Timeout : 0.27%
    """
    yesterday = (_now_eastern() - timedelta(days=1)).strftime("%m/%d/%Y")
    try:
        resp = httpx.get(_KHOMP_SHEET_URL, timeout=10, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        return f"[Could not fetch sheet: {exc}]"

    rows = [
        [c.strip().strip('"') for c in line.split(",")]
        for line in resp.text.strip().splitlines()[1:]  # skip header
        if line.strip()
    ]
    # Only keep rows that actually have Short/Long/Timeout values
    data_rows = [r for r in rows if len(r) >= 4 and r[1].strip() and r[2].strip()]
    if not data_rows:
        return "[No classification data found in sheet]"

    # Prefer yesterday; fall back to the last row that has data
    row = next((r for r in data_rows if r[0] == yesterday), data_rows[-1])
    if len(row) < 4:
        return "[Unexpected sheet format]"

    date_v    = row[0]
    short_v   = row[1].replace("%", "").strip()
    long_v    = row[2].replace("%", "").strip()
    timeout_v = row[3].replace("%", "").strip()
    return f"{date_v} | Short : {short_v}% | Long : {long_v}% | Timeout : {timeout_v}%"


def _find(answers, *keywords):
    """Return all answers whose section_title contains any keyword (case-insensitive)."""
    return [
        a for a in answers
        if any(k.lower() in dict(a)["section_title"].lower() for k in keywords)
    ]


def _result(items):
    """Summarise a list of answer rows into pass/fail dict, or None if empty."""
    if not items:
        return None
    rows     = [dict(a) for a in items]
    all_pass = all(r["passed"] for r in rows)
    failing  = [r for r in rows if not r["passed"]]
    return {"all_pass": all_pass, "failing": failing}


def _status_line(result, working=_WORKING):
    if result is None:
        return "[not tested]"
    if result["all_pass"]:
        return working
    # Deduplicate and filter out generic boilerplate notes
    seen, notes = set(), []
    for r in result["failing"]:
        n = r.get("note", "").strip()
        if n and n not in seen:
            seen.add(n)
            notes.append(n)
    # Drop notes that are themselves just "ongoing issue..." boilerplate
    specific = [n for n in notes if "ongoing issue with outbound" not in n.lower()]
    if specific:
        return "Ongoing issue — " + "; ".join(specific)
    return "Ongoing issue with outbound dialing."


def _latency_lines(answers):
    """Collect latency measurements entered on RetellAI / AMD steps."""
    lines = []
    retell_ids = {"retell_connecting", "retell_scheduling", "amd_detection", "retell_stop_dnc"}
    for a in answers:
        row  = dict(a)
        note = row.get("latency_note", "") or ""
        if note.strip() and row.get("item_id") in retell_ids:
            for raw in note.strip().splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    val = float(raw.split()[0])
                    lines.append(f"{val:.2f} secs hello to play greeting (Google Voice)")
                except ValueError:
                    lines.append(raw)
    return lines


def build_draft_text(session, answers, extra: dict = None) -> str:
    """
    Generate the narrative report text.

    extra keys (all optional — shown as placeholders when missing):
        khomp_peak, khomp_time,
        rollbar,
        khomp_class,
        zap_usage, zap_reset, zap_runs, zap_action
    """
    extra = extra or {}

    # ── Always use current Eastern time for the "as of" header ───────────
    dt       = _now_eastern()
    date_str = dt.strftime("%m/%d/%Y")
    time_str = dt.strftime("%I:%M %p")

    # ── Section results ───────────────────────────────────────────────────
    thinq  = _result(_find(answers, "Account Used", "Keypress Actions",
                            "Dynamic Inserts", "AMD Detection", "Auto-Connect"))
    tbi_k  = _result(_find(answers, "TBI Khomp"))
    tbi_fs = _result(_find(answers, "TBI Freeswitch"))
    sig_k  = _result(_find(answers, "Signalmash Khomp"))
    sig_fs = _result(_find(answers, "Signalmash Freeswitch"))
    retell = _result(_find(answers, "RetellAI"))
    sms    = _result(_find(answers, "SMS Only"))
    sms_ai = _result(_find(answers, "SMS with AI"))
    kp     = _result(_find(answers, "Keypress Actions"))
    dyn    = _result(_find(answers, "Dynamic Inserts"))

    # ── Extra / placeholder values ────────────────────────────────────────
    khomp_peak  = extra.get("khomp_peak",  "[PEAK]")
    khomp_time  = extra.get("khomp_time",  "[HH:MM AM/PM]")
    rollbar     = extra.get("rollbar",     "[No errors in Production for last hour]")
    # Skip Khomp classification on weekends (Saturday=5, Sunday=6)
    _today = _now_eastern()
    if extra.get("khomp_class"):
        khomp_class = extra["khomp_class"]
    elif _today.weekday() >= 5:
        khomp_class = None          # omitted from report on weekends
    else:
        khomp_class = _fetch_khomp_classification()
    zap_usage   = extra.get("zap_usage",   "[X,XXX/50k]")
    zap_reset   = extra.get("zap_reset",   "[X weeks]")
    zap_runs    = extra.get("zap_runs",    "Error ( POST Vivint Facebook Lead Ads to Pipes )")
    zap_action  = extra.get("zap_action",  "None")

    # ── Header ────────────────────────────────────────────────────────────
    s           = dict(session)
    report_type = s.get("report_type", "daily")
    if report_type == "hourly":
        header = f"Hourly Monitoring Checklist Updates - {date_str} as of {time_str} Eastern Time"
    else:
        header = f"Daily QA Report - {date_str} as of {time_str} Eastern Time"

    # ── RetellAI narrative line ───────────────────────────────────────────
    if retell and retell["all_pass"]:
        retell_line = (
            "RetellAI test agent is responsive. "
            "Transfer is working and post-call analysis are getting passed correctly."
        )
    elif retell:
        seen_n, fail_notes = set(), []
        for r in retell["failing"]:
            n = r.get("note", "").strip()
            if n and n not in seen_n:
                seen_n.add(n)
                fail_notes.append(n)
        retell_line = "RetellAI — Issues detected." + (f" {'; '.join(fail_notes)}" if fail_notes else "")
    else:
        retell_line = "RetellAI — [not tested]"

    # ── One-liners ────────────────────────────────────────────────────────
    kp_line  = "Working" if (kp  and kp["all_pass"])  else "Issues detected"
    dyn_line = "Working" if (dyn and dyn["all_pass"])  else "Issues detected"
    sms_line = (
        "Working - Lead was DNC'd accordingly"
        if (sms and sms["all_pass"])
        else "Issues detected — check SMS suppression"
    )
    sms_ai_line = (
        "Bot is responsive and scheduling calls"
        if (sms_ai and sms_ai["all_pass"])
        else "Issues detected"
    )

    # ── Assemble ──────────────────────────────────────────────────────────
    parts = [
        header,
        "",
        f"Khomp monitoring - peak {khomp_peak} at {khomp_time} Eastern.",
        "",
        "Outbound Dialing Khomp:",
        f"ThinQ - {_status_line(thinq)}",
        f"TBI Telco - {_status_line(tbi_k)}",
        f"Signalmash - {_status_line(sig_k)}",
        "",
        "Outbound Dialing FS:",
        "ThinQ - [not tested in this checklist]",
        f"TBI Telco - {_status_line(tbi_fs)}",
        f"Signalmash - {_status_line(sig_fs)}",
        "",
        "Inbound Dialling:",
        f"• ThinQ - {_status_line(thinq)}",
        f"• TBI Telco - {_status_line(tbi_k)}",
        f"• Signalmash - {_status_line(sig_k)}",
        "",
        f"Keypress Actions: {kp_line}",
        f"SMS Opt Out {sms_line}",
        f"AI SMS - {sms_ai_line}",
        f"Dynamic Inserts - {dyn_line}",
        retell_line,
        "",
        "Outbound RetellAI Call latency with Khomp AMD in Production.",
        "",
    ]

    # Latency from saved answers, or placeholder
    lat = _latency_lines(answers)
    if lat:
        parts += lat
    else:
        parts.append("[LATENCY]")

    khomp_line = (
        [f"Khomp Classification (last 8hrs.): {khomp_class}"]
        if khomp_class else []
    )
    parts += [
        "",
        f"Rollbar Errors: {rollbar}",
        *khomp_line,
        "Zapier:",
        f"Task Usage: {zap_usage} Usage resets in {zap_reset}.",
        f"Zap runs: {zap_runs}",
        f"Action Needed : {zap_action}",
    ]

    return "\n".join(parts)
