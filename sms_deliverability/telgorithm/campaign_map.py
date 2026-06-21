import re

CAMPAIGN_MAP: dict[str, str] = {
    "CMZDS2N": "Property Leads",
    "CE0FENI": "Universal Accounting Center",
    "C0JHMXZ": "Safeway Moving",
    "CEQM0P8": "Solomon & Sons Relocation Service Inc",
    "C1JYTUM": "Good Greek Moving & Storage",
    "CLWEPEX": "NSP",
    "C9B5TGJ": "NSP",
    "CNIBSAZ": "NSP",
    "C5YUQ9Y": "Choice Tax Relief",
    "C8PEK71": "ACA Helpline, LLC",
    "COKL6R8": "SailsFlow",
    "CWFQZOF": "SailsFlow",
    "CEAHZ7N": "SailsFlow",
}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# slug → company name (for URL routing)
SLUG_TO_COMPANY: dict[str, str] = {
    slugify(name): name for name in set(CAMPAIGN_MAP.values())
}
