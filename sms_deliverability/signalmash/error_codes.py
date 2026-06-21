ERROR_CODES: dict[str, str] = {
    "0":   "Delivered to Device by the external entity",
    "1":   "Source not found. Internal routing error.",
    "6":   "EC_ABSENT_SUBSCRIBER_SM",
    "15":  "Screening block",
    "21":  "Expired",
    "31":  "EC_SUBSCRIBER_BUSY_FOR_MT_SMS",
    "32":  "EC_SM_DELIVERY_FAILURE",
    "34":  "Message Validity Expired",
    "45":  "MDN BLOCKED",
    "60":  "Campaign not active on AT&T",
    "61":  "Destination blocked",
    "64":  "Blocked due to exceeded quota",
    "66":  "Data coding scheme blocked",
    "69":  "Sending limit reached",
    "153": "Absent subscriber",
    "201": "Absent subscriber, IMSI detached",
    "300": "Invalid destination address",
    "310": "Invalid source address",
    "321": "ESME Receiver reject error",
    "322": "ESME Receiver temporary error",
    "349": "Request failed",
    "409": "MC vendor specific errors",
}

DELIVERED_CODE = "0"


def describe(code: str) -> str:
    return ERROR_CODES.get(str(code).strip(), f"Unknown error ({code})")


def is_delivered(code: str) -> bool:
    return str(code).strip() == DELIVERED_CODE
