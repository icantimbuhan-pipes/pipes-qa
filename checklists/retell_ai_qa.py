from checklists.daily_qa import CheckItem, Section

RETELL_AI_QA: list[Section] = [

    Section(
        id="retell_ai",
        title="RetellAI — Accident Office",
        trigger_call_at_start=True,
        start_instruction="Answer your Google Voice — RetellAI agent should connect and respond.",
        items=[
            CheckItem(
                id="retell_connecting",
                text="Call Connecting to RetellAI Agent",
                note="Call should connect and RetellAI agent should pick up.",
            ),
            CheckItem(
                id="retell_responsive",
                text="Agent is Responsive",
                note="Agent should respond naturally to what you say.",
            ),
            CheckItem(
                id="retell_lead_transfer",
                text="Lead Details & Transfer",
                note="Agent should have correct lead details and transfer the call properly.",
            ),
            CheckItem(
                id="retell_scheduling",
                text="Call Scheduling",
                note="Agent should be able to schedule a callback when requested.",
            ),
            CheckItem(
                id="retell_stop_dnc",
                text="Stop Dialing & DNC",
                note="Saying stop or DNC should suppress the number. Verify then remove suppression.",
            ),
        ],
    ),
]
