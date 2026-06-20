import os
import httpx
from datetime import datetime


def _icon(passed: bool) -> str:
    return "✅" if passed else "❌"


def build_blocks(results: dict) -> list:
    provider = results["provider"]
    started = datetime.fromisoformat(results["started_at"])
    passed = results["passed"]
    total = results["total"]
    all_good = passed == total

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{'✅' if all_good else '❌'} Pipes QA — Daily Monitoring Report",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Provider:*\n{provider}"},
                {"type": "mrkdwn", "text": f"*Date / Time:*\n{started.strftime('%Y-%m-%d at %I:%M %p')}"},
            ],
        },
        {"type": "divider"},
    ]

    for section in results["sections"]:
        items = section["items"]
        sec_pass = sum(1 for i in items if i["passed"])
        sec_total = len(items)
        sec_icon = "✅" if sec_pass == sec_total else "⚠️"
        lines = [f"*{sec_icon} {section['title']}* — {sec_pass}/{sec_total}"]
        for item in items:
            line = f"  {_icon(item['passed'])} {item['text']}"
            if item.get("note"):
                line += f"\n    _{item['note']}_"
            lines.append(line)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})
        blocks.append({"type": "divider"})

    summary = f"*TOTAL: {passed}/{total} PASSED*"
    if not all_good:
        failed = [i["text"] for s in results["sections"] for i in s["items"] if not i["passed"]]
        summary += "\n*Failed:*\n" + "\n".join(f"  • {t}" for t in failed)

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": summary}})
    return blocks


def send_slack_report(results: dict) -> bool:
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook:
        return False
    r = httpx.post(webhook, json={"blocks": build_blocks(results)}, timeout=15)
    r.raise_for_status()
    return True
