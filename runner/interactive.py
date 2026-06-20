"""
Interactive daily QA runner.

    uv run python -m runner                        # shows provider menu
    uv run python -m runner --provider heavy-khomp # skip menu, run one directly
"""
import sys
import json
import importlib
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich import box

from checklists.daily_qa import DAILY_QA
from runner.report import send_slack_report

console = Console()

PROVIDERS = [
    {"key": "heavy-khomp", "name": "Outbound Heavy Khomp", "module": "providers.heavy_khomp", "active": True},
    {"key": "heavy-fs",    "name": "Outbound Heavy FS",    "module": "providers.heavy_fs",    "active": False},
    {"key": "lite-khomp",  "name": "Outbound Lite Khomp",  "module": "providers.lite_khomp",  "active": False},
    {"key": "lite-fs",     "name": "Outbound Lite FS",     "module": "providers.lite_fs",     "active": False},
]

REPORTS_DIR = Path("data/reports")


# ── Progress / resume ──────────────────────────────────────────────────────────

def _progress_path(provider_key: str) -> Path:
    return REPORTS_DIR / f".progress_{provider_key}.json"


def _save_progress(results: dict):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _progress_path(results["provider_key"]).write_text(json.dumps(results, indent=2))


def _load_progress(provider_key: str) -> dict | None:
    path = _progress_path(provider_key)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    return None


def _clear_progress(provider_key: str):
    path = _progress_path(provider_key)
    if path.exists():
        path.unlink()


def _check_resume(provider_key: str) -> dict | None:
    """If an incomplete run exists, ask the user whether to resume it."""
    saved = _load_progress(provider_key)
    if not saved:
        return None

    started = datetime.fromisoformat(saved["started_at"])
    completed = sum(len(s["items"]) for s in saved.get("sections", []))
    total     = sum(len(s.items) for s in DAILY_QA)

    console.print(Panel(
        f"[yellow]Incomplete run found[/yellow]\n"
        f"[dim]Started {started.strftime('%Y-%m-%d at %H:%M')} — {completed}/{total} items done[/dim]",
        border_style="yellow",
        padding=(1, 4),
    ))

    resp = console.input("  [bold](R)[/bold] Resume where you left off   [bold](N)[/bold] Start fresh  → ").strip().lower()
    if resp == "r":
        console.print(f"  [green]Resuming from item {completed + 1}...[/green]\n")
        return saved

    _clear_progress(provider_key)
    return None


# ── Provider selection menu ────────────────────────────────────────────────────

