"""
Interactive daily QA runner.

    uv run python -m runner                        # all active providers
    uv run python -m runner --provider heavy-khomp # one provider
"""
import sys
import json
import importlib
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm
from rich.rule import Rule
from rich import box

from checklists.daily_qa import DAILY_QA
from runner.report import send_slack_report

console = Console()

PROVIDERS = {
    "heavy-khomp": "providers.heavy_khomp",
    # Uncomment as providers are configured:
    # "heavy-fs":   "providers.heavy_fs",
    # "lite-khomp": "providers.lite_khomp",
    # "lite-fs":    "providers.lite_fs",
}

REPORTS_DIR = Path("data/reports")


def _trigger_call(provider) -> bool:
    with console.status("[bold cyan]Triggering outbound call...", spinner="dots"):
        try:
            result = provider.trigger()
            console.print(f"  [green]✓[/green] Call triggered (HTTP {result['http_code']})")
            return True
        except Exception as e:
            console.print(f"  [red]✗[/red] Failed: {e}")
            return False


def _ask(item_text: str) -> tuple[bool, str]:
    passed = Confirm.ask("    [bold]Pass?[/bold]", default=True)
    note = ""
    if not passed:
        note = console.input("    [dim]Failure note (Enter to skip): [/dim]").strip()
    return passed, note


def _save_report(results: dict):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.fromisoformat(results["started_at"]).strftime("%Y%m%d_%H%M")
    path = REPORTS_DIR / f"{results['provider_key']}_{ts}.json"
    path.write_text(json.dumps(results, indent=2))
    return path


def run_provider(provider) -> dict:
    started_at = datetime.now()
    total_items = sum(len(s.items) for s in DAILY_QA)

    console.print(Panel(
        f"[bold white]{provider.NAME}[/bold white]\n[dim]{started_at.strftime('%Y-%m-%d  %H:%M')}[/dim]",
        title="[bold cyan]  PIPES QA — DAILY MONITORING  [/bold cyan]",
        border_style="cyan",
        padding=(1, 6),
    ))

    results = {
        "provider": provider.NAME,
        "provider_key": provider.PROVIDER_KEY,
        "started_at": started_at.isoformat(),
        "sections": [],
    }

    item_num = 0

    for sec_idx, section in enumerate(DAILY_QA):
        console.print(f"\n[bold yellow][{sec_idx + 1}/{len(DAILY_QA)}]  {section.title}[/bold yellow]")
        console.print(Rule(style="yellow dim"))

        sec_results = {"title": section.title, "items": []}

        if section.trigger_call_at_start:
            console.print()
            ok = _trigger_call(provider)
            if not ok:
                if Confirm.ask("  Call failed — skip this section?", default=False):
                    results["sections"].append(sec_results)
                    continue
            console.input("\n  [dim]Answer your Google Voice, then press [ENTER] when you're on the call...[/dim] ")

        for item in section.items:
            item_num += 1
            console.print()

            if item.trigger_call:
                console.print("  [cyan]📞  Triggering new call...[/cyan]")
                ok = _trigger_call(provider)
                if ok:
                    console.print(f"\n  [bold white]  ▶  {item.call_instruction}[/bold white]")
                    console.input("\n  [dim]Press [ENTER] when you're ready...[/dim] ")

            console.print(f"  [bold white][{item_num}/{total_items}][/bold white]  {item.text}")
            if item.note:
                console.print(f"  [dim]        → {item.note}[/dim]")

            passed, note = _ask(item.text)

            icon = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
            console.print(f"        {icon}" + (f"  — {note}" if note else ""))

            sec_results["items"].append({"id": item.id, "text": item.text, "passed": passed, "note": note})

        results["sections"].append(sec_results)

    all_items = [i for s in results["sections"] for i in s["items"]]
    passed_count = sum(1 for i in all_items if i["passed"])
    total_count = len(all_items)
    all_good = passed_count == total_count

    results.update({
        "finished_at": datetime.now().isoformat(),
        "passed": passed_count,
        "total": total_count,
    })

    # Summary table
    console.print("\n")
    table = Table(box=box.ROUNDED, border_style="green" if all_good else "red")
    table.add_column("Section", style="bold")
    table.add_column("Pass", justify="center", style="green")
    table.add_column("Fail", justify="center")
    for sec in results["sections"]:
        items = sec["items"]
        p = sum(1 for i in items if i["passed"])
        f = len(items) - p
        table.add_row(sec["title"], str(p), f"[red]{f}[/red]" if f > 0 else "[dim]—[/dim]")

    color = "green" if all_good else "red"
    summary = "ALL PASSED ✓" if all_good else f"{passed_count}/{total_count} PASSED"
    console.print(Panel(table, title=f"[bold {color}]  {summary}  [/bold {color}]", border_style=color))

    report_path = _save_report(results)
    console.print(f"  [dim]Report saved → {report_path}[/dim]")

    return results


def main():
    provider_key = None
    if "--provider" in sys.argv:
        idx = sys.argv.index("--provider")
        if idx + 1 < len(sys.argv):
            provider_key = sys.argv[idx + 1]

    if provider_key:
        if provider_key not in PROVIDERS:
            console.print(f"[red]Unknown provider:[/red] {provider_key}")
            console.print(f"Available: {', '.join(PROVIDERS)}")
            sys.exit(1)
        keys = [provider_key]
    else:
        keys = list(PROVIDERS.keys())

    for key in keys:
        provider = importlib.import_module(PROVIDERS[key])
        results = run_provider(provider)

        console.print()
        with console.status("[dim]Sending Slack report...[/dim]", spinner="dots"):
            try:
                sent = send_slack_report(results)
                if sent:
                    console.print("[green]✓[/green] Slack report sent.")
                else:
                    console.print("[yellow]⚠[/yellow]  SLACK_WEBHOOK_URL not set — add it to .env to enable reports.")
            except Exception as e:
                console.print(f"[red]✗[/red] Slack send failed: {e}")

        if len(keys) > 1 and key != keys[-1]:
            console.input("\n[dim]Press [ENTER] to continue to the next provider...[/dim] ")
