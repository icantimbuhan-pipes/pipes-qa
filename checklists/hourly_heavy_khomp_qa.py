from checklists.daily_qa import CheckItem, Section

HOURLY_HEAVY_KHOMP_QA: list[Section] = [

    Section(
        id="hourly_monitoring",
        title="Hourly Monitoring QA — Heavy Khomp",
        items=[
            CheckItem(
                id="hm_heavy_khomp",
                text="Transfer to a Call Destination — Heavy Khomp",
                trigger_call=True,
                call_instruction="Answer your Google Voice and verify the call transfers correctly.",
                provider_key="heavy_khomp",
            ),
            CheckItem(
                id="hm_heavy_khomp_dynamic",
                text="Dynamic Keypress to Transfer to a Call Destination",
                trigger_call=True,
                call_instruction="Answer and verify dynamic fields (name, subids) are correct, then keypress to transfer.",
                provider_key="heavy_khomp_dynamic",
            ),
            CheckItem(
                id="hm_tbi_khomp",
                text="Transfer to a Call Destination — TBI Khomp",
                trigger_call=True,
                call_instruction="Answer your Google Voice and verify the call transfers correctly.",
                provider_key="tbi_khomp",
            ),
            CheckItem(
                id="hm_tbi_fs",
                text="Transfer to a Call Destination — TBI Freeswitch",
                trigger_call=True,
                call_instruction="Answer your Google Voice and verify the call transfers correctly.",
                provider_key="tbi_fs",
            ),
            CheckItem(
                id="hm_signalmash_khomp",
                text="Transfer to a Call Destination — Signalmash Khomp",
                trigger_call=True,
                call_instruction="Answer your Google Voice and verify the call transfers correctly.",
                provider_key="signalmash_khomp",
            ),
            CheckItem(
                id="hm_signalmash_fs",
                text="Transfer to a Call Destination — Signalmash Freeswitch",
                trigger_call=True,
                call_instruction="Answer your Google Voice and verify the call transfers correctly.",
                provider_key="signalmash_fs",
            ),
            CheckItem(
                id="hm_retell_ai",
                text="Transfer to a Call Destination — RetellAI (Accident Office)",
                trigger_call=True,
                call_instruction="Answer and verify RetellAI agent connects and transfers the call.",
                provider_key="accident_office",
            ),
            CheckItem(
                id="hm_sms_only",
                text="SMS Only — Signalmash",
                trigger_call=True,
                call_instruction="Submit lead and verify SMS is sent and received.",
                provider_key="sms_signalmash",
            ),
            CheckItem(
                id="hm_sms_ai",
                text="SMS with AI — Signalmash",
                trigger_call=True,
                call_instruction="Submit lead and verify AI SMS bot responds correctly.",
                provider_key="sms_ai_signalmash",
            ),
        ],
    ),
]
