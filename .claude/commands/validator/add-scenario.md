# /validator:add-scenario

Add a new rejection test scenario to the API Validator.

File: `portal/validator/scenarios.py`

---

## When to add a scenario

Add one whenever you want to regularly verify that a specific rejection code fires correctly — a new compliance rule, a carrier restriction, a data quality check, etc.

---

## Step 1 — Add the scenario to SCENARIOS

Open `portal/validator/scenarios.py` and append a new dict to the `SCENARIOS` list:

```python
{
    "key":      "my_scenario",          # snake_case, unique
    "name":     "Human-Readable Name",  # shown in the card header
    "category": "Category Label",       # e.g. "Jornaya", "TCPA", "Phone", "Location", "DNC"
    "color":    "#hex",                 # accent color for the category badge
    "description": (
        "One or two sentences describing what this test does "
        "and why the API should reject it."
    ),
    "expected_rejection": "exact rejection string",  # or None if any outcome is valid
    "editable": [
        {"param": "param_name", "label": "Display Label", "default": "override_value"},
    ],
},
```

---

## Field reference

### `expected_rejection`

The string the API returns in any of: `reason`, `message`, `error`, `rejection_reason`, `status_message`, or `status`. Case-insensitive substring match — `"invalid phone"` will match `"invalid phone number"`. Set to `None` if you just want to observe the result without a pass/fail verdict.

Known rejection codes:

```
account paused, already dnc, blacklist word, campaign is archived,
campaign is rejecting, data source is paused, duplicate email,
duplicate phone number, duplicate vertical phone number,
fed DNC 90 safety check, high risk, invalid birth_date,
invalid caller ready campaign, invalid data source, invalid email address,
invalid form post, invalid jornaya leadid, invalid jornaya leadid audit,
invalid phone carrier, invalid phone number, invalid phone number format,
invalid postal code, invalid state, invalid tcpa, invalid trusted form,
invalid uber validation, invalid vertical, max age validation,
min age validation, no call buyers available, no campaign found,
no destination available, no dialing pattern, no jornaya leadid provided,
no phone destination available, non compliant jornaya ID,
rejected by destination, unexpected system error
```

### `editable`

Each entry lets the user change one param value before running. The value in `default` is what pre-fills the input.

Special sentinel defaults:
- `"__QA_JORNAYA_LEADID__"` — pre-fills from `QA_JORNAYA_LEADID` env var
- `"__QA_PHONE_NUMBER__"` — pre-fills from `QA_PHONE_NUMBER` env var
- `"__91_days_ago__"` — pre-fills with today minus 91 days (YYYY-MM-DD)

### `color`

Category color for the badge. Existing palette:
- Jornaya: `#5b6af0`
- TCPA: `#f59e0b`
- Phone: `#ec4899`
- Location: `#10b981`
- DNC: `#ef4444`

---

## Step 2 — Verify it appears

The validator page (`/validator`) renders scenarios server-side — no rebuild needed. Hard-reload the page and the new card should appear.

Run the scenario against a configured provider to confirm:
- The expected rejection string matches what the API actually returns
- The card shows ✅ when it fires correctly

---

## Step 3 — Add to REJECTION_CODES (optional)

If the new scenario uses a rejection string not already in `REJECTION_CODES`, add it to the list at the top of `scenarios.py` to keep the reference complete.

---

## Example — adding a "Duplicate Phone" test

```python
{
    "key":      "duplicate_phone",
    "name":     "Duplicate Phone Number",
    "category": "Phone",
    "color":    "#ec4899",
    "description": (
        "Post with a phone number that has already been submitted recently. "
        "System should reject with 'duplicate phone number'."
    ),
    "expected_rejection": "duplicate phone number",
    "editable": [
        {"param": "phone_number", "label": "Phone Number", "default": "__QA_PHONE_NUMBER__"},
    ],
},
```
