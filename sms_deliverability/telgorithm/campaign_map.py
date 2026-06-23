import re

CAMPAIGN_MAP: dict[str, str] = {
    # HTM Primary
    "CLYDZKN": "HTM Primary",
    "C1Q2YL9": "HTM Primary",
    # NextGen Leads
    "C3RQ7YO": "NextGen Leads",
    # Moving companies
    "CCQBQ3O": "Roadway Moving",
    "CMW59PF": "Bold Moving and Storage",
    "CZIE208": "Bravo Moving",
    "CCWHLU6": "Joyce Van Lines",
    "CMZDS2N": "Property Leads",
    "C0JHMXZ": "Safeway Moving",
    "CEQM0P8": "Solomon & Sons Relocation Service Inc",
    "C1JYTUM": "Good Greek Moving & Storage",
    # Tax / Finance
    "CE0FENI": "Universal Accounting Center",
    "C5YUQ9Y": "Choice Tax Relief",
    # Healthcare
    "C8PEK71": "ACA Helpline, LLC",
    # Tech / Services
    "CLWEPEX": "NSP",
    "C9B5TGJ": "NSP",
    "CNIBSAZ": "NSP",
    "COKL6R8": "SailsFlow",
    "CWFQZOF": "SailsFlow",
    "CEAHZ7N": "SailsFlow",
    "CYDVAXA": "Vivint",
    "CGGR37V": "Lagoon Media",
    "CP4JQO0": "Apollo Interactive",
    "CRZBYXQ": "Apollo Interactive",
    "CVOJYYP": "Apollo Interactive",
    "C1EQQEO": "LeadScorz",
    "CSBHAKD": "LeadScorz",
    "CJ6YIN4": "LeadScorz",
    "CN8PYWQ": "Pipes Website Followup",
}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


SLUG_TO_COMPANY: dict[str, str] = {
    slugify(name): name for name in set(CAMPAIGN_MAP.values())
}
