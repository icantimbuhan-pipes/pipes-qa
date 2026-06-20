from checklists.daily_qa import CheckItem, Section

SMS_AI_QA: list[Section] = [

    Section(
        id="sms_ai",
        title="SMS with AI — Signalmash",
        trigger_call_at_start=True,
        start_instruction="Submit the lead — AI SMS bot should engage and allow call scheduling.",
        items=[
            CheckItem(
                id="sms_ai_scheduling",
                text="Call scheduled via SMS AI Bot",
                note="Client schedules a call through SMS AI bot. Call status must remain 'Scheduled' so Pipes can call the lead.",
            ),
        ],
    ),
]
