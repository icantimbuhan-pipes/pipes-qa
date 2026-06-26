"""
Shared SMS deliverability analysis knowledge base.
Maps error codes → root cause, action, severity, category.
Used by Telgorithm and Signalmash analysis pages and Slack payloads.
"""

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH     = "high"
SEVERITY_MEDIUM   = "medium"
SEVERITY_LOW      = "low"

CAT_LIST     = "List Quality"
CAT_CARRIER  = "Carrier Block"
CAT_CONTENT  = "Content Filter"
CAT_SENDER   = "Sender Config"
CAT_NETWORK  = "Network"
CAT_TRANSIENT = "Transient"
CAT_COMPLIANCE = "Compliance"

THRESHOLD_CRITICAL = 94.0
THRESHOLD_WARNING  = 95.0


def delivery_status(rate: float) -> str:
    """Return 'healthy', 'warning', or 'critical' for a delivery rate."""
    if rate >= THRESHOLD_WARNING:
        return "healthy"
    if rate >= THRESHOLD_CRITICAL:
        return "warning"
    return "critical"


# ── Signalmash DLR code analysis ──────────────────────────────────────────────

SIGNALMASH_KB: dict[str, dict] = {
    "0": {
        "label": "Delivered",
        "severity": SEVERITY_LOW,
        "category": "",
        "root_cause": "",
        "action": "",
    },
    "1": {
        "label": "Source not found",
        "severity": SEVERITY_CRITICAL,
        "category": CAT_SENDER,
        "root_cause": "The FROM number is not provisioned in Signalmash or has been deregistered. The routing table has no entry for this sender.",
        "action": "Check FROM number status in Signalmash portal. Deregistered numbers must be replaced and re-provisioned before the next send.",
    },
    "6": {
        "label": "Absent subscriber",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_TRANSIENT,
        "root_cause": "Recipient device is powered off or out of coverage at time of delivery.",
        "action": "Retry after 24 hours. If still failing after 3 attempts, remove from active campaigns.",
    },
    "15": {
        "label": "Screening block",
        "severity": SEVERITY_HIGH,
        "category": CAT_CONTENT,
        "root_cause": "Carrier spam filter flagged the message content. Common triggers: debt/financial language, missing opt-out text, all-caps, URL shorteners, or excessive urgency phrases.",
        "action": "Pull the message templates sent to this carrier. Review against spam trigger list. Ensure every message has 'Reply STOP to opt out'. Avoid: guaranteed, risk-free, debt relief, ACT NOW, excessive punctuation.",
    },
    "21": {
        "label": "Expired",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_TRANSIENT,
        "root_cause": "Message validity period expired before the device came back online.",
        "action": "Reduce message validity period setting. Retry once. Persistent absent subscribers should be removed.",
    },
    "31": {
        "label": "Subscriber busy (inbox full)",
        "severity": SEVERITY_LOW,
        "category": CAT_TRANSIENT,
        "root_cause": "Recipient's SMS inbox is full.",
        "action": "Retry after a few hours. No list action needed.",
    },
    "32": {
        "label": "Delivery failure",
        "severity": SEVERITY_HIGH,
        "category": CAT_NETWORK,
        "root_cause": "Carrier-side delivery failure — network congestion, SMSC error, or routing issue.",
        "action": "Retry once. If this code exceeds 1% of total volume, contact Signalmash support with your batch ID.",
    },
    "34": {
        "label": "Message validity expired",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_TRANSIENT,
        "root_cause": "Same as code 21 — message held in queue past the validity window.",
        "action": "Adjust validity period settings. Retry absent subscribers once.",
    },
    "45": {
        "label": "MDN BLOCKED",
        "severity": SEVERITY_CRITICAL,
        "category": CAT_CARRIER,
        "root_cause": "Destination number is on the carrier's MDN blacklist. Caused by: prior STOP reply, carrier complaint flag, or deactivated/recycled number. T-Mobile and Verizon Wireless maintain the most aggressive MDN blacklists.",
        "action": "Remove all code-45 numbers from ALL campaigns immediately. Add to DNC list. If MDN BLOCKED exceeds 5% of volume, audit the lead source quality.",
    },
    "60": {
        "label": "Campaign not active on AT&T",
        "severity": SEVERITY_CRITICAL,
        "category": CAT_CARRIER,
        "root_cause": "The 10DLC campaign is not registered or not approved on AT&T's network. AT&T requires explicit per-campaign approval, separate from general TCR registration.",
        "action": "Log into TCR, select the campaign, and check AT&T approval status. Submit or appeal if missing. AT&T approval typically takes 1–3 business days.",
    },
    "61": {
        "label": "Destination blocked",
        "severity": SEVERITY_HIGH,
        "category": CAT_CARRIER,
        "root_cause": "Network-level block on the destination number (similar to MDN BLOCKED but at the carrier routing layer).",
        "action": "Remove number from campaigns. Investigate if a pattern appears on a specific carrier.",
    },
    "64": {
        "label": "Blocked — quota exceeded",
        "severity": SEVERITY_HIGH,
        "category": CAT_SENDER,
        "root_cause": "Too many messages sent from this campaign too quickly. The campaign daily or hourly cap has been hit.",
        "action": "Throttle sending velocity. Stay within the campaign's daily cap. Request higher limits from Signalmash if volume is legitimate.",
    },
    "66": {
        "label": "Data coding scheme blocked",
        "severity": SEVERITY_HIGH,
        "category": CAT_CONTENT,
        "root_cause": "Message uses Unicode characters (emoji, smart quotes, em-dashes, curly apostrophes) that the recipient carrier does not support.",
        "action": "Convert all message templates to GSM-7 ASCII only. Remove emoji, smart quotes (“”), em-dashes (—), and any non-standard characters. Use plain straight quotes and hyphens.",
    },
    "69": {
        "label": "Sending limit reached",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_SENDER,
        "root_cause": "Account or campaign daily message cap has been hit.",
        "action": "Request increased limits from Signalmash or spread the volume over multiple days.",
    },
    "153": {
        "label": "Absent subscriber",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_TRANSIENT,
        "root_cause": "Device is unreachable — powered off, out of coverage, or roaming without service.",
        "action": "Retry after 24 hours. Remove if still absent after 3 attempts over 72 hours.",
    },
    "201": {
        "label": "Absent subscriber, IMSI detached",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_TRANSIENT,
        "root_cause": "SIM has been removed from the device or the device has been powered off for an extended period. Often indicates a churned or inactive subscriber.",
        "action": "Remove from list if IMSI detached persists beyond 72 hours.",
    },
    "300": {
        "label": "Invalid destination address",
        "severity": SEVERITY_CRITICAL,
        "category": CAT_LIST,
        "root_cause": "The destination number does not exist, is disconnected, or was ported with routing errors. The carrier cannot resolve the MDN.",
        "action": "Remove all code-300 numbers permanently. Run the remaining contact list through a carrier lookup / LRN validation API. A code-300 rate above 3% indicates a low-quality lead source.",
    },
    "310": {
        "label": "Invalid source address",
        "severity": SEVERITY_CRITICAL,
        "category": CAT_SENDER,
        "root_cause": "The FROM number is misconfigured, deregistered, or not active in Signalmash. The SMSC cannot accept messages from this sender.",
        "action": "Pull the list of FROM numbers generating code 310. Check each in the Signalmash portal. Deregistered numbers must be replaced immediately. Do not retry sends until FROM numbers are corrected.",
    },
    "321": {
        "label": "ESME Receiver reject",
        "severity": SEVERITY_HIGH,
        "category": CAT_NETWORK,
        "root_cause": "The SMSC rejected the message at the protocol level. Can indicate a compliance violation, message formatting issue, or SMSC configuration problem.",
        "action": "Contact Signalmash support with the batch ID. Review message formatting for compliance. Check if a specific campaign is causing the rejections.",
    },
    "322": {
        "label": "ESME Receiver temporary error",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_NETWORK,
        "root_cause": "Transient SMSC or network congestion error. Often caused by retry storms — when large volumes of previously-failed messages are re-attempted simultaneously.",
        "action": "Implement retry backoff: do not retry code-300 or code-45 (permanent failures). For code-322, allow one retry with a 4-hour delay to reduce SMSC load.",
    },
    "349": {
        "label": "Request failed",
        "severity": SEVERITY_HIGH,
        "category": CAT_NETWORK,
        "root_cause": "Catch-all failure code. Specific cause is in the SMSC logs.",
        "action": "Contact Signalmash support with the batch ID from the upload for carrier-specific details.",
    },
    "409": {
        "label": "MC vendor specific error",
        "severity": SEVERITY_HIGH,
        "category": CAT_CARRIER,
        "root_cause": "Carrier-proprietary block or rejection. The specific reason is determined by which carrier's column has the highest count.",
        "action": "Identify the carrier generating the 409 errors. Contact Signalmash support with carrier name and batch ID for carrier-specific guidance.",
    },
}


