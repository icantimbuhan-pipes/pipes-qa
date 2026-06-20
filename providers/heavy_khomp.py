import os
from providers.base import fire, shared_params

NAME         = "Outbound Heavy Khomp"
PROVIDER_KEY = "heavy_khomp"


def trigger() -> dict:
    return fire({
        **shared_params(),
        "api_key":     os.environ.get("HEAVY_KHOMP_API_KEY",    ""),
        "first_name":  os.environ.get("HEAVY_KHOMP_FIRST_NAME", "Justin Bieber"),
        "state":       os.environ.get("HEAVY_KHOMP_STATE",      "FL"),
        "postal_code": os.environ.get("HEAVY_KHOMP_POSTAL_CODE","32004"),
    })
