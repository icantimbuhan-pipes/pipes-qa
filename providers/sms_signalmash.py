import os
from providers.base import fire, shared_params

NAME         = "SMS Only — Signalmash"
PROVIDER_KEY = "sms_signalmash"


def trigger() -> dict:
    return fire({
        **shared_params(),
        "api_key":     os.environ.get("SMS_SIGNALMASH_API_KEY",    "zGLD21ayl3AY8paBrGZoX9m6d5xwbjJV"),
        "first_name":  os.environ.get("SMS_SIGNALMASH_FIRST_NAME", "Taehyung"),
        "postal_code": os.environ.get("SMS_SIGNALMASH_POSTAL_CODE","32004"),
    })