# ── Telgorithm status code analysis ──────────────────────────────────────────

TELGORITHM_KB: dict[str, dict] = {
    "DeliveryFailure": {
        "label": "Delivery failure",
        "severity": SEVERITY_HIGH,
        "category": CAT_NETWORK,
        "root_cause": "Message was accepted by Telgorithm but could not be delivered at the carrier level. Common causes: soft carrier block on sender number, message held in queue too long, or carrier network issue.",
        "action": "Check sender number opt-out rate and complaint rate in Telgorithm portal. If opt-out rate > 5%, retire the number. Verify 10DLC campaign is active and approved.",
    },
    "UnknownError": {
        "label": "Unknown error",
        "severity": SEVERITY_HIGH,
        "category": CAT_NETWORK,
        "root_cause": "Gateway-level rejection with no carrier reason code returned. Often indicates sender number reputation issues or a carrier-side soft block that doesn't generate a specific code.",
        "action": "Monitor volume of UnknownError. If > 5% of total, rotate the sender number and check 10DLC campaign registration.",
    },
    "NoError": {
        "label": "No error (undelivered)",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_NETWORK,
        "root_cause": "Telgorithm received a success response but the DLR callback showed the message was not delivered. Typically a timing issue where the DCA status updates before the final delivery confirmation.",
        "action": "Monitor but not immediately actionable. If this persists above 2%, contact Telgorithm support.",
    },
    "RecipientOptedOut": {
        "label": "Recipient opted out",
        "severity": SEVERITY_LOW,
        "category": CAT_COMPLIANCE,
        "root_cause": "Recipient replied STOP to a previous message. Carrier honored the opt-out.",
        "action": "Add to DNC list immediately. Do not re-contact without fresh opt-in consent.",
    },
    "30003": {
        "label": "Landline or unreachable carrier",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_LIST,
        "root_cause": "Number is a landline, VoIP, or on an unsupported carrier network.",
        "action": "Remove from SMS campaigns. Consider voice-only outreach for landlines.",
    },
    "30006": {
        "label": "Landline or unreachable carrier",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_LIST,
        "root_cause": "Number is a landline or on a carrier that cannot receive SMS.",
        "action": "Remove from SMS campaigns.",
    },
}


