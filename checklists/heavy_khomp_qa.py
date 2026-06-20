from checklists.daily_qa import SubCall, CheckItem, Section

HEAVY_KHOMP_QA: list[Section] = [

    # ── 1/5  Account Used  ─────────────────────────────────── item 1/11 ──
    Section(
        id="account_used",
        title="1/5  Account Used",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice and listen to the full IVR greeting.",
        items=[
            CheckItem(
                id="account_used",
                text="Account Used — IVR check",
                bullets=[
                    "IVR's outbound greeting and prompts are clear and complete.",
                    "IVR repeats once and drops the call if there's no keypress.",
                    "IVR's inbound greeting and prompts are clear and complete.",
                    "IVR repeats once and drops the call if there's no keypress (IB).",
                ],
            ),
        ],
    ),

    # ── 2/5  Keypress Actions  ─────────────────────────── items 2–8/11 ──
    Section(
        id="keypress_actions",
        title="2/5  Test Keypress Actions",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice. Press [3] Retrigger for each new option.",
        items=[
            CheckItem("kp_transfer",  "Transfer Call Destination OB & IB"),
            CheckItem("kp_sched_am",  "Schedule Tomorrow Morning OB & IB"),
            CheckItem("kp_sched_pm",  "Schedule Tomorrow Afternoon OB & IB"),
            CheckItem("kp_sched_eve", "Schedule Tomorrow Evening OB & IB"),
            CheckItem(
                id="kp_continue",
                text="Continue OB & IB",
                bullets=[
                    "Make sure call is transferred.",
                    "Make sure call is ended after pressing End Call.",
                ],
            ),
            CheckItem("kp_endcall", "End Call OB & IB"),
            CheckItem(
                id="kp_dnc",
                text="DNC OB & IB",
                note="Make sure phone number is suppressed then remove from suppression.",
            ),
        ],
    ),

    # ── 3/5  Dynamic Inserts — uses heavy_khomp_dynamic API  item 9/11 ──
    Section(
        id="dynamic_inserts",
        title="3/5  Dynamic Inserts",
        trigger_call_at_start=True,
        start_instruction="Answer the call and verify all dynamic fields are spoken correctly.",
        provider_key="heavy_khomp_dynamic",
        items=[
            CheckItem(
                id="dynamic_insert_check",
                text="Dynamic Inserts OB & IB",
                note="Verify: First Name, Last Name, City, State, Postal Code, Pipes Phone Number, SubID 1-10.",
                provider_key="heavy_khomp_dynamic",
            ),
        ],
    ),

    # ── 4/5  Detection  ───────────────────────────────── item 10/11 ─────
    Section(
        id="detection",
        title="4/5  AMD Detection",
        items=[
            CheckItem(
                id="amd_detection",
                text="AMD Detection — 4 sequential call tests",
                sub_calls=[
                    SubCall(
                        instruction='Answer and say "Hello" — IVR should play (live-person detected).',
                        note="Expected: IVR plays",
                    ),
                    SubCall(
                        instruction='Answer and say "Hello this is [Name]" — IVR should play.',
                        note="Expected: IVR plays",
                    ),
                    SubCall(
                        instruction='Answer and say "Hey this is [Name] with Pipes how may I help you?" — IVR should STOP.',
                        note="Expected: Detection = voicemail",
                    ),
                    SubCall(
                        instruction="Answer but say nothing — IVR should play (live-person detected).",
                        note="Expected: IVR plays",
                    ),
                ],
            ),
        ],
    ),

    # ── 5/5  Auto-Connect  ────────────────────────────── item 11/11 ─────
    Section(
        id="auto_connect",
        title="5/5  Auto-Connect",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice — call should auto-transfer without any keypress.",
        items=[
            CheckItem(
                id="auto_connect_check",
                text="Auto-Connect OB & IB",
                bullets=[
                    "Make sure call is transferred automatically when a lead answers.",
                    "Make sure call is scheduled for the next dialling pattern if declined/rejected.",
                ],
            ),
        ],
    ),
]
