from checklists.daily_qa import SubCall, CheckItem, Section

HEAVY_KHOMP_QA: list[Section] = [

    # ── 1/12  Account Used  ──────────────────────────────── item 1/31 ──
    Section(
        id="account_used",
        title="1/12  Account Used",
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

    # ── 2/12  Keypress Actions  ──────────────────────── items 2–8/31 ──
    Section(
        id="keypress_actions",
        title="2/12  Test Keypress Actions",
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
                trigger_call=True,
                call_instruction="Trigger a call, answer, then press the DNC key. Verify the number is suppressed, then remove suppression.",
            ),
        ],
    ),

    # ── 3/12  Dynamic Inserts  ───────────────────────── item 9/31 ─────
    Section(
        id="dynamic_inserts",
        title="3/12  Dynamic Inserts",
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

    # ── 4/12  AMD Detection  ────────────────────────── item 10/31 ─────
    Section(
        id="detection",
        title="4/12  AMD Detection",
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

    # ── 5/12  Auto-Connect  ─────────────────────────── item 11/31 ─────
    Section(
        id="auto_connect",
        title="5/12  Auto-Connect",
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

    # ── 6/12  TBI Khomp OB & IB  ──────────────────── items 12–14/31 ──
    Section(
        id="tbi_khomp",
        title="6/12  Outbound & Inbound — TBI Khomp",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice — TBI Khomp call should connect.",
        provider_key="tbi_khomp",
        items=[
            CheckItem(
                id="tbi_khomp_transfer",
                text="Transfer to a Call Destination OB & IB",
                provider_key="tbi_khomp",
            ),
            CheckItem(
                id="tbi_khomp_schedule",
                text="Scheduling Call OB & IB",
                note="Schedule a call and verify it appears in the system.",
                provider_key="tbi_khomp",
            ),
            CheckItem(
                id="tbi_khomp_dnc",
                text="DNC OB & IB",
                note="Make sure phone number is suppressed then remove from suppression.",
                trigger_call=True,
                call_instruction="Trigger a call, answer, then press the DNC key. Verify the number is suppressed, then remove suppression.",
                provider_key="tbi_khomp",
            ),
        ],
    ),

    # ── 7/12  TBI Freeswitch OB & IB  ─────────────── items 15–17/31 ──
    Section(
        id="tbi_fs",
        title="7/12  Outbound & Inbound — TBI Freeswitch",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice — TBI Freeswitch call should connect.",
        provider_key="tbi_fs",
        items=[
            CheckItem(
                id="tbi_fs_transfer",
                text="Transfer to a Call Destination OB & IB",
                provider_key="tbi_fs",
            ),
            CheckItem(
                id="tbi_fs_schedule",
                text="Scheduling Call OB & IB",
                note="Schedule a call and verify it appears in the system.",
                provider_key="tbi_fs",
            ),
            CheckItem(
                id="tbi_fs_dnc",
                text="DNC OB & IB",
                note="Make sure phone number is suppressed then remove from suppression.",
                trigger_call=True,
                call_instruction="Trigger a call, answer, then press the DNC key. Verify the number is suppressed, then remove suppression.",
                provider_key="tbi_fs",
            ),
        ],
    ),

    # ── 8/12  Signalmash Khomp OB & IB  ───────────── items 18–20/31 ──
    Section(
        id="signalmash_khomp",
        title="8/12  Outbound & Inbound — Signalmash Khomp",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice — Signalmash Khomp call should connect.",
        provider_key="signalmash_khomp",
        items=[
            CheckItem(
                id="sig_khomp_transfer",
                text="Transfer to a Call Destination OB & IB",
                provider_key="signalmash_khomp",
            ),
            CheckItem(
                id="sig_khomp_schedule",
                text="Scheduling Call OB & IB",
                note="Schedule a call and verify it appears in the system.",
                provider_key="signalmash_khomp",
            ),
            CheckItem(
                id="sig_khomp_dnc",
                text="DNC OB & IB",
                note="Make sure phone number is suppressed then remove from suppression.",
                trigger_call=True,
                call_instruction="Trigger a call, answer, then press the DNC key. Verify the number is suppressed, then remove suppression.",
                provider_key="signalmash_khomp",
            ),
        ],
    ),

    # ── 9/12  Signalmash Freeswitch OB & IB  ──────── items 21–23/31 ──
    Section(
        id="signalmash_fs",
        title="9/12  Outbound & Inbound — Signalmash Freeswitch",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice — Signalmash Freeswitch call should connect.",
        provider_key="signalmash_fs",
        items=[
            CheckItem(
                id="sig_fs_transfer",
                text="Transfer to a Call Destination OB & IB",
                provider_key="signalmash_fs",
            ),
            CheckItem(
                id="sig_fs_schedule",
                text="Scheduling Call OB & IB",
                note="Schedule a call and verify it appears in the system.",
                provider_key="signalmash_fs",
            ),
            CheckItem(
                id="sig_fs_dnc",
                text="DNC OB & IB",
                note="Make sure phone number is suppressed then remove from suppression.",
                trigger_call=True,
                call_instruction="Trigger a call, answer, then press the DNC key. Verify the number is suppressed, then remove suppression.",
                provider_key="signalmash_fs",
            ),
        ],
    ),

    # ── 10/12  RetellAI — Accident Office  ────────── items 24–26/31 ──
    Section(
        id="retell_ai",
        title="10/12  RetellAI — Accident Office Turyal V2.0",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice — RetellAI agent should connect and respond.",
        provider_key="accident_office",
        items=[
            CheckItem(
                id="retell_connecting",
                text="Call Connecting to RetellAI Agent, Agent is Responsive, Lead Details & Transfer",
                note="Call connects, agent responds, lead details are correct, call transfers.",
                provider_key="accident_office",
            ),
            CheckItem(
                id="retell_scheduling",
                text="Call Scheduling",
                note="Agent schedules a callback when requested.",
                provider_key="accident_office",
            ),
            CheckItem(
                id="retell_stop_dnc",
                text="Stop Dialing & DNC",
                note="Saying stop or DNC suppresses the number. Verify then remove suppression.",
                trigger_call=True,
                call_instruction='Trigger a call, answer, then say "Stop" or "DNC" to the agent. Verify the number is suppressed, then remove suppression.',
                provider_key="accident_office",
            ),
        ],
    ),

    # ── 11/12  SMS Only — Signalmash  ─────────────── items 27–30/31 ──
    Section(
        id="sms_only",
        title="11/12  SMS Only — Signalmash",
        trigger_call_at_start=True,
        start_instruction="Submit the lead — SMS should arrive on your test phone number.",
        provider_key="sms_signalmash",
        items=[
            CheckItem(
                id="sms_sent_received",
                text="SMS sent and received (SMS Only Campaign)",
                note="Outbound SMS is sent and received by the lead.",
                provider_key="sms_signalmash",
            ),
            CheckItem(
                id="sms_outbound",
                text="Outbound SMS are being sent and received",
                provider_key="sms_signalmash",
            ),
            CheckItem(
                id="sms_inbound",
                text="Inbound SMS received by Pipes",
                note="Reply from the test number — Pipes should receive the inbound SMS.",
                provider_key="sms_signalmash",
            ),
            CheckItem(
                id="sms_emoji",
                text="Inbound SMS with Emoji received by Pipes",
                note="Send an inbound SMS containing an emoji — Pipes should receive it correctly.",
                provider_key="sms_signalmash",
            ),
        ],
    ),

    # ── 12/12  SMS with AI — Signalmash  ──────────── item 31/31 ──────
    Section(
        id="sms_ai",
        title="12/12  SMS with AI — Signalmash",
        trigger_call_at_start=True,
        start_instruction="Submit the lead — AI SMS bot should engage and allow call scheduling.",
        provider_key="sms_ai_signalmash",
        items=[
            CheckItem(
                id="sms_ai_scheduling",
                text="Call scheduled via SMS AI Bot",
                note="Client schedules a call through SMS AI bot. Call status must remain 'Scheduled' so Pipes can call the lead.",
                provider_key="sms_ai_signalmash",
            ),
        ],
    ),
]
