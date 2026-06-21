import re

CAMPAIGN_MAP: dict[str, str] = {
    "CLYDZKN": "HTM Primary",
    "C1Q2YL9": "HTM Primary",
    "C3RQ7YO": "NextGen Leads",
    "CCQBQ3O": "Roadway Moving",
    "CMW59PF": "Bold Moving and Storage",
    "CZIE208": "Bravo Moving",
    "CCWHLU6": "Joyce Van Lines",
}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


SLUG_TO_COMPANY: dict[str, str] = {
    slugify(name): name for name in set(CAMPAIGN_MAP.values())
}
