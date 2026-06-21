import os
from datetime import date, timedelta

import httpx
from dotenv import dotenv_values
from flask import Blueprint, jsonify, render_template, request

from portal.validator.scenarios import REJECTION_CODES, SCENARIOS

bp = Blueprint("validator", __name__, template_folder="templates")

API_URL = "https://leads.pipes.ai/api/lead"

# Voice providers only (SMS uses a different flow)
VALIDATOR_PROVIDERS = [
    {"key": "heavy_khomp",         "name": "Heavy Khomp"},
    {"key": "heavy_khomp_dynamic", "name": "Heavy Khomp (Dynamic)"},
    {"key": "lite_khomp",          "name": "Lite Khomp"},
    {"key": "tbi_khomp",           "name": "TBI Khomp"},
    {"key": "tbi_fs",              "name": "TBI Freeswitch"},
    {"key": "signalmash_khomp",    "name": "Signalmash Khomp"},
    {"key": "signalmash_fs",       "name": "Signalmash Freeswitch"},
    {"key": "accident_office",     "name": "Accident Office (RetellAI)"},
]


def _env() -> dict:
    """Read .env fresh on each call so maintenance-page edits are reflected."""
    values = {}
    if os.path.exists(".env"):
        values = dict(dotenv_values(".env"))
    # Fall back to os.environ for any key not in .env
    return values


def _build_params(provider_key: str, overrides: dict) -> dict:
    env = _env()

    def v(key, default=""):
        return env.get(key) or os.environ.get(key, default)

    # Shared base params
    params = {
        "phone_number":      v("QA_PHONE_NUMBER",   "5122227114"),
        "ip_address":        v("QA_IP_ADDRESS",     "79.116.129.221"),
        "tcpa_consent":      "1",
        "tcpa_consent_date": date.today().isoformat(),
        "email":             v("QA_EMAIL",          "iccantimbuhan@gmail.com"),
        "jornaya_leadid":    v("QA_JORNAYA_LEADID", ""),
    }

    # Provider-specific params
    provider_params = {
        "heavy_khomp": {
            "api_key":    v("HEAVY_KHOMP_API_KEY"),
            "first_name": v("HEAVY_KHOMP_FIRST_NAME", "Justin Bieber"),
            "state":      v("HEAVY_KHOMP_STATE",      "FL"),
            "postal_code":v("HEAVY_KHOMP_POSTAL_CODE","32004"),
        },
        "heavy_khomp_dynamic": {
            "api_key":    v("HEAVY_KHOMP_DYNAMIC_API_KEY"),
            "first_name": v("HEAVY_KHOMP_DYNAMIC_FIRST_NAME", "Prince"),
            "last_name":  v("HEAVY_KHOMP_DYNAMIC_LAST_NAME",  "Canlas"),
            "city":       v("HEAVY_KHOMP_DYNAMIC_CITY",       "Manhattan"),
            "state":      v("HEAVY_KHOMP_DYNAMIC_STATE",      "New York"),
            "postal_code":v("HEAVY_KHOMP_DYNAMIC_POSTAL_CODE","10001"),
        },
        "lite_khomp": {
            "api_key":    v("LITE_KHOMP_API_KEY"),
            "first_name": v("LITE_KHOMP_FIRST_NAME", "John Lite"),
            "last_name":  v("LITE_KHOMP_LAST_NAME",  "Khomp"),
            "city":       v("LITE_KHOMP_CITY",        "Manhattan"),
            "state":      v("LITE_KHOMP_STATE",       "New York"),
            "postal_code":v("LITE_KHOMP_POSTAL_CODE", "10001"),
        },
        "tbi_khomp": {
            "api_key":    v("TBI_KHOMP_API_KEY"),
            "first_name": v("TBI_KHOMP_FIRST_NAME", "John TBI"),
            "last_name":  v("TBI_KHOMP_LAST_NAME",  "Khomp"),
            "state":      v("TBI_KHOMP_STATE",      "FL"),
            "postal_code":v("TBI_KHOMP_POSTAL_CODE","32004"),
        },
        "tbi_fs": {
            "api_key":    v("TBI_FS_API_KEY"),
            "first_name": v("TBI_FS_FIRST_NAME", "John TBI"),
            "last_name":  v("TBI_FS_LAST_NAME",  "Freeswitch"),
            "state":      v("TBI_FS_STATE",      "FL"),
            "postal_code":v("TBI_FS_POSTAL_CODE","32004"),
        },
        "signalmash_khomp": {
            "api_key":    v("SIGNALMASH_KHOMP_API_KEY"),
            "first_name": v("SIGNALMASH_KHOMP_FIRST_NAME", "John Signalmash"),
            "last_name":  v("SIGNALMASH_KHOMP_LAST_NAME",  "Khomp"),
            "state":      v("SIGNALMASH_KHOMP_STATE",      "FL"),
            "postal_code":v("SIGNALMASH_KHOMP_POSTAL_CODE","32004"),
        },
        "signalmash_fs": {
            "api_key":    v("SIGNALMASH_FS_API_KEY"),
            "first_name": v("SIGNALMASH_FS_FIRST_NAME", "John Signalmash"),
            "last_name":  v("SIGNALMASH_FS_LAST_NAME",  "Freeswitch"),
            "state":      v("SIGNALMASH_FS_STATE",      "FL"),
            "postal_code":v("SIGNALMASH_FS_POSTAL_CODE","32004"),
        },
        "accident_office": {
            "api_key":    v("ACCIDENT_OFFICE_API_KEY"),
            "first_name": v("ACCIDENT_OFFICE_FIRST_NAME", "Rene"),
            "state":      v("ACCIDENT_OFFICE_STATE",      "FL"),
            "postal_code":v("ACCIDENT_OFFICE_POSTAL_CODE","32004"),
            "subid_1":    v("ACCIDENT_OFFICE_SUBID_1", "test"),
            "subid_2":    v("ACCIDENT_OFFICE_SUBID_2", "test"),
        },
    }

    params.update(provider_params.get(provider_key, {}))

    # Apply overrides — resolve special sentinels
    for key, val in overrides.items():
        if val == "__91_days_ago__":
            val = (date.today() - timedelta(days=91)).isoformat()
        params[key] = val

    return params


