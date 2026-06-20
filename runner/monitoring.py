"""
Hourly monitoring form — runs after the QA checklist.
Collects carrier statuses, latency, errors, and sends it all in one Slack report.
"""
from datetime import datetime
from rich.console import Console
from rich.rule import Rule
from rich.panel import Panel

console = Console()

CARRIERS  = ["ThinQ", "TBI Telco", "Signalmash"]

CHANNELS = [
    ("ob_khomp", "Outbound Dialing Khomp"),
    ("ob_fs",    "Outbound Dialing FS"),
    ("inbound",  "Inbound Dialling"),
]

CHECKS = [
    ("keypress_actions", "Keypress Actions"),
    ("sms_opt_out",      "SMS Opt Out"),
    ("ai_sms",           "AI SMS — Bot responsive and scheduling calls"),
    ("dynamic_inserts",  "Dynamic Inserts"),
]


def _ask_status(label: str) -> dict:
    """1 Working  2 Issue  Enter = Working (default)"""
    console.print(f"\n  [bold white]{label}[/bold white]")
    console.print("  [dim]1  Working    2  Issue[/dim]")
    resp = input("  → ").strip()

    if resp == "2":
        note = input("  Note: ").strip()
        console.print(f"  [red]2 ❌[/red]" + (f"  — {note}" if note else ""))
        return {"status": "issue", "note": note}

    console.print(f"  [green]1 ✅[/green]")
    return {"status": "working", "note": ""}


def run_monitoring_form() -> dict:
    """Interactive monitoring form. Returns a dict merged into the QA results."""
    console.print()
    console.print(Panel(
        "[bold white]Hourly Monitoring Report[/bold white]\n"
        "[dim]Fill in after finishing the checklist — press Enter to accept defaults[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))

    data: dict = {"timestamp": datetime.now().isoformat()}

    # ── Khomp peak ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[yellow]Khomp Peak[/yellow]", style="yellow dim"))
    console.print("\n  Peak concurrent calls (Enter to skip):")
    peak_val  = input("  → ").strip()
    console.print("  Time of peak (e.g. 14:07):")
    peak_time = input("  → ").strip()
    data["khomp_peak"] = {
        "concurrent": int(peak_val) if peak_val.isdigit() else None,
        "time":       peak_time or None,
    }

    # ── Carrier statuses ─────────────────────────────────────────────────────────
    data["carriers"] = {}
    for channel_key, channel_name in CHANNELS:
        console.print()
        console.print(Rule(f"[yellow]{channel_name}[/yellow]", style="yellow dim"))
        data["carriers"][channel_key] = {}
        for carrier in CARRIERS:
            data["carriers"][channel_key][carrier] = _ask_status(carrier)

    # ── Other checks ─────────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[yellow]Other Checks[/yellow]", style="yellow dim"))
    data["checks"] = {}
    for check_key, check_name in CHECKS:
        data["checks"][check_key] = _ask_status(check_name)

    # ── RetellAI ─────────────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[yellow]RetellAI[/yellow]", style="yellow dim"))
    data["retell"] = _ask_status("RetellAI test agent (responsive, transfer working, post-call analysis passing)")

    console.print("\n  Latency — hello to play greeting (3 readings, Enter to skip):")
    latency = []
    for i in range(1, 4):
        val = input(f"  Reading {i} (secs): ").strip()
        if val:
            try:
                latency.append(float(val))
            except ValueError:
                pass
    data["retell"]["latency"] = latency

    # ── Rollbar ──────────────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[yellow]Rollbar Errors[/yellow]", style="yellow dim"))
    console.print("\n  Errors in Production (last hour) — 0 or count:")
    err_count = input("  → ").strip()
    err_int   = int(err_count) if err_count.isdigit() else 0
    err_note  = input("  Note (Enter to skip): ").strip() if err_int > 0 else ""
    data["rollbar"] = {"errors": err_int, "note": err_note}

    # ── Khomp Classification ─────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[yellow]Khomp Classification (last 8 hrs)[/yellow]", style="yellow dim"))
    console.print()
    kc_date  = input("  Date (e.g. 06/18/2026): ").strip()
    kc_short = input("  Short %   (e.g. 6.32):  ").strip()
    kc_long  = input("  Long %    (e.g. 0.03):  ").strip()
    kc_tmout = input("  Timeout % (e.g. 1.35):  ").strip()
    data["khomp_classification"] = {
        "date":        kc_date,
        "short_pct":   kc_short,
        "long_pct":    kc_long,
        "timeout_pct": kc_tmout,
    }

    # ── Zapier ───────────────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[yellow]Zapier[/yellow]", style="yellow dim"))
    console.print()
    zap_usage  = input("  Task usage (e.g. 5,922/50k):      ").strip()
    zap_reset  = input("  Resets in  (e.g. 4 weeks):        ").strip()
    console.print("  Zap errors? (Enter for none, or describe):")
    zap_err    = input("  → ").strip() or "None"
    zap_action = input("  Action needed (Enter for None):   ").strip() or "None"
    data["zapier"] = {
        "task_usage":    zap_usage,
        "resets_in":     zap_reset,
        "errors":        zap_err,
        "action_needed": zap_action,
    }

    console.print()
    console.print("[green]✓[/green] Monitoring form complete.\n")
    return data
