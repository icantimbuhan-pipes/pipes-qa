"""
Hourly Monitoring QA — report builder.

Auto-fills carrier statuses from checklist pass/fail.
Asks a short form for fields that can't be inferred.
Sends a plain-text Slack message in the exact format used by the team.
"""
import os
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo

from rich.console import Console
from rich.rule import Rule

from runner.sheets import fetch_khomp_classification

console = Console()
EASTERN = ZoneInfo("America/New_York")

PASS_CALL = "Working (Transfer, End Call, DNC, Reschedule)"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _inp(prompt: str = "") -> str:
    if prompt:
        console.print(prompt, end="")
    return input().strip()


def _status(items: dict, item_id: str, pass_text: str = PASS_CALL) -> str:
    it = items.get(item_id)
    if not it:
        return "Not tested"
    if it["passed"]:
        return pass_text
    note = it.get("note", "")
    return "Ongoing issue." + (f" {note}" if note else "")


def _ask_status(label: str) -> str:
    """Ask 1=Working / 2=Issue for a carrier not covered by the checklist."""
    r = _inp(f"  {label} — 1 Working  2 Issue: ")
    if r == "2":
        note = _inp("    Note: ")
        return "Ongoing issue." + (f" {note}" if note else "")
    return PASS_CALL


# ── Manual form ───────────────────────────────────────────────────────────────

def run_hourly_form(results: dict) -> dict:
    """
    Takes the completed hourly checklist results.
    Auto-fills everything it can, then asks for the few manual fields.
    Returns a form dict used by build_hourly_message().
    """
    items: dict = {}
    for sec in results.get("sections", []):
        for item in sec.get("items", []):
            items[item["id"]] = item

    now_et = datetime.now(EASTERN)

    console.print()
    console.print(Rule("[bold cyan]Hourly Monitoring — Quick Form[/bold cyan]", style="cyan"))
    console.print(
        "[dim]Auto-filled from checklist: Khomp carriers, TBI, Signalmash, SMS, RetellAI, Dynamic Inserts.[/dim]\n"
    )

    # ── Khomp peak ──
    peak_count = _inp("  Khomp peak count (e.g. 100): ")
    peak_time  = _inp("  Peak time ET (e.g. 14:07 PM): ")

    # ── FS ThinQ + Inbound ThinQ — not in hourly checklist ──
    console.print("\n  [dim]Two carriers not in the hourly checklist:[/dim]")
    fs_thinq_status      = _ask_status("Outbound Dialing FS: ThinQ")
    inbound_thinq_status = _ask_status("Inbound Dialling: ThinQ")

    # ── RetellAI latency — 3 measurements ──
    console.print("\n  RetellAI latency — 3 measurements (seconds, e.g. 4.26):")
    lat = [
        _inp("  Measurement 1: "),
        _inp("  Measurement 2: "),
        _inp("  Measurement 3: "),
    ]

    # ── Rollbar — prefilled, press ENTER to keep ──
    console.print("\n  Rollbar Errors:")
    console.print("  [dim]ENTER = No errors in Production for last hour[/dim]")
    rollbar = _inp("  → ") or "No errors in Production for last hour"

    # ── Khomp Classification — auto-fill from Google Sheet ──
    console.print("\n  Khomp Classification (last 8hrs):")
    auto_class = fetch_khomp_classification(target_date=now_et.date())
    if auto_class:
        console.print(f"  [green]Auto-filled:[/green] {auto_class}")
        console.print("  [dim]ENTER to keep, or type to override[/dim]")
        khomp_class = _inp("  → ") or auto_class
    else:
        console.print("  [dim]e.g. 06/18/2026 | Short : 6.32% | Long : 0.03% | Timeout : 1.35%[/dim]")
        console.print("  [dim](Sheet unavailable — type manually)[/dim]")
        khomp_class = _inp("  → ")

    # ── Zapier ──
    console.print("\n  Zapier:")
    zapier_usage  = _inp("  Task Usage (e.g. 5,922/50k Usage resets in 4 weeks): ")
    zapier_runs   = _inp("  Zap runs (e.g. Error (POST Vivint...) or OK): ")
    action_needed = _inp("  Action Needed (e.g. None): ") or "None"

    return {
        "timestamp_et":        now_et.isoformat(),
        "peak_count":          peak_count,
        "peak_time":           peak_time,
        "items":               items,
        "fs_thinq_status":     fs_thinq_status,
        "inbound_thinq_status":inbound_thinq_status,
        "latency":             lat,
        "rollbar":             rollbar,
        "khomp_class":         khomp_class,
        "zapier_usage":        zapier_usage,
        "zapier_runs":         zapier_runs,
        "action_needed":       action_needed,
    }


