"""
Quick test — run the hourly form manually with fake checklist data.
Simulates a completed hourly checklist so you can fill the form and
see the exact Slack message before it sends.

Run:
    uv run python -m tests.test_hourly_report
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from runner.hourly_report import run_hourly_form, build_hourly_message, send_hourly_report
from rich.console import Console

console = Console()

# Fake checklist results — change passed=True/False to test different outputs
FAKE_RESULTS = {
    "sections": [
        {
            "title": "Hourly Monitoring QA — Heavy Khomp",
            "items": [
                {"id": "hm_heavy_khomp",          "passed": True,  "note": ""},
                {"id": "hm_heavy_khomp_dynamic",   "passed": True,  "note": ""},
                {"id": "hm_tbi_khomp",             "passed": True,  "note": ""},
                {"id": "hm_tbi_fs",                "passed": True,  "note": ""},
                {"id": "hm_signalmash_khomp",      "passed": True,  "note": ""},
                {"id": "hm_signalmash_fs",         "passed": True,  "note": ""},
                {"id": "hm_retell_ai",             "passed": True,  "note": ""},
                {"id": "hm_sms_only",              "passed": True,  "note": ""},
                {"id": "hm_sms_ai",                "passed": True,  "note": ""},
            ],
        }
    ]
}

if __name__ == "__main__":
    console.print("\n[bold cyan]Hourly Report Test[/bold cyan]")
    console.print("[dim]Fill in the manual fields. At the end you'll see the Slack message preview.[/dim]\n")

    form = run_hourly_form(FAKE_RESULTS)

    console.print("\n[bold green]── Slack Message Preview ──[/bold green]")
    console.print(build_hourly_message(form))

    console.print("\n  Send to Slack now?  1 Yes   2 No")
    resp = input("  → ").strip()
    if resp == "1":
        sent = send_hourly_report(form)
        if sent:
            console.print("[green]✓[/green] Sent!")
        else:
            console.print("[yellow]⚠[/yellow] SLACK_WEBHOOK_URL not set in .env")
    else:
        console.print("[dim]Not sent — test complete.[/dim]")
