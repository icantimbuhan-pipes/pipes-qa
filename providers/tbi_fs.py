import os
from providers.base import fire, shared_params

NAME         = "Outbound & Inbound — TBI Freeswitch"
PROVIDER_KEY = "tbi_fs"


def trigger() -> dict:
    return fire({
        **shared_params(),
        "api_key":     os.environ.get("TBI_FS_API_KEY",    "GqwoajmWl6xk5ZXmBKE4JBQrKY0L9NgD"),
        "first_name":  os.environ.get("TBI_FS_FIRST_NAME", "John TBI"),
        "last_name":   os.environ.get("TBI_FS_LAST_NAME",  "Freeswitch"),
        "state":       os.environ.get("TBI_FS_STATE",      "FL"),
        "postal_code": os.environ.get("TBI_FS_POSTAL_CODE","32004"),
    })
