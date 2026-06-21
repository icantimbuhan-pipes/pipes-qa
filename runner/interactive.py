"""
Interactive QA runner.

    uv run python -m runner                            # checklist selection menu
    uv run python -m runner --checklist daily-heavy-khomp
    uv run python -m runner --checklist retell-ai
    uv run python -m runner --checklist sms-only
    uv run python -m runner --checklist sms-ai
"""
import sys
import json
import importlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

from runner.report import send_slack_report
from runner.monitoring import run_monitoring_form
from runner.hourly_report import run_hourly_form, send_hourly_report

console = Console()

# ── Checklist registry ─────────────────────────────────────────────────────────

CHECKLISTS = [
    {
        "key":              "daily-heavy-khomp",
        "name":             "Daily QA — Heavy Khomp",
        "desc":             "31 items · 12 sections",
        "module":           "checklists.heavy_khomp_qa",
        "attr":             "HEAVY_KHOMP_QA",
        "default_provider": "heavy_khomp",
        "active":           True,
    },
    {
        "key":              "retell-ai",
        "name":             "RetellAI — Accident Office",
        "desc":             "5 items",
        "module":           "checklists.retell_ai_qa",
        "attr":             "RETELL_AI_QA",
        "default_provider": "accident_office",
        "active":           True,
    },
    {
        "key":              "sms-only",
        "name":             "SMS Only — Signalmash",
        "desc":             "4 items",
        "module":           "checklists.sms_only_qa",
        "attr":             "SMS_ONLY_QA",
        "default_provider": "sms_signalmash",
        "active":           True,
    },
    {
        "key":              "sms-ai",
        "name":             "SMS with AI — Signalmash",
        "desc":             "1 item",
        "module":           "checklists.sms_ai_qa",
        "attr":             "SMS_AI_QA",
        "default_provider": "sms_ai_signalmash",
        "active":           True,
    },
    {
        "key":              "hourly-heavy-khomp",
        "name":             "Hourly Monitoring QA — Heavy Khomp",
        "desc":             "9 items · all providers",
        "module":           "checklists.hourly_heavy_khomp_qa",
        "attr":             "HOURLY_HEAVY_KHOMP_QA",
        "default_provider": "heavy_khomp",
        "report_type":      "hourly",
        "active":           True,
    },
]

# ── Provider registry ──────────────────────────────────────────────────────────

PROVIDER_MODULES = {
    "heavy_khomp":         "providers.heavy_khomp",
    "heavy_khomp_dynamic": "providers.heavy_khomp_dynamic",
    "lite_khomp":          "providers.lite_khomp",
    "tbi_khomp":           "providers.tbi_khomp",
    "tbi_fs":              "providers.tbi_fs",
    "signalmash_khomp":    "providers.signalmash_khomp",
    "signalmash_fs":       "providers.signalmash_fs",
    "accident_office":     "providers.accident_office",
    "sms_signalmash":      "providers.sms_signalmash",
    "sms_ai_signalmash":   "providers.sms_ai_signalmash",
}

_provider_cache: dict = {}

def _get_provider(key: str):
    if key not in _provider_cache:
        mod_path = PROVIDER_MODULES.get(key)
        if not mod_path:
            raise ValueError(f"Unknown provider key: {key!r}")
        _provider_cache[key] = importlib.import_module(mod_path)
    return _provider_cache[key]

REPORTS_DIR = Path("data/reports")


# ── Input helper ───────────────────────────────────────────────────────────────

def _input(prompt: str = "") -> str:
    if prompt:
        console.print(prompt, end="")
    return input().strip()


# ── Progress / resume ──────────────────────────────────────────────────────────

def _progress_path(key: str) -> Path:
    return REPORTS_DIR / f".progress_{key.replace('-', '_')}.json"


def _save_progress(results: dict):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _progress_path(results["checklist_key"]).write_text(json.dumps(results, indent=2))


def _load_progress(key: str) -> Optional[dict]:
    path = _progress_path(key)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    return None


def _clear_progress(key: str):
    path = _progress_path(key)
    if path.exists():
        path.unlink()


def _check_resume(checklist_entry: dict, checklist) -> Optional[dict]:
    saved = _load_progress(checklist_entry["key"])
    if not saved:
        return None

    started   = datetime.fromisoformat(saved["started_at"])
    completed = sum(len(s["items"]) for s in saved.get("sections", []))
    total     = sum(len(s.items) for s in checklist)

    console.print(Panel(
        f"[yellow]Incomplete run found[/yellow]\n"
        f"[dim]Started {started.strftime('%Y-%m-%d at %H:%M')} — {completed}/{total} items done[/dim]",
        border_style="yellow",
        padding=(1, 4),
    ))
    console.print("  [bold](R)[/bold] Resume    [bold](N)[/bold] Start fresh")
    resp = input("  → ").strip().lower()
    if resp == "r":
        console.print(f"  [green]Resuming from item {completed + 1}...[/green]\n")
        return saved

    _clear_progress(checklist_entry["key"])
    return None


