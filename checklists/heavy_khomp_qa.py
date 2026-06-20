from dataclasses import dataclass, field


@dataclass
class SubCall:
    """A single call-trigger step inside a multi-call checklist item."""
    instruction: str
    note: str = ""


@dataclass
class CheckItem:
    id: str
    text: str
    note: str = ""
    bullets: list[str] = field(default_factory=list)   # sub-bullets shown under the item text
    trigger_call: bool = False                          # single call before this item
    call_instruction: str = ""
    sub_calls: list[SubCall] = field(default_factory=list)  # multiple sequential calls (e.g. detection)


@dataclass
class Section:
    id: str
    title: str
    items: list[CheckItem]
    trigger_call_at_start: bool = False
    start_instruction: str = ""


HEAVY_KHOMP_QA: list[Section] = [

    # ── 1/5  Account Used  ───────────────────────────────── item 1/11 ──────────
    Section(
        id="account_used",
        title="Account Used",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice and listen to the full IVR greeting.",
        items=[
            CheckItem(
                "account_used",
                "Account Used — IVR outbound check",
                bullets=[
                    "Make sure IVR's outbound greeting and prompts are clear and complete during call.",
                    "Make sure IVR repeats once and drops the call if there's no keypress.",
                ],
            ),
        ],
    ),

    # ── 2/5  Keypress Actions  ─────────────────────────── items 2–8/11 ─────────
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
                "Continue OB & IB",
                bullets=[
                    "Make sure call is transferred",
                    "Make sure call is ended after pressing End Call",
                ],
            ),
            CheckItem("kp_endcall", "End Call OB & IB"),
            CheckItem(
                "kp_dnc",
                "DNC OB & IB",
                note="Make sure phone number is suppressed then remove from suppression",
            ),
        ],
    ),

    # ── 3/5  Dynamic Inserts  ──────────────────────────── item 9/11 ─────────────
    Section(
        id="dynamic_inserts",
        title="Dynamic Inserts OB & IB",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice. Verify each value is read correctly by the IVR.",
        items=[
            CheckItem(
                "di_all",
                "First Name, Last Name, City, State, Postal Code, Pipes Phone Number, SubID 1-10",
            ),
        ],
    ),

    # ── 4/5  Detection  ────────────────────────────────── item 10/11 ────────────
    Section(
        id="amd_detection",
        title="Detection",
        items=[
            CheckItem(
                "amd_all",
                "AMD Detection — 4 outbound call tests",
                sub_calls=[
                    SubCall(
                        instruction='Answer and say "Hello"',
                        note='IVR should play (live-person detected)',
                    ),
                    SubCall(
                        instruction='Answer and say "Hello this is [your name]"',
                        note='IVR should play (live-person detected)',
                    ),
                    SubCall(
                        instruction='Answer and say "Hey this is [Name] with Pipes how may I help you?"',
                        note='IVR should STOP (voicemail detected)',
                    ),
                    SubCall(
                        instruction='Answer but say NOTHING — stay completely silent',
                        note='IVR should play (live-person detected)',
                    ),
                ],
            ),
        ],
    ),

    # ── 5/5  Auto-Connect  ─────────────────────────────── item 11/11 ───────────
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
