"""
Canonical dataclass definitions for all QA checklists.
Import SubCall, CheckItem, Section from here in every checklist file.
"""
from dataclasses import dataclass, field


@dataclass
class SubCall:
    """One step in a multi-call sequence (e.g. AMD Detection)."""
    instruction: str
    note: str = ""


@dataclass
class CheckItem:
    id: str
    text: str
    note: str = ""
    bullets: list[str] = field(default_factory=list)
    trigger_call: bool = False
    call_instruction: str = ""
    sub_calls: list[SubCall] = field(default_factory=list)
    provider_key: str = ""  # overrides the checklist default provider for this item


@dataclass
class Section:
    id: str
    title: str
    items: list[CheckItem]
    trigger_call_at_start: bool = False
    start_instruction: str = ""
    provider_key: str = ""  # overrides the checklist default for this section's trigger
