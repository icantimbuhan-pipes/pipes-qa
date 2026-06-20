import os
from providers.base import fire, shared_params

NAME         = "Outbound & Inbound — TBI Khomp"
PROVIDER_KEY = "tbi_khomp"


def trigger() -> dict:
    return fire({
        **shared_params(),
        "api_key":     os.environ.get("TBI_KHOMP_API_KEY",    "1zLKxj7adY2JWplXedp6yNgPv8lOkBb3"),
        "first_name":  os.environ.get("TBI_KHOMP_FIRST_NAME", "John TBI"),
        "last_name":   os.environ.get("TBI_KHOMP_LAST_NAME",  "Khomp"),
        "state":       os.environ.get("TBI_KHOMP_STATE",      "FL"),
        "postal_code": os.environ.get("TBI_KHOMP_POSTAL_CODE","32004"),
    })
