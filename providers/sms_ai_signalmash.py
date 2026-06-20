import os
from providers.base import fire, shared_params

NAME         = "SMS with AI — Signalmash"
PROVIDER_KEY = "sms_ai_signalmash"


def trigger() -> dict:
    return fire({
        **shared_params(),
        "api_key":     os.environ.get("SMS_AI_SIGNALMASH_API_KEY",    "By8dm0bjqg5nDRWm1NZAMO1WzvXYGekw"),
        "first_name":  os.environ.get("SMS_AI_SIGNALMASH_FIRST_NAME", "Jungkook"),
        "postal_code": os.environ.get("SMS_AI_SIGNALMASH_POSTAL_CODE","32004"),
    })