# ── Message builder ───────────────────────────────────────────────────────────

def build_hourly_message(form: dict) -> str:
    items    = form["items"]
    now_et   = datetime.fromisoformat(form["timestamp_et"])
    date_str = now_et.strftime("%m/%d/%Y")
    time_str = now_et.strftime("%I:%M %p")
    lat      = form.get("latency", ["—", "—", "—"])

    def s(item_id, pass_text=PASS_CALL):
        return _status(items, item_id, pass_text)

    # SMS Opt Out
    sms_opt = (
        "Working - Lead was DNC'd accordingly"
        if items.get("hm_sms_only", {}).get("passed")
        else "Issue. " + items.get("hm_sms_only", {}).get("note", "check SMS opt-out flow")
    )

    # AI SMS
    sms_ai = (
        "Bot is responsive and scheduling calls"
        if items.get("hm_sms_ai", {}).get("passed")
        else "Issue. " + items.get("hm_sms_ai", {}).get("note", "check AI SMS bot")
    )

    # RetellAI
    retell = (
        "agent is responsive. Transfer is working and post-call analysis are getting passed correctly."
        if items.get("hm_retell_ai", {}).get("passed")
        else "Issue. " + items.get("hm_retell_ai", {}).get("note", "check RetellAI agent")
    )

    # Dynamic Inserts
    dynamic = (
        "Working"
        if items.get("hm_heavy_khomp_dynamic", {}).get("passed")
        else "Issue. " + items.get("hm_heavy_khomp_dynamic", {}).get("note", "check dynamic inserts")
    )

    # Keypress Actions — inferred from heavy_khomp result
    keypress = (
        "Working"
        if items.get("hm_heavy_khomp", {}).get("passed")
        else "Issue. " + items.get("hm_heavy_khomp", {}).get("note", "check keypress actions")
    )

    lines = [
        f"*Hourly Monitoring Checklist Updates - {date_str} as of {time_str} Eastern Time*",
        "",
        f"Khomp monitoring - peak {form.get('peak_count', '—')} at {form.get('peak_time', '—')} Eastern.",
        "",
        "*Outbound Dialing Khomp:*",
        f"ThinQ - {s('hm_heavy_khomp')}",
        f"TBI Telco - {s('hm_tbi_khomp')}",
        f"Signalmash - {s('hm_signalmash_khomp')}",
        "",
        "*Outbound Dialing FS:*",
        f"ThinQ - {form.get('fs_thinq_status', '—')}",
        f"TBI Telco - {s('hm_tbi_fs')}",
        f"Signalmash - {s('hm_signalmash_fs')}",
        "",
        "*Inbound Dialling:*",
        f"• ThinQ - {form.get('inbound_thinq_status', '—')}",
        f"• TBI Telco - {s('hm_tbi_khomp')}",
        f"• Signalmash - {s('hm_signalmash_khomp')}",
        "",
        f"Keypress Actions: {keypress}",
        f"SMS Opt Out {sms_opt}",
        f"AI SMS - {sms_ai}",
        f"Dynamic Inserts - {dynamic}",
        f"RetellAI test {retell}",
        "Outbound RetellAI Call latency with Khomp AMD in Production.",
        "",
        f"{lat[0]} secs hello to play greeting (Google Voice)",
        f"{lat[1]} secs hello to play greeting (Google Voice)",
        f"{lat[2]} secs hello to play greeting (Google Voice)",
        f"Rollbar Errors: [{form.get('rollbar', '—')}]",
        f"Khomp Classification (last 8hrs.): {form.get('khomp_class', '—')}",
        "Zapier:",
        f"Task Usage: {form.get('zapier_usage', '—')}",
        f"Zap runs: {form.get('zapier_runs', '—')}",
        f"Action Needed : {form.get('action_needed', 'None')}",
    ]
    return "\n".join(lines)


# ── Slack sender ──────────────────────────────────────────────────────────────

def send_hourly_report(form: dict) -> bool:
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        return False
    msg = build_hourly_message(form)
    httpx.post(url, json={"text": msg}, timeout=15)
    # Print preview in terminal
    console.print("\n[dim]─── Slack message preview ───[/dim]")
    console.print(msg)
    console.print("[dim]────────────────────────────[/dim]")
    return True
