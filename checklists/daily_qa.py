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


DAILY_QA: list[Section] = [
    Section(
        id="ivr_quality",
        title="IVR Quality Check",
        trigger_call_at_start=True,
        items=[
            CheckItem("ivr_ob_clarity", "IVR outbound greeting and prompts are clear and complete"),
            CheckItem("ivr_ob_repeat",  "IVR repeats once and drops the call if there's no keypress"),
            CheckItem("ivr_ib_clarity", "IVR inbound greeting and prompts are clear and complete"),
            CheckItem("ivr_ib_repeat",  "IVR inbound repeats once and drops the call if there's no keypress"),
        ],
    ),
    Section(
        id="outbound_dispositions",
        title="Outbound — Call Dispositions",
        items=[
            CheckItem("ob_transfer",  "Transfer Call Destination",    note="Make sure call is transferred"),
            CheckItem("ob_sched_am",  "Schedule Tomorrow Morning"),
            CheckItem("ob_sched_pm",  "Schedule Tomorrow Afternoon"),
            CheckItem("ob_sched_eve", "Schedule Tomorrow Evening"),
            CheckItem("ob_continue",  "Continue"),
            CheckItem("ob_end_call",  "End Call",                      note="Make sure call ends after pressing End Call"),
            CheckItem("ob_dnc",       "DNC",                           note="Verify number is suppressed, then remove suppression"),
        ],
    ),
    Section(
        id="inbound_dispositions",
        title="Inbound — Call Dispositions",
        items=[
            CheckItem("ib_transfer",  "Transfer Call Destination",    note="Make sure call is transferred"),
            CheckItem("ib_sched_am",  "Schedule Tomorrow Morning"),
            CheckItem("ib_sched_pm",  "Schedule Tomorrow Afternoon"),
            CheckItem("ib_sched_eve", "Schedule Tomorrow Evening"),
            CheckItem("ib_continue",  "Continue"),
            CheckItem("ib_end_call",  "End Call",                      note="Make sure call ends after pressing End Call"),
            CheckItem("ib_dnc",       "DNC",                           note="Verify number is suppressed, then remove suppression"),
        ],
    ),
    Section(
        id="amd_detection",
        title="AMD Detection Tests",
        items=[
            CheckItem(
                "amd_hello", 'Say "Hello" → IVR should play',
                trigger_call=True,
                call_instruction='Answer your Google Voice and say "Hello"',
                note="Expected: IVR plays (live-person detected)",
            ),
            CheckItem(
                "amd_hello_name", 'Say "Hello this is [Name]" → IVR should play',
                trigger_call=True,
                call_instruction='Answer and say "Hello this is [your name]"',
                note="Expected: IVR plays (live-person detected)",
            ),
            CheckItem(
                "amd_full_phrase", 'Say "Hey this is [Name] with Pipes..." → IVR should STOP',
                trigger_call=True,
                call_instruction='Answer and say "Hey this is [Name] with Pipes how may I help you?"',
                note="Expected: IVR stops (voicemail detected)",
            ),
            CheckItem(
                "amd_silence", "Answer but say nothing — IVR plays, live-person",
                trigger_call=True,
                call_instruction="Answer your Google Voice but DO NOT say anything — stay completely silent",
                note="Expected: IVR plays (live-person detected)",
            ),
        ],
    ),
]
