"""
Daily QA checklist for Outbound Heavy Khomp.

5 sections, ~40 items:
  1. Account Used          — IVR greeting & repeat behaviour (OB + IB)
  2. Keypress Actions      — every menu option tested OB & IB
  3. Dynamic Inserts       — verify each insert plays correctly OB & IB
  4. Detection             — 4 AMD scenarios, one fresh call each
  5. Auto-Connect          — automatic transfer & schedule-on-decline
"""
from dataclasses import dataclass


@dataclass
class CheckItem:
    id: str
    text: str
    note: str = ""
    trigger_call: bool = False
    call_instruction: str = ""


@dataclass
class Section:
    id: str
    title: str
    items: list[CheckItem]
    trigger_call_at_start: bool = False
    start_instruction: str = ""   # shown after call triggers, before items


HEAVY_KHOMP_QA: list[Section] = [

    # ── 1. Account Used ─────────────────────────────────────────────────────────
    Section(
        id="account_used",
        title="1. Account Used — IVR Greeting & Behaviour",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice. Listen to the full IVR greeting.",
        items=[
            CheckItem(
                "ivr_ob_clarity",
                "OB — IVR outbound greeting and prompts are clear and complete",
            ),
            CheckItem(
                "ivr_ob_repeat",
                "OB — IVR repeats once and drops the call if there's no keypress",
            ),
            CheckItem(
                "ivr_ib_clarity",
                "IB — IVR inbound greeting and prompts are clear and complete",
                note="Pipes IVR Recording — Inbound",
            ),
            CheckItem(
                "ivr_ib_repeat",
                "IB — IVR inbound repeats once and drops the call if there's no keypress",
            ),
        ],
    ),

    # ── 2. Keypress Actions ──────────────────────────────────────────────────────
    Section(
        id="keypress_actions",
        title="2. Keypress Actions — OB & IB",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice. Test each keypress option. Use [R] to retrigger for each new option.",
        items=[
            # Transfer
            CheckItem(
                "kp_transfer_ob",
                "Transfer Call Destination — Outbound",
                note="Make sure call is transferred",
            ),
            CheckItem(
                "kp_transfer_ib",
                "Transfer Call Destination — Inbound",
                note="Make sure call is transferred",
            ),
            # Schedule Morning
            CheckItem("kp_sched_am_ob", "Schedule Tomorrow Morning — Outbound"),
            CheckItem("kp_sched_am_ib", "Schedule Tomorrow Morning — Inbound"),
            # Schedule Afternoon
            CheckItem("kp_sched_pm_ob", "Schedule Tomorrow Afternoon — Outbound"),
            CheckItem("kp_sched_pm_ib", "Schedule Tomorrow Afternoon — Inbound"),
            # Schedule Evening
            CheckItem("kp_sched_eve_ob", "Schedule Tomorrow Evening — Outbound"),
            CheckItem("kp_sched_eve_ib", "Schedule Tomorrow Evening — Inbound"),
            # Continue
            CheckItem(
                "kp_continue_transfer_ob",
                "Continue — Outbound: call is transferred",
            ),
            CheckItem(
                "kp_continue_endcall_ob",
                "Continue — Outbound: call ends after pressing End Call",
            ),
            CheckItem(
                "kp_continue_transfer_ib",
                "Continue — Inbound: call is transferred",
            ),
            CheckItem(
                "kp_continue_endcall_ib",
                "Continue — Inbound: call ends after pressing End Call",
            ),
            # End Call
            CheckItem("kp_endcall_ob", "End Call — Outbound"),
            CheckItem("kp_endcall_ib", "End Call — Inbound"),
            # DNC
            CheckItem(
                "kp_dnc_ob",
                "DNC — Outbound",
                note="Suppress number, then remove from suppression",
            ),
            CheckItem(
                "kp_dnc_ib",
                "DNC — Inbound",
                note="Suppress number, then remove from suppression",
            ),
        ],
    ),

    # ── 3. Dynamic Inserts ───────────────────────────────────────────────────────
    Section(
        id="dynamic_inserts",
        title="3. Dynamic Inserts — OB & IB",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice. Verify each dynamic value is read correctly by the IVR.",
        items=[
            CheckItem("di_firstname_ob",  "First Name — Outbound"),
            CheckItem("di_firstname_ib",  "First Name — Inbound"),
            CheckItem("di_lastname_ob",   "Last Name — Outbound"),
            CheckItem("di_lastname_ib",   "Last Name — Inbound"),
            CheckItem("di_city_ob",       "City — Outbound"),
            CheckItem("di_city_ib",       "City — Inbound"),
            CheckItem("di_state_ob",      "State — Outbound"),
            CheckItem("di_state_ib",      "State — Inbound"),
            CheckItem("di_postal_ob",     "Postal Code — Outbound"),
            CheckItem("di_postal_ib",     "Postal Code — Inbound"),
            CheckItem("di_phone_ob",      "Pipes Phone Number — Outbound"),
            CheckItem("di_phone_ib",      "Pipes Phone Number — Inbound"),
            CheckItem("di_subid_ob",      "SubID 1-10 — Outbound",
                      note="Verify all SubID values are inserted correctly"),
            CheckItem("di_subid_ib",      "SubID 1-10 — Inbound",
                      note="Verify all SubID values are inserted correctly"),
        ],
    ),

    # ── 4. Detection ─────────────────────────────────────────────────────────────
    Section(
        id="amd_detection",
        title="4. Detection — AMD Tests",
        trigger_call_at_start=False,
        items=[
            CheckItem(
                "amd_hello",
                'Say "Hello" → IVR should play',
                trigger_call=True,
                call_instruction='Answer your Google Voice and say "Hello"',
                note="Expected: IVR plays (live-person detected)",
            ),
            CheckItem(
                "amd_hello_name",
                'Say "Hello this is [Name]" → IVR should play',
                trigger_call=True,
                call_instruction='Answer and say "Hello this is [your name]"',
                note="Expected: IVR plays (live-person detected)",
            ),
            CheckItem(
                "amd_full_phrase",
                'Say "Hey this is [Name] with Pipes..." → IVR should STOP',
                trigger_call=True,
                call_instruction='Answer and say "Hey this is [Name] with Pipes how may I help you?"',
                note="Expected: IVR stops (voicemail detected)",
            ),
            CheckItem(
                "amd_silence",
                "Answer but say nothing — IVR plays, live-person",
                trigger_call=True,
                call_instruction="Answer your Google Voice but DO NOT say anything — stay completely silent",
                note="Expected: IVR plays (live-person detected)",
            ),
        ],
    ),

    # ── 5. Auto-Connect ──────────────────────────────────────────────────────────
    Section(
        id="auto_connect",
        title="5. Auto-Connect — Outbound",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice. Do NOT press any key — wait for auto-connect.",
        items=[
            CheckItem(
                "ac_transfer",
                "Call is transferred automatically when lead answers",
                note="No keypress needed — transfer should happen on its own",
            ),
            CheckItem(
                "ac_decline",
                "Call scheduled for next dialling pattern if declined / rejected",
                note="Decline the call and verify it is rescheduled in the system",
            ),
        ],
    ),
]
