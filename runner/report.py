import os
import httpx
from datetime import datetime


def _icon(passed: bool) -> str:
    return "✅" if passed else "❌"


def _carrier_icon(status: str) -> str:
    return "✅" if status == "working" else "❌"


# ── Checklist blocks ───────────────────────────────────────────────────────────

def _checklist_blocks(results: dict) -> list:
    provider   = results["provider"]
    started    = datetime.fromisoformat(results["started_at"])
    passed     = results["passed"]
    total      = results["total"]
    all_good   = passed == total

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{'✅' if all_good else '❌'} Pipes QA — Hourly Monitoring Report",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Provider:*\n{provider}"},
                {"type": "mrkdwn", "text": f"*Date / Time:*\n{started.strftime('%m/%d/%Y at %I:%M %p')} Eastern"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*📋 QA Checklist Results*"},
        },
    ]

    for section in results["sections"]:
        items      = section["items"]
        sec_pass   = sum(1 for i in items if i["passed"])
        sec_total  = len(items)
        sec_icon   = "✅" if sec_pass == sec_total else "⚠️"
        lines      = [f"*{sec_icon} {section['title']}* — {sec_pass}/{sec_total}"]
        for item in items:
            line = f"  {_icon(item['passed'])} {item['text']}"
            if item.get("note"):
                line += f"\n    _{item['note']}_"
            lines.append(line)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})

    summary = f"*TOTAL: {passed}/{total} PASSED*"
    if not all_good:
        failed  = [i["text"] for s in results["sections"] for i in s["items"] if not i["passed"]]
        summary += "\n*Failed:*\n" + "\n".join(f"  • {t}" for t in failed)
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": summary}})

    return blocks


# ── Monitoring blocks ──────────────────────────────────────────────────────────

def _monitoring_blocks(mon: dict) -> list:
    blocks: list = [
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*📊 Hourly Monitoring*"},
        },
    ]

    # Khomp peak
    peak = mon.get("khomp_peak", {})
    if peak.get("concurrent") or peak.get("time"):
        peak_text = "Khomp monitoring"
        if peak.get("concurrent") and peak.get("time"):
            peak_text += f" — peak *{peak['concurrent']}* at *{peak['time']}* Eastern"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": peak_text}})

    # Carrier status tables
    channel_labels = {
        "ob_khomp": "Outbound Dialing Khomp",
        "ob_fs":    "Outbound Dialing FS",
        "inbound":  "Inbound Dialling",
    }
    carriers_data = mon.get("carriers", {})
    for ch_key, ch_label in channel_labels.items():
        ch = carriers_data.get(ch_key, {})
        if not ch:
            continue
        lines = [f"*{ch_label}:*"]
        for carrier, info in ch.items():
            icon  = _carrier_icon(info.get("status", "working"))
            note  = info.get("note", "")
            line  = f"  {icon} {carrier}"
            if note:
                line += f" — _{note}_"
            lines.append(line)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})

    # Other checks
    check_labels = {
        "keypress_actions": "Keypress Actions",
        "sms_opt_out":      "SMS Opt Out",
        "ai_sms":           "AI SMS",
        "dynamic_inserts":  "Dynamic Inserts",
    }
    checks = mon.get("checks", {})
    if checks:
        lines = ["*Other Checks:*"]
        for ck_key, ck_label in check_labels.items():
            info = checks.get(ck_key)
            if info is None:
                continue
            icon = _carrier_icon(info.get("status", "working"))
            note = info.get("note", "")
            line = f"  {icon} {ck_label}"
            if note:
                line += f" — _{note}_"
            lines.append(line)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})

    # RetellAI
    retell = mon.get("retell", {})
    if retell:
        icon    = _carrier_icon(retell.get("status", "working"))
        note    = retell.get("note", "")
        latency = retell.get("latency", [])
        lines   = [f"*RetellAI:*", f"  {icon} Test agent" + (f" — _{note}_" if note else "")]
        if latency:
            lat_str = " / ".join(f"{v} secs" for v in latency)
            lines.append(f"  Outbound latency (hello → greeting): {lat_str}")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})

    # Rollbar
    rollbar = mon.get("rollbar", {})
    if rollbar is not None:
        err_count = rollbar.get("errors", 0)
        err_note  = rollbar.get("note", "")
        if err_count == 0:
            rb_text = "✅ *Rollbar:* No errors in Production for last hour"
        else:
            rb_text = f"❌ *Rollbar:* {err_count} error(s) in Production"
            if err_note:
                rb_text += f" — _{err_note}_"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": rb_text}})

    # Khomp classification
    kc = mon.get("khomp_classification", {})
    if any(kc.get(k) for k in ("short_pct", "long_pct", "timeout_pct")):
        kc_text = f"*Khomp Classification (last 8 hrs)"
        if kc.get("date"):
            kc_text += f" — {kc['date']}"
        kc_text += ":*"
        parts = []
        if kc.get("short_pct"):
            parts.append(f"Short: {kc['short_pct']}%")
        if kc.get("long_pct"):
            parts.append(f"Long: {kc['long_pct']}%")
        if kc.get("timeout_pct"):
            parts.append(f"Timeout: {kc['timeout_pct']}%")
        kc_text += "  " + " | ".join(parts)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": kc_text}})

    # Zapier
    zap = mon.get("zapier", {})
    if zap:
        lines = ["*Zapier:*"]
        if zap.get("task_usage"):
            resets = f" — resets in {zap['resets_in']}" if zap.get("resets_in") else ""
            lines.append(f"  Task Usage: {zap['task_usage']}{resets}")
        errors = zap.get("errors", "None")
        if errors and errors.lower() != "none":
            lines.append(f"  ⚠️ Zap error: {errors}")
        else:
            lines.append("  ✅ No Zap errors")
        action = zap.get("action_needed", "None")
        lines.append(f"  Action Needed: {action}")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})

    return blocks


# ── Public API ─────────────────────────────────────────────────────────────────

def build_blocks(results: dict) -> list:
    blocks = _checklist_blocks(results)
    mon    = results.get("monitoring")
    if mon:
        blocks.extend(_monitoring_blocks(mon))
    return blocks


def send_slack_report(results: dict) -> bool:
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook:
        return False
    r = httpx.post(webhook, json={"blocks": build_blocks(results)}, timeout=15)
    r.raise_for_status()
    return True
