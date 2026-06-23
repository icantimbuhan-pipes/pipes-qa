STATUS_CODES: dict[str, str] = {
    "200": "Delivered",
    "005": "Undeliverable",
    "600": "Unregistered Traffic",
    "700": "Opt Out Filtered",
    "800": "Carrier Blocked",
    "900": "Carrier Disabled",
}

DELIVERED_CODE = "200"


def describe(code: str) -> str:
    return STATUS_CODES.get(str(code).strip(), f"Unknown ({code})")


def is_delivered(code: str) -> bool:
    return str(code).strip() == DELIVERED_CODE
