"""
API validation test scenarios.
Each scenario posts to the Pipes API with specific param overrides and checks
the response against an expected rejection code (or expects acceptance).
"""

REJECTION_CODES = [
    "account paused", "already dnc", "blacklist word", "campaign is archived",
    "campaign is rejecting", "data source is paused", "duplicate email",
    "duplicate phone number", "duplicate vertical phone number",
    "fed DNC 90 safety check", "high risk", "invalid birth_date",
    "invalid caller ready campaign", "invalid data source", "invalid email address",
    "invalid form post", "invalid jornaya leadid", "invalid jornaya leadid audit",
    "invalid phone carrier", "invalid phone number", "invalid phone number format",
    "invalid postal code", "invalid state", "invalid tcpa", "invalid trusted form",
    "invalid uber validation", "invalid vertical", "max age validation",
    "min age validation", "no call buyers available", "no campaign found",
    "no destination available", "no dialing pattern", "no jornaya leadid provided",
    "no phone destination available", "non compliant jornaya ID",
    "rejected by destination", "unexpected system error",
]

SCENARIOS = [
    {
        "key":      "valid_jornaya",
        "name":     "Valid Jornaya Lead ID",
        "category": "Jornaya",
        "color":    "#5b6af0",
        "description": (
            "Post with your configured Jornaya Lead ID. "
            "If accepted, the system validated the ID correctly. "
            "If rejected for a non-Jornaya reason, that's also a pass for this test."
        ),
        "expected_rejection": None,
        "editable": [
            {"param": "jornaya_leadid", "label": "Jornaya Lead ID", "default": "__QA_JORNAYA_LEADID__"},
        ],
    },
    {
        "key":      "invalid_jornaya",
        "name":     "Invalid Jornaya Lead ID",
        "category": "Jornaya",
        "color":    "#5b6af0",
        "description": (
            "Post with a fake Jornaya Lead ID. "
            "System should reject with 'invalid jornaya leadid'."
        ),
        "expected_rejection": "invalid jornaya leadid",
        "editable": [
            {"param": "jornaya_leadid", "label": "Jornaya Lead ID", "default": "FAKE-JORNAYA-000000000000000000000"},
        ],
    },
    {
        "key":      "expired_tcpa",
        "name":     "Expired TCPA Consent (91 days)",
        "category": "TCPA",
        "color":    "#f59e0b",
        "description": (
            "Post with a consent date 91 days in the past. "
            "System should reject with 'fed DNC 90 safety check'."
        ),
        "expected_rejection": "fed DNC 90 safety check",
        "editable": [
            {"param": "tcpa_consent_date", "label": "Consent Date", "default": "__91_days_ago__"},
        ],
    },
    {
        "key":      "invalid_phone",
        "name":     "Invalid Phone Number",
        "category": "Phone",
        "color":    "#ec4899",
        "description": (
            "Post with an invalid phone number (0000000000). "
            "System should reject for invalid phone."
        ),
        "expected_rejection": "invalid phone number",
        "editable": [
            {"param": "phone_number", "label": "Phone Number", "default": "0000000000"},
        ],
    },
    {
        "key":      "invalid_postal",
        "name":     "Invalid Postal Code",
        "category": "Location",
        "color":    "#10b981",
        "description": (
            "Post with an invalid zip code (00000). "
            "System should reject for invalid postal code."
        ),
        "expected_rejection": "invalid postal code",
        "editable": [
            {"param": "postal_code", "label": "Postal Code", "default": "00000"},
        ],
    },
    {
        "key":      "invalid_state",
        "name":     "Invalid State",
        "category": "Location",
        "color":    "#10b981",
        "description": (
            "Post with an invalid state code (XX). "
            "System should reject for invalid state."
        ),
        "expected_rejection": "invalid state",
        "editable": [
            {"param": "state", "label": "State", "default": "XX"},
        ],
    },
    {
        "key":      "dnc_check",
        "name":     "DNC Status Check",
        "category": "DNC",
        "color":    "#ef4444",
        "description": (
            "Post with your QA phone number to check its DNC status. "
            "If rejected with 'already dnc', the number is suppressed — "
            "remove it from suppression, then re-run to confirm."
        ),
        "expected_rejection": None,
        "editable": [
            {"param": "phone_number", "label": "Phone Number", "default": "__QA_PHONE_NUMBER__"},
        ],
    },
    {
        "key":      "no_jornaya",
        "name":     "No Jornaya Lead ID",
        "category": "Jornaya",
        "color":    "#5b6af0",
        "description": (
            "Post without a Jornaya Lead ID (empty string). "
            "System should reject with 'no jornaya leadid provided'."
        ),
        "expected_rejection": "no jornaya leadid provided",
        "editable": [
            {"param": "jornaya_leadid", "label": "Jornaya Lead ID", "default": ""},
        ],
    },
]
