"""Build and send Slack Block Kit payloads for daily SMS deliverability reports."""
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

# Use a dedicated webhook if set, otherwise fall back to the project-wide one.
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
    """
    companies: list of dicts with keys name, total, delivered, failed,
               delivered_rate, failed_rate, avg_per_min, campaign_ids
    failures_by_company: company_name -> list of {carrier, error, cnt}
    """
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"SMS Deliverability Report — {date}", "emoji": True},
        },
        {"type": "divider"},
    ]

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
            error_short = (top["error"] or "Unknown")[:60]
            lines.append(f"• Top failure: *{top['carrier']}* — {error_short} ({_fmt_num(top['cnt'])})")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        })
        blocks.append({"type": "divider"})

    # Footer
    total_all = sum(c["total"] for c in companies)
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"Pipes QA · Telgorithm · {_fmt_num(total_all)} total messages · {date}"}],
    })

    return {"blocks": blocks}


def send(payload: dict) -> tuple[bool, str]:
    """POST payload to Slack. Returns (success, message)."""
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