def get_signalmash(code: str) -> dict:
    """Return analysis entry for a Signalmash DLR code, or a safe default."""
    return SIGNALMASH_KB.get(str(code), {
        "label": f"Unknown ({code})",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_NETWORK,
        "root_cause": "Unrecognised DLR code. Check Signalmash documentation or contact support.",
        "action": "Contact Signalmash support with batch ID if volume is significant.",
    })


def get_telgorithm(code: str) -> dict:
    """Return analysis entry for a Telgorithm error code, or a safe default."""
    return TELGORITHM_KB.get(str(code), {
        "label": f"Unknown ({code})",
        "severity": SEVERITY_MEDIUM,
        "category": CAT_NETWORK,
        "root_cause": "Unrecognised error code.",
        "action": "Contact Telgorithm support if volume is significant.",
    })


SEVERITY_ORDER = {SEVERITY_CRITICAL: 0, SEVERITY_HIGH: 1, SEVERITY_MEDIUM: 2, SEVERITY_LOW: 3}

SEVERITY_BADGE = {
    SEVERITY_CRITICAL: ("Critical",  "badge-fail"),
    SEVERITY_HIGH:     ("High",      "badge-partial"),
    SEVERITY_MEDIUM:   ("Medium",    "badge-blue"),
    SEVERITY_LOW:      ("Low",       "badge-pending"),
}

STATUS_BADGE = {
    "healthy":  ("✅ Healthy",  "badge-pass"),
    "warning":  ("⚠ Warning",  "badge-partial"),
    "critical": ("🔴 Critical", "badge-fail"),
}
