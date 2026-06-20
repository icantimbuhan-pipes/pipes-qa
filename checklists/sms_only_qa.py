from checklists.daily_qa import CheckItem, Section

SMS_ONLY_QA: list[Section] = [

    Section(
        id="sms_only",
        title="SMS Only — Signalmash",
        trigger_call_at_start=True,
        start_instruction="Submit the lead — SMS should arrive on your test phone number.",
        items=[
            CheckItem(
                id="sms_sent_received",
                text="SMS sent and received (SMS Only Campaign)",
                note="Make sure outbound SMS is being sent and received by the lead.",
            ),
            CheckItem(
                id="sms_outbound",
                text="Outbound SMS are being sent and received",
                note="Verify SMS goes out and lead receives it.",
            ),
            CheckItem(
                id="sms_inbound",
                text="Inbound SMS received by Pipes",
                note="Reply from the test number — Pipes should receive the inbound SMS.",
            ),
            CheckItem(
                id="sms_emoji",
                text="Inbound SMS with Emoji received by Pipes",
                note="Send an inbound SMS containing an emoji — Pipes should receive it correctly.",
            ),
        ],
    ),
]