def _select_providers() -> list[dict]:
    console.print(Panel(
        "[bold white]Pipes QA — Daily Monitoring[/bold white]\n[dim]Select a provider to test[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Num",  style="bold cyan", justify="right")
    table.add_column("Name", style="bold white")
    table.add_column("Status")

    for i, p in enumerate(PROVIDERS, 1):
        status = "[green]✅ Active[/green]" if p["active"] else "[dim]🔧 Not configured[/dim]"
        table.add_row(f"[{i}]", p["name"], status)

    table.add_row("[A]", "All active providers", "")
    console.print(table)

    active = [p for p in PROVIDERS if p["active"]]

    while True:
        choice = console.input("\n  Select → ").strip().lower()

        if choice == "a":
            if not active:
                console.print("  [red]No active providers. Run /qa:add-provider to configure one.[/red]")
                continue
            return active

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(PROVIDERS):
                p = PROVIDERS[idx]
                if not p["active"]:
                    console.print(f"  [yellow]{p['name']} is not configured yet.[/yellow] Run [bold]/qa:add-provider[/bold].")
                    continue
                return [p]

        console.print("  [dim]Enter a number or A[/dim]")


# ── Call trigger helpers ───────────────────────────────────────────────────────

def _trigger_call(provider) -> bool:
    with console.status("[bold cyan]Triggering outbound call...", spinner="dots"):
        try:
            result = provider.trigger()
            console.print(f"  [green]✓[/green] Call triggered (HTTP {result['http_code']})")
            return True
        except Exception as e:
            console.print(f"  [red]✗[/red] Failed: {e}")
            return False


def _trigger_and_wait(provider, instruction: str = "") -> bool:
    """
    Trigger a call and wait for the user to answer.
      ENTER  — on the call, continue
      R      — missed it, retrigger
      S      — skip this item
    """
    while True:
        ok = _trigger_call(provider)

        if not ok:
            resp = console.input(
                "\n  Call failed.  [bold](R)[/bold] retry   [bold](S)[/bold] skip → "
            ).strip().lower()
            if resp == "s":
                return False
            continue

        if instruction:
            console.print(f"\n  [bold white]  ▶  {instruction}[/bold white]")

        console.print(
            "\n  [dim]"
            "[bold white][ENTER][/bold white] I'm on the call   "
            "[bold white][R][/bold white] Missed it — retrigger   "
            "[bold white][S][/bold white] Skip"
            "[/dim]"
        )
        resp = console.input("  → ").strip().lower()

        if resp == "r":
            console.print()
            continue
        elif resp == "s":
            return False
        else:
            return True


# ── Checklist helpers ──────────────────────────────────────────────────────────

def _ask(item_text: str, provider=None) -> tuple[bool, str]:
    """
      y / Enter  — pass
      n          — fail (prompts for a note)
      r          — retrigger call, re-ask same item
    """
    while True:
        resp = console.input(
            "    [bold]Pass?[/bold]  [dim][y] pass   [n] fail   [r] retrigger[/dim]  → "
        ).strip().lower()

        if resp in ("y", "yes", ""):
            return True, ""
        elif resp in ("n", "no"):
            note = console.input("    [dim]Failure note (Enter to skip): [/dim]").strip()
            return False, note
        elif resp == "r":
            if provider:
                console.print()
                _trigger_and_wait(provider)
            else:
                console.print("    [dim]No provider to retrigger.[/dim]")
        else:
            console.print("    [dim]y = pass   n = fail   r = retrigger[/dim]")


def _save_report(results: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.fromisoformat(results["started_at"]).strftime("%Y%m%d_%H%M")
    path = REPORTS_DIR / f"{results['provider_key']}_{ts}.json"
    path.write_text(json.dumps(results, indent=2))
    return path


# ── Main run loop ──────────────────────────────────────────────────────────────

def run_provider(provider, resume_data: dict | None = None) -> dict:
    # Build a lookup of already-completed items from a resumed run
    completed: dict[str, dict] = {}
    if resume_data:
        for sec in resume_data.get("sections", []):
            for item in sec.get("items", []):
                completed[item["id"]] = item

    started_at   = datetime.fromisoformat(resume_data["started_at"]) if resume_data else datetime.now()
    total_items  = sum(len(s.items) for s in DAILY_QA)

    console.print(Panel(
        f"[bold white]{provider.NAME}[/bold white]\n[dim]{started_at.strftime('%Y-%m-%d  %H:%M')}[/dim]",
        title="[bold cyan]  PIPES QA — DAILY MONITORING  [/bold cyan]",
        border_style="cyan",
        padding=(1, 6),
    ))

    results = {
        "provider":     provider.NAME,
        "provider_key": provider.PROVIDER_KEY,
        "started_at":   started_at.isoformat(),
        "sections":     [],
    }

    item_num = 0

    for sec_idx, section in enumerate(DAILY_QA):
        sec_item_ids   = {item.id for item in section.items}
        already_done   = {iid for iid in sec_item_ids if iid in completed}
        sec_results    = {"title": section.title, "items": []}

        # Entire section already done — restore and skip
        if already_done == sec_item_ids:
            for item in section.items:
                item_num += 1
                sec_results["items"].append(completed[item.id])
            results["sections"].append(sec_results)
            console.print(f"\n[dim]  ↩  {section.title} — resumed ({len(sec_item_ids)} items)[/dim]")
            continue

        console.print(f"\n[bold yellow][{sec_idx + 1}/{len(DAILY_QA)}]  {section.title}[/bold yellow]")
        console.print(Rule(style="yellow dim"))

        if section.trigger_call_at_start:
            console.print()
            if already_done:
                console.print(f"  [dim]Resuming — {len(already_done)} items already done. Triggering a new call for the rest.[/dim]")
            answered = _trigger_and_wait(provider)
            if not answered:
                results["sections"].append(sec_results)
                _save_progress(results)
                continue

        for item in section.items:
            item_num += 1
            console.print()

            # Already completed in a prior session — restore silently
            if item.id in completed:
                saved = completed[item.id]
                icon  = "[green]✓[/green]" if saved["passed"] else "[red]✗[/red]"
                console.print(f"  [dim][{item_num}/{total_items}]  {item.text}  {icon} (resumed)[/dim]")
                sec_results["items"].append(saved)
                continue

            if item.trigger_call:
                console.print("  [cyan]📞  Triggering new call...[/cyan]")
                answered = _trigger_and_wait(provider, instruction=item.call_instruction)
                if not answered:
                    item_num -= 1
                    console.print("  [dim]Skipped.[/dim]")
                    continue

            console.print(f"  [bold white][{item_num}/{total_items}][/bold white]  {item.text}")
            if item.note:
                console.print(f"  [dim]        → {item.note}[/dim]")

            passed, note = _ask(item.text, provider=provider)

            icon = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
            console.print(f"        {icon}" + (f"  — {note}" if note else ""))

            sec_results["items"].append({"id": item.id, "text": item.text, "passed": passed, "note": note})

            # Save progress after every answered item
            results["sections"].append(sec_results)
            _save_progress(results)
            results["sections"].pop()

        results["sections"].append(sec_results)
        _save_progress(results)

    # Final summary
    all_items    = [i for s in results["sections"] for i in s["items"]]
    passed_count = sum(1 for i in all_items if i["passed"])
    total_count  = len(all_items)
    all_good     = passed_count == total_count

    results.update({
        "finished_at": datetime.now().isoformat(),
        "passed":      passed_count,
        "total":       total_count,
    })

    console.print("\n")
    table = Table(box=box.ROUNDED, border_style="green" if all_good else "red")
    table.add_column("Section", style="bold")
    table.add_column("Pass",    justify="center", style="green")
    table.add_column("Fail",    justify="center")
    for sec in results["sections"]:
        items = sec["items"]
        p = sum(1 for i in items if i["passed"])
        f = len(items) - p
        table.add_row(sec["title"], str(p), f"[red]{f}[/red]" if f > 0 else "[dim]—[/dim]")

    color   = "green" if all_good else "red"
    summary = "ALL PASSED ✓" if all_good else f"{passed_count}/{total_count} PASSED"
    console.print(Panel(table, title=f"[bold {color}]  {summary}  [/bold {color}]", border_style=color))

    report_path = _save_report(results)
    _clear_progress(provider.PROVIDER_KEY)   # run complete — clean up progress file
    console.print(f"  [dim]Report saved → {report_path}[/dim]")

    return results


def main():
    provider_key = None
    if "--provider" in sys.argv:
        idx = sys.argv.index("--provider")
        if idx + 1 < len(sys.argv):
            provider_key = sys.argv[idx + 1]

    if provider_key:
        match = next((p for p in PROVIDERS if p["key"] == provider_key), None)
        if not match:
            console.print(f"[red]Unknown provider:[/red] {provider_key}")
            console.print("Available: " + ", ".join(p["key"] for p in PROVIDERS))
            sys.exit(1)
        selected = [match]
    else:
        selected = _select_providers()

    for entry in selected:
        provider    = importlib.import_module(entry["module"])
        resume_data = _check_resume(entry["key"])
        results     = run_provider(provider, resume_data=resume_data)

        console.print()
        with console.status("[dim]Sending Slack report...[/dim]", spinner="dots"):
            try:
                sent = send_slack_report(results)
                if sent:
                    console.print("[green]✓[/green] Slack report sent.")
                else:
                    console.print("[yellow]⚠[/yellow]  SLACK_WEBHOOK_URL not set — add it to .env.")
            except Exception as e:
                console.print(f"[red]✗[/red] Slack send failed: {e}")

        if entry != selected[-1]:
            console.input("\n[dim]Press [ENTER] to continue to the next provider...[/dim] ")
