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
    start_instruction: str = ""


HEAVY_KHOMP_QA: list[Section] = [

    # ── 1/5  Account Used ────────────────────────────────────────────────────────
    Section(
        id="account_used",
        title="Account Used",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice and listen to the full IVR greeting.",
        items=[
            CheckItem(
                "ivr_ob_clarity",
                "Make sure IVR's outbound greeting and prompts are clear and complete during call.",
            ),
            CheckItem(
                "ivr_ob_repeat",
                "Make sure IVR repeats once and drops the call if there's no keypress.",
            ),
            CheckItem(
                "ivr_ib_clarity",
                "Make sure IVR's inbound greeting and prompts are clear and complete during call.",
                note="Pipes IVR Recording — Inbound",
            ),
            CheckItem(
                "ivr_ib_repeat",
                "Make sure IVR repeats once and drops the call if there's no keypress.",
                note="Pipes IVR Recording — Inbound",
            ),
        ],
    ),

    # ── 2/5  Keypress Actions ────────────────────────────────────────────────────
    Section(
        id="keypress_actions",
        title="Test Keypress Actions",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice. Press [R] to retrigger for each new option.",
        items=[
            CheckItem("kp_transfer",  "Transfer Call Destination OB & IB"),
            CheckItem("kp_sched_am",  "Schedule Tomorrow Morning OB & IB"),
            CheckItem("kp_sched_pm",  "Schedule Tomorrow Afternoon OB & IB"),
            CheckItem("kp_sched_eve", "Schedule Tomorrow Evening OB & IB"),
            CheckItem(
                "kp_continue",
                "Continue: Make sure call is transferred & Make sure call is ended after pressing End Call OB & IB",
            ),
            CheckItem("kp_endcall", "End Call OB & IB"),
            CheckItem(
                "kp_dnc",
                "DNC: Make sure phone number is suppressed then remove from suppression OB & IB",
            ),
        ],
    ),

    # ── 3/5  Dynamic Inserts ─────────────────────────────────────────────────────
    Section(
        id="dynamic_inserts",
        title="Dynamic Inserts OB & IB",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice. Verify each value is read correctly by the IVR.",
        items=[
            CheckItem(
                "di_all",
                "First Name, Last Name, City, State, Postal Code, Pipes Phone Number, SubID 1-10 OB & IB",
            ),
        ],
    ),

    # ── 4/5  Detection ───────────────────────────────────────────────────────────
    Section(
        id="amd_detection",
        title="Detection",
        items=[
            CheckItem(
                "amd_hello",
                'Send an outbound call, answer the call and say "Hello". IVR should play.',
                trigger_call=True,
                call_instruction='Answer your Google Voice and say "Hello"',
                note="Expected: IVR plays (live-person detected)",
            ),
            CheckItem(
                "amd_hello_name",
                'Send an outbound call, answer the call and say "Hello this is [Name]". IVR should play.',
                trigger_call=True,
                call_instruction='Answer and say "Hello this is [your name]"',
                note="Expected: IVR plays (live-person detected)",
            ),
            CheckItem(
                "amd_full_phrase",
                'Send an outbound call, answer the call and say "Hey this is [Name] with Pipes how may I help you?". IVR should stop. Detection will be voicemail.',
                trigger_call=True,
                call_instruction='Answer and say "Hey this is [Name] with Pipes how may I help you?"',
                note="Expected: IVR stops (voicemail detected)",
            ),
            CheckItem(
                "amd_silence",
                "Send an outbound call, answer the call and do not say anything. IVR should be played and detection will be live-person.",
                trigger_call=True,
                call_instruction="Answer your Google Voice but DO NOT say anything — stay completely silent",
                note="Expected: IVR plays (live-person detected)",
            ),
        ],
    ),

    # ── 5/5  Auto-Connect ────────────────────────────────────────────────────────
    Section(
        id="auto_connect",
        title="Auto-Connect",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice. Do NOT press any key — wait for auto-connect.",
        items=[
            CheckItem(
                "ac_outbound",
                "Outbound: Make sure call is transferred automatically when a lead answers the call. & Make sure call is scheduled for the next dialling pattern if call is declined/rejected.",
            ),
        ],
    ),
]