# ── Checklist selection menu ───────────────────────────────────────────────────

def _select_checklist() -> dict:
    console.print(Panel(
        "[bold white]Pipes QA — Daily Monitoring[/bold white]\n[dim]Select a checklist to run[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Num",  style="bold cyan", justify="right")
    table.add_column("Name", style="bold white")
    table.add_column("Info", style="dim")

    for i, cl in enumerate(CHECKLISTS, 1):
        status = cl["desc"] if cl["active"] else "[dim]🔧 Not configured[/dim]"
        table.add_row(f"[{i}]", cl["name"], status)

    console.print(table)

    while True:
        console.print("\n  Enter a number:")
        choice = input("  → ").strip()

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(CHECKLISTS):
                cl = CHECKLISTS[idx]
                if not cl["active"]:
                    console.print(f"  [yellow]{cl['name']} is not configured yet.[/yellow]")
                    continue
                return cl

        console.print(f"  [dim]Enter a number 1–{len(CHECKLISTS)}[/dim]")


# ── Call trigger helpers ───────────────────────────────────────────────────────

def _trigger_call(provider) -> bool:
    with console.status("[bold cyan]Triggering call...", spinner="dots"):
        try:
            result = provider.trigger()
            console.print(f"  [green]✓[/green] Call triggered — HTTP {result['http_code']}")
            return True
        except Exception as e:
            console.print(f"  [red]✗[/red] Failed: {e}")
            return False


def _trigger_and_wait(provider, instruction: str = "") -> bool:
    while True:
        ok = _trigger_call(provider)

        if not ok:
            console.print("  [bold]R[/bold] Retry    [bold]S[/bold] Skip")
            resp = input("  → ").strip().lower()
            if resp == "s":
                return False
            continue

        if instruction:
            console.print(f"\n  [bold white]▶  {instruction}[/bold white]")

        console.print("\n  [dim][ENTER] I'm on the call   [R] Retrigger   [S] Skip[/dim]")
        resp = input("  → ").strip().lower()

        if resp == "r":
            continue
        elif resp == "s":
            return False
        else:
            return True


# ── Pass/fail prompt ───────────────────────────────────────────────────────────

def _ask(item_num: int, provider=None) -> tuple[bool, str]:
    while True:
        console.print("\n  [dim]  1  Pass    2  Fail    3  Retrigger[/dim]")
        resp = input("  → ").strip().lower()

        if resp in ("1", "y", "yes", ""):
            console.print(f"  [bold green]{item_num} ✅[/bold green]")
            return True, ""

        elif resp in ("2", "n", "no"):
            note = input("  Note (Enter to skip): ").strip()
            console.print(f"  [bold red]{item_num} ❌[/bold red]" + (f"  — {note}" if note else ""))
            return False, note

        elif resp in ("3", "r"):
            if provider:
                console.print()
                _trigger_and_wait(provider)
            else:
                console.print("  [dim]No provider — can't retrigger.[/dim]")

        else:
            console.print("  [dim]1  Pass   2  Fail   3  Retrigger[/dim]")


# ── Report save ────────────────────────────────────────────────────────────────

def _save_report(results: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.fromisoformat(results["started_at"]).strftime("%Y%m%d_%H%M")
    path = REPORTS_DIR / f"{results['checklist_key']}_{ts}.json"
    path.write_text(json.dumps(results, indent=2))
    return path


# ── Main run loop ──────────────────────────────────────────────────────────────

def run_checklist(entry: dict, resume_data: Optional[dict] = None) -> dict:
    checklist_mod   = importlib.import_module(entry["module"])
    checklist       = getattr(checklist_mod, entry["attr"])
    default_pkey    = entry["default_provider"]

    completed: dict[str, dict] = {}
    if resume_data:
        for sec in resume_data.get("sections", []):
            for item in sec.get("items", []):
                completed[item["id"]] = item

    started_at  = datetime.fromisoformat(resume_data["started_at"]) if resume_data else datetime.now()
    total_items = sum(len(s.items) for s in checklist)

    console.print(Panel(
        f"[bold white]{entry['name']}[/bold white]\n[dim]{started_at.strftime('%Y-%m-%d  %H:%M')}[/dim]",
        title="[bold cyan]  PIPES QA — DAILY MONITORING  [/bold cyan]",
        border_style="cyan",
        padding=(1, 6),
    ))

    results = {
        "checklist":     entry["name"],
        "checklist_key": entry["key"],
        "started_at":    started_at.isoformat(),
        "sections":      [],
        # keep provider/provider_key for backward-compat with report.py
        "provider":      entry["name"],
        "provider_key":  entry["key"].replace("-", "_"),
    }

    item_num = 0

    for sec_idx, section in enumerate(checklist):
        sec_item_ids = {item.id for item in section.items}
        already_done = {iid for iid in sec_item_ids if iid in completed}
        sec_results  = {"title": section.title, "items": []}

        # Entire section already done — restore and skip
        if already_done == sec_item_ids:
            for item in section.items:
                item_num += 1
                sec_results["items"].append(completed[item.id])
            results["sections"].append(sec_results)
            console.print(f"\n[dim]  ↩  {section.title} — resumed ({len(sec_item_ids)} items)[/dim]")
            continue

        console.print(f"\n[bold yellow][{sec_idx + 1}/{len(checklist)}]  {section.title}[/bold yellow]")
        console.print(Rule(style="yellow dim"))

        # Section-level call trigger (uses section.provider_key if set, else default)
        if section.trigger_call_at_start:
            sec_pkey    = getattr(section, "provider_key", "") or default_pkey
            sec_provider = _get_provider(sec_pkey)
            if already_done:
                console.print(f"  [dim]Resuming — {len(already_done)} item(s) already done. Triggering a new call for the rest.[/dim]")
            instruction = getattr(section, "start_instruction", "") or ""
            answered = _trigger_and_wait(sec_provider, instruction=instruction)
            if not answered:
                results["sections"].append(sec_results)
                _save_progress(results)
                continue

        for item in section.items:
            item_num += 1
            console.print()

            # Already completed in a prior session
            if item.id in completed:
                saved = completed[item.id]
                icon  = "[green]✓[/green]" if saved["passed"] else "[red]✗[/red]"
                console.print(f"  [dim][{item_num}/{total_items}]  {item.text}  {icon} (resumed)[/dim]")
                sec_results["items"].append(saved)
                continue

            # Per-item provider lookup
            item_pkey    = getattr(item, "provider_key", "") or default_pkey
            item_provider = _get_provider(item_pkey)

            # Single-call item trigger
            if item.trigger_call:
                console.print("  [cyan]📞  Triggering new call...[/cyan]")
                answered = _trigger_and_wait(item_provider, instruction=item.call_instruction)
                if not answered:
                    item_num -= 1
                    console.print("  [dim]Skipped.[/dim]")
                    continue

            console.print(f"  [bold white][{item_num}/{total_items}][/bold white]  {item.text}")
            if item.note:
                console.print(f"  [dim]         → {item.note}[/dim]")

            for bullet in getattr(item, "bullets", []):
                console.print(f"  [dim]         • {bullet}[/dim]")

            # Multi-call item (AMD Detection)
            sub_calls = getattr(item, "sub_calls", [])
            if sub_calls:
                console.print(f"\n  [dim]This item has {len(sub_calls)} sequential call tests:[/dim]")
                for sc_idx, sub in enumerate(sub_calls, 1):
                    console.print()
                    console.print(f"  [bold cyan]Test {sc_idx}/{len(sub_calls)}[/bold cyan]  {sub.instruction}")
                    if sub.note:
                        console.print(f"  [dim]         → {sub.note}[/dim]")
                    answered = _trigger_and_wait(item_provider, instruction=sub.instruction)
                    if not answered:
                        console.print(f"  [dim]Skipped test {sc_idx}[/dim]")
                console.print(f"\n  [dim]All {len(sub_calls)} tests done.[/dim]")

            passed, note = _ask(item_num, provider=item_provider)

            sec_results["items"].append({"id": item.id, "text": item.text, "passed": passed, "note": note})

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
    _clear_progress(entry["key"])
    console.print(f"  [dim]Report saved → {report_path}[/dim]")

    return results


def main():
    checklist_key = None

    # --checklist flag (new) or --provider flag (backward compat)
    for flag in ("--checklist", "--provider"):
        if flag in sys.argv:
            idx = sys.argv.index(flag)
            if idx + 1 < len(sys.argv):
                checklist_key = sys.argv[idx + 1]
                # map old provider keys to new checklist keys
                if checklist_key in ("heavy-khomp", "heavy_khomp"):
                    checklist_key = "daily-heavy-khomp"
                break

    if checklist_key:
        entry = next((cl for cl in CHECKLISTS if cl["key"] == checklist_key), None)
        if not entry:
            console.print(f"[red]Unknown checklist:[/red] {checklist_key}")
            console.print("Available: " + ", ".join(cl["key"] for cl in CHECKLISTS))
            sys.exit(1)
    else:
        entry = _select_checklist()

    checklist_mod = importlib.import_module(entry["module"])
    checklist     = getattr(checklist_mod, entry["attr"])
    resume_data   = _check_resume(entry, checklist)
    results       = run_checklist(entry, resume_data=resume_data)

    if entry.get("report_type") == "hourly":
        form = run_hourly_form(results)
        console.print()
        with console.status("[dim]Sending Slack report...[/dim]", spinner="dots"):
            try:
                sent = send_hourly_report(form)
                if sent:
                    console.print("[green]✓[/green] Hourly Slack report sent.")
                else:
                    console.print("[yellow]⚠[/yellow]  SLACK_WEBHOOK_URL not set — add it to .env.")
            except Exception as e:
                console.print(f"[red]✗[/red] Slack send failed: {e}")
    else:
        results["monitoring"] = run_monitoring_form()
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
