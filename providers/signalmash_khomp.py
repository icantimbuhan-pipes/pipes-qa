import os
from providers.base import fire, shared_params

NAME         = "Outbound & Inbound — Signalmash Khomp"
PROVIDER_KEY = "signalmash_khomp"


def trigger() -> dict:
    return fire({
        **shared_params(),
        "api_key":     os.environ.get("SIGNALMASH_KHOMP_API_KEY",    "l1ejY8WOyB3P9E1P0eZwKJ7M4aD52Lzr"),
        "first_name":  os.environ.get("SIGNALMASH_KHOMP_FIRST_NAME", "John Signalmash"),
        "last_name":   os.environ.get("SIGNALMASH_KHOMP_LAST_NAME",  "Khomp"),
        "state":       os.environ.get("SIGNALMASH_KHOMP_STATE",      "FL"),
        "postal_code": os.environ.get("SIGNALMASH_KHOMP_POSTAL_CODE","32004"),
    })
