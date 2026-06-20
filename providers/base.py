"""
Shared API trigger for all Pipes providers.
All providers call fire() with their specific params dict.

Provider contract — every provider module must expose:
    NAME: str          human-readable name
    PROVIDER_KEY: str  snake_case key (used in filenames and reports)
    def trigger() -> dict
"""
import os
import httpx
from datetime import date
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://leads.pipes.ai/api/lead"


def shared_params() -> dict:
    """Params common to every provider — pulled from .env."""
    return {
        "phone_number":      os.environ.get("QA_PHONE_NUMBER",   "5122227114"),
        "ip_address":        os.environ.get("QA_IP_ADDRESS",     "79.116.129.221"),
        "tcpa_consent":      "1",
        "tcpa_consent_date": date.today().isoformat(),
        "email":             os.environ.get("QA_EMAIL",          "iccantimbuhan@gmail.com"),
        "jornaya_leadid":    os.environ.get("QA_JORNAYA_LEADID", "93C30C8C-FA4F-D125-0622-2D176826CBED"),
    }


def fire(params: dict) -> dict:
    """POST to the Pipes leads API. Returns {"ok": bool, "http_code": int, "response": str}."""
    r = httpx.post(API_URL, data=params, timeout=30)
    r.raise_for_status()
    return {"ok": True, "http_code": r.status_code, "response": r.text}
