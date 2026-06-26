"""Build and send Slack Block Kit payloads for Signalmash SMS deliverability reports."""
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

from sms_deliverability.analysis_kb import get_signalmash

load_dotenv()

_WEBHOOK_ENV_KEYS = ("SMS_SLACK_WEBHOOK_URL", "SLACK_WEBHOOK_URL")


def _webhook_url() -> Optional[str]:
    for key in _WEBHOOK_ENV_KEYS:
        url = os.environ.get(key, "").strip()
        if url:
            return url
    return None


def _fmt_num(n: int) -> str:
    return f"{n:,}"


def build_payload(date: str, companies: list[dict], failures_by_company: dict[str, list]) -> dict:
    ALERT_THRESHOLD = 94

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"SMS Deliverability Report — {date}", "emoji": True},
        },
        {"type": "divider"},
    ]

    at_risk = [c for c in companies if c["delivered_rate"] < ALERT_THRESHOLD]
    if at_risk:
        alert_lines = ["🚨 *DELIVERY ALERT — Below 94% threshold*"]
        for c in at_risk:
            alert_lines.append(f"• *{c['name']}* — {c['delivered_rate']}% delivered ({_fmt_num(c['delivered'])}/{_fmt_num(c['total'])})")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(alert_lines)},
        })
        blocks.append({"type": "divider"})

    for c in companies:
        name = c["name"]
        failures = failures_by_company.get(name, [])
        top = failures[0] if failures else None

        delivered_icon = "✅" if c["delivered_rate"] >= 95 else ("⚠️" if c["delivered_rate"] >= 80 else "🔴")
        failed_icon    = "🟢" if c["failed_rate"] <= 5 else ("⚠️" if c["failed_rate"] <= 20 else "🔴")

        lines = [
            f"*{name}*",
            f"• Total Messages: {_fmt_num(c['total'])}",
            f"• {delivered_icon} Delivered: {_fmt_num(c['delivered'])} ({c['delivered_rate']}%)",
            f"• {failed_icon} Failed: {_fmt_num(c['failed'])} ({c['failed_rate']}%)",
        ]

        if top:
            error_short = (top["error"] or "Unknown")[:60]
            lines.append(f"• Top DLR: *{top.get('dlr_code','?')}* {error_short} ({_fmt_num(top['cnt'])})")
            kb = get_signalmash(top.get("dlr_code", ""))
            if kb.get("root_cause"):
                cause_short = kb["root_cause"].split(".")[0][:100]
                lines.append(f"  _Root cause: {cause_short}_")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        })
        blocks.append({"type": "divider"})

    total_all = sum(c["total"] for c in companies)
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"Pipes QA · Signalmash · {_fmt_num(total_all)} total messages · {date}"}],
    })

    return {"blocks": blocks}


def build_company_payload(
    company_name: str,
    period_label: str,
    kpi: dict,
    failures: list[dict],
) -> dict:
    """Build a per-company analysis Slack payload with root causes and actions."""
    rate = kpi["rate"]
    status_icon = "✅" if rate >= 95 else ("⚠️" if rate >= 94 else "🔴")

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Analysis Report — {company_name}", "emoji": True},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"*Period:* {period_label}\n"
                f"*Total:* {_fmt_num(kpi['total'])}   "
                f"*Delivered:* {_fmt_num(kpi['delivered'])}   "
                f"*Failed:* {_fmt_num(kpi['failed'])}\n"
                f"{status_icon} *Delivery Rate: {rate}%*"
            )},
        },
        {"type": "divider"},
    ]

    if failures:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*DLR Failure Analysis*"},
        })
        for f in failures[:8]:
            sev_icon = "🔴" if f["severity"] == "critical" else ("⚠️" if f["severity"] == "high" else "🔵")
            lines = [
                f"{sev_icon} *DLR {f['code']}* — {f['label']} ({_fmt_num(f['count'])}, {f['pct']}%)",
            ]
            if f.get("root_cause"):
                lines.append(f"  _Root cause:_ {f['root_cause'].split('.')[0][:120]}")
            if f.get("action"):
                lines.append(f"  _Action:_ {f['action'].split('.')[0][:120]}")
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(lines)},
            })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "✅ No failures recorded for this period."},
        })

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"Pipes QA · Signalmash · {company_name} · {period_label}"}],
    })

    return {"blocks": blocks}


def send(payload: dict) -> tuple[bool, str]:
    url = _webhook_url()
    if not url:
        return False, "No Slack webhook configured. Set SMS_SLACK_WEBHOOK_URL or SLACK_WEBHOOK_URL in .env"

    try:
        resp = httpx.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.text == "ok":
            return True, "Report sent to Slack."
        return False, f"Slack returned HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        return False, f"Failed to reach Slack: {exc}"
