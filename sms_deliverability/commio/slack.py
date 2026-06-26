"""Build and send Slack Block Kit payloads for Commio SMS deliverability reports."""
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

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


def build_payload(label: str, companies: list[dict], failures_by_company: dict[str, list]) -> dict:
    ALERT_THRESHOLD = 94

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Commio SMS Deliverability — {label}", "emoji": True},
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

        if c.get("avg_per_min") is not None:
            lines.append(f"• Avg SMS/min: {c['avg_per_min']:.1f}")

        if top:
            code = top.get("status_code", "")
            error_short = (top.get("error") or code or "Unknown")[:60]
            lines.append(f"• Top failure: *{top['carrier']}* — {error_short} ({_fmt_num(top['cnt'])})")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        })
        blocks.append({"type": "divider"})

    total_all = sum(c["total"] for c in companies)
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"Pipes QA · Commio · {_fmt_num(total_all)} total messages · {label}"}],
    })

    return {"blocks": blocks}


def send(payload: dict) -> tuple[bool, str]:
    url = _webhook_url()
    if not url:
        return False, "No Slack webhook configured. Set SMS_SLACK_WEBHOOK_URL or SLACK_WEBHOOK_URL in .env"
    try:
        resp = httpx.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.text == "ok":
            return True, "Commio report sent to Slack."
        return False, f"Slack returned HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        return False, f"Failed to reach Slack: {exc}"
