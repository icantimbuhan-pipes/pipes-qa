import os
from providers.base import fire, shared_params

NAME         = "Dynamic Placeholder Testing — Heavy Khomp"
PROVIDER_KEY = "heavy_khomp_dynamic"


def trigger() -> dict:
    return fire({
        **shared_params(),
        "api_key":     os.environ.get("HEAVY_KHOMP_DYNAMIC_API_KEY",    "9drqYwLAyXzbopML6QRa8JmOQvlkVeBx"),
        "first_name":  os.environ.get("HEAVY_KHOMP_DYNAMIC_FIRST_NAME", "Prince"),
        "last_name":   os.environ.get("HEAVY_KHOMP_DYNAMIC_LAST_NAME",  "Canlas"),
        "city":        os.environ.get("HEAVY_KHOMP_DYNAMIC_CITY",       "Manhattan"),
        "state":       os.environ.get("HEAVY_KHOMP_DYNAMIC_STATE",      "New York"),
        "postal_code": os.environ.get("HEAVY_KHOMP_DYNAMIC_POSTAL_CODE","10001"),
        "subid_1":     os.environ.get("HEAVY_KHOMP_DYNAMIC_SUBID_1",    "Heavy Khomp One"),
        "subid_2":     os.environ.get("HEAVY_KHOMP_DYNAMIC_SUBID_2",    "Heavy Khomp Two"),
        "subid_3":     os.environ.get("HEAVY_KHOMP_DYNAMIC_SUBID_3",    "Heavy Khomp Three"),
        "subid_4":     os.environ.get("HEAVY_KHOMP_DYNAMIC_SUBID_4",    "Heavy Khomp Four"),
        "subid_5":     os.environ.get("HEAVY_KHOMP_DYNAMIC_SUBID_5",    "Heavy Khomp Five"),
        "subid_6":     os.environ.get("HEAVY_KHOMP_DYNAMIC_SUBID_6",    "Heavy Khomp Six"),
        "subid_7":     os.environ.get("HEAVY_KHOMP_DYNAMIC_SUBID_7",    "Heavy Khomp Seven"),
        "subid_8":     os.environ.get("HEAVY_KHOMP_DYNAMIC_SUBID_8",    "Heavy Khomp Eight"),
        "subid_9":     os.environ.get("HEAVY_KHOMP_DYNAMIC_SUBID_9",    "Heavy Khomp Nine"),
        "subid_10":    os.environ.get("HEAVY_KHOMP_DYNAMIC_SUBID_10",   "Heavy Khomp Ten"),
    })
