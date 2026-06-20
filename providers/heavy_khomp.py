import os
import httpx
from datetime import date
from dotenv import load_dotenv
from checklists.heavy_khomp_qa import HEAVY_KHOMP_QA

load_dotenv()

NAME = "Outbound Heavy Khomp"
PROVIDER_KEY = "heavy_khomp"
API_URL = "https://leads.pipes.ai/api/lead"
CHECKLIST = HEAVY_KHOMP_QA


def trigger() -> dict:
    params = {
        "api_key": os.environ["HEAVY_KHOMP_API_KEY"],
        "phone_number": os.environ["QA_PHONE_NUMBER"],
        "ip_address": os.environ["QA_IP_ADDRESS"],
        "tcpa_consent": "1",
        "tcpa_consent_date": date.today().isoformat(),
        "first_name": os.environ.get("QA_FIRST_NAME", "Justin Bieber"),
        "email": os.environ["QA_EMAIL"],
        "jornaya_leadid": os.environ["QA_JORNAYA_LEADID"],
        "postal_code": os.environ.get("QA_POSTAL_CODE", "32004"),
        "state": os.environ.get("QA_STATE", "FL"),
    }
    r = httpx.post(API_URL, data=params, timeout=30)
    r.raise_for_status()
    return {"status": "ok", "http_code": r.status_code, "response": r.text}
