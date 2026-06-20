import os
from providers.base import fire, shared_params

NAME         = "Outbound & Inbound — Signalmash Freeswitch"
PROVIDER_KEY = "signalmash_fs"


def trigger() -> dict:
    return fire({
        **shared_params(),
        "api_key":     os.environ.get("SIGNALMASH_FS_API_KEY",    "oJegx2wlP48kbRr6alRndmVAKD3j0O6Q"),
        "first_name":  os.environ.get("SIGNALMASH_FS_FIRST_NAME", "John Signalmash"),
        "last_name":   os.environ.get("SIGNALMASH_FS_LAST_NAME",  "Freeswitch"),
        "state":       os.environ.get("SIGNALMASH_FS_STATE",      "FL"),
        "postal_code": os.environ.get("SIGNALMASH_FS_POSTAL_CODE","32004"),
    })
