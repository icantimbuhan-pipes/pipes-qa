import os
from providers.base import fire, shared_params

NAME         = "Outbound Lite Khomp"
PROVIDER_KEY = "lite_khomp"


def trigger() -> dict:
    return fire({
        **shared_params(),
        "api_key":     os.environ.get("LITE_KHOMP_API_KEY",    ""),
        "first_name":  os.environ.get("LITE_KHOMP_FIRST_NAME", "John Lite"),
        "last_name":   os.environ.get("LITE_KHOMP_LAST_NAME",  "Khomp"),
        "city":        os.environ.get("LITE_KHOMP_CITY",       "Manhattan"),
        "state":       os.environ.get("LITE_KHOMP_STATE",      "New York"),
        "postal_code": os.environ.get("LITE_KHOMP_POSTAL_CODE","10001"),
    })
