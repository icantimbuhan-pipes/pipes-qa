import os
from providers.base import fire, shared_params

NAME         = "QA — Accident Office Turyal V2.0 (Live Heavy Khomp)"
PROVIDER_KEY = "accident_office"


def trigger() -> dict:
    return fire({
        **shared_params(),
        "api_key":     os.environ.get("ACCIDENT_OFFICE_API_KEY",    "raeglQY6XBnPVEVkdvRDLKJjMwAG9yqo"),
        "first_name":  os.environ.get("ACCIDENT_OFFICE_FIRST_NAME", "Rene"),
        "state":       os.environ.get("ACCIDENT_OFFICE_STATE",      "FL"),
        "postal_code": os.environ.get("ACCIDENT_OFFICE_POSTAL_CODE","32004"),
        "subid_1":     os.environ.get("ACCIDENT_OFFICE_SUBID_1",    "test"),
        "subid_2":     os.environ.get("ACCIDENT_OFFICE_SUBID_2",    "test"),
    })