def _parse_rejection(response_json: dict) -> str:
    """Extract the rejection reason from the API response."""
    # Common response shapes from Pipes API
    for field in ("reason", "message", "error", "rejection_reason", "status_message"):
        if field in response_json:
            return str(response_json[field]).lower().strip()
    # Sometimes the whole response is a string under 'status'
    status = response_json.get("status", "")
    if isinstance(status, str) and status.lower() not in ("accepted", "success", "ok"):
        return status.lower().strip()
    return ""


@bp.route("/")
def index():
    env = _env()
    # Pre-resolve env-based defaults for the template
    qa_phone  = env.get("QA_PHONE_NUMBER") or os.environ.get("QA_PHONE_NUMBER", "5122227114")
    qa_jornaya = env.get("QA_JORNAYA_LEADID") or os.environ.get("QA_JORNAYA_LEADID", "")
    days_ago_91 = (date.today() - timedelta(days=91)).isoformat()

    return render_template(
        "validator/index.html",
        providers=VALIDATOR_PROVIDERS,
        scenarios=SCENARIOS,
        rejection_codes=REJECTION_CODES,
        qa_phone=qa_phone,
        qa_jornaya=qa_jornaya,
        days_ago_91=days_ago_91,
    )


@bp.route("/run", methods=["POST"])
def run_test():
    data         = request.get_json(silent=True) or {}
    provider_key = data.get("provider_key", "heavy_khomp")
    overrides    = data.get("overrides", {})

    params = _build_params(provider_key, overrides)

    # Mask API key in the params we send back for display
    display_params = {k: ("••••••••" if k == "api_key" else v) for k, v in params.items()}

    try:
        resp = httpx.post(API_URL, data=params, timeout=15)
        resp_json = resp.json()
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    rejection = _parse_rejection(resp_json)
    accepted  = resp.status_code == 200 and not rejection

    return jsonify({
        "ok":           True,
        "accepted":     accepted,
        "rejection":    rejection,
        "status_code":  resp.status_code,
        "response":     resp_json,
        "params_sent":  display_params,
    })
