"""
Slack Events API endpoint — receives reaction_added events and triggers DNC.

Flow:
  1. QA person posts phone number(s) in the DNC Slack channel
  2. Someone reacts with ✔️  (heavy_check_mark)
  3. Slack POSTs a reaction_added event to https://qa.aimagicstuff.com/slack/events
  4. This handler fetches the original message, extracts phones, calls DNC API
  5. Adds ✅ (all ok) or ❌ (any failed) reaction back on the message
  6. Posts a thread reply listing failed numbers if any

Required .env:
    SLACK_BOT_TOKEN      xoxb-...   (Bot OAuth token — Scopes: channels:history, reactions:write, chat:write)
    DNC_SLACK_CHANNEL    C0XXXXXXX  (channel ID to watch; leave blank to watch all)
    SLACK_SIGNING_SECRET xxxxxxxx   (from Slack App → Basic Information → Signing Secret)
"""

import hashlib
import hmac
import logging
import os
import re
import time
from typing import Optional

import httpx
from dotenv import dotenv_values
from flask import Blueprint, Response, request

log = logging.getLogger("slack_dnc")

bp = Blueprint("slack_dnc", __name__)

DNC_URL       = "https://integrations.pipes.ai/api/lead/do-not-call/7l6OaLWvqXoBz9pDVeExbn3JwG2rP8jN"
TRIGGER_EMOJI = "heavy_check_mark"   # ✔️  — react this to DNC a number


def _env(key: str) -> str:
    return dotenv_values(".env").get(key, "") or os.environ.get(key, "")


# ── Phone extraction ──────────────────────────────────────────────────────────

def extract_phones(text: str) -> list[str]:
    """Return all unique 10-digit US numbers found in text."""
    found = []
    # Phase 1 — Slack auto-format: <tel:5122227114|(512) 222-7114>
    for m in re.findall(r"<tel:(\d+)\|", text):
        d = m[1:] if (len(m) == 11 and m[0] == "1") else m
        if len(d) == 10:
            found.append(d)
    # Phase 2 — raw 10/11-digit sequences
    for m in re.findall(r"\b\d{10,11}\b", text):
        d = m[1:] if (len(m) == 11 and m[0] == "1") else m
        if len(d) == 10:
            found.append(d)
    # Phase 3 — formatted: (XXX) XXX-XXXX or XXX-XXX-XXXX
    for m in re.findall(r"\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}", text):
        d = re.sub(r"\D", "", m)
        if len(d) == 10:
            found.append(d)
    # Phase 4 — (XXX)XXXXXXX — no separator after closing paren
    for m in re.findall(r"\(\d{3}\)\d{7}", text):
        d = re.sub(r"\D", "", m)
        if len(d) == 10:
            found.append(d)
    # Phase 5 — strip all non-digits from any phone-like chunk and check
    for m in re.findall(r"[\d\(\)\-\.\s\+]{10,17}", text):
        d = re.sub(r"\D", "", m)
        if len(d) == 11 and d[0] == "1":
            d = d[1:]
        if len(d) == 10:
            found.append(d)
    return list(dict.fromkeys(found))  # deduplicate, preserve order


# ── Slack signature verification ──────────────────────────────────────────────

def _verify_signature(body: bytes, timestamp: str, signature: str, secret: str) -> bool:
    if not secret:
        return True  # skip verification if secret not configured (dev mode)
    try:
        if abs(time.time() - float(timestamp)) > 300:
            return False
        base = f"v0:{timestamp}:{body.decode('utf-8')}"
        computed = "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, signature)
    except Exception:
        return False


# ── Slack API helpers ─────────────────────────────────────────────────────────

def _slack(method: str, token: str, **payload) -> dict:
    """Call a Slack Web API method (POST JSON)."""
    try:
        r = httpx.post(
            f"https://slack.com/api/{method}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        return r.json()
    except Exception as exc:
        log.error(f"Slack API {method} error: {exc}")
        return {"ok": False, "error": str(exc)}


def _get_message_text(token: str, channel: str, ts: str) -> Optional[str]:
    """Fetch the text of a specific message by channel + timestamp."""
    result = _slack("conversations.history", token,
                    channel=channel, latest=ts, inclusive=True, limit=1)
    if not result.get("ok"):
        log.warning(f"conversations.history failed: {result.get('error')}")
        return None
    msgs = result.get("messages", [])
    return msgs[0].get("text", "") if msgs else None


def _add_reaction(token: str, channel: str, ts: str, emoji: str) -> None:
    result = _slack("reactions.add", token, channel=channel, timestamp=ts, name=emoji)
    if not result.get("ok") and result.get("error") != "already_reacted":
        log.warning(f"reactions.add failed: {result.get('error')}")


def _post_thread(token: str, channel: str, ts: str, text: str) -> None:
    _slack("chat.postMessage", token, channel=channel, thread_ts=ts, text=text)


# ── DNC API call ──────────────────────────────────────────────────────────────

def dnc_number(phone: str) -> bool:
    try:
        r = httpx.post(DNC_URL, data={"phone": phone}, timeout=15)
        ok = r.status_code < 400
        log.info(f"DNC {phone} → HTTP {r.status_code} {'OK' if ok else 'FAIL'}")
        return ok
    except Exception as exc:
        log.error(f"DNC {phone} error: {exc}")
        return False


# ── Main event endpoint ───────────────────────────────────────────────────────

@bp.route("/slack/events", methods=["POST"])
def slack_events():
    body_bytes = request.get_data()
    data       = request.get_json(silent=True) or {}

    signing_secret = _env("SLACK_SIGNING_SECRET")
    timestamp  = request.headers.get("X-Slack-Request-Timestamp", "")
    signature  = request.headers.get("X-Slack-Signature", "")

    if not _verify_signature(body_bytes, timestamp, signature, signing_secret):
        log.warning("Slack signature verification failed")
        return Response("Unauthorized", status=403)

    # Slack URL verification challenge (first-time setup)
    if data.get("type") == "url_verification":
        return Response(data["challenge"], mimetype="text/plain")

    if data.get("type") != "event_callback":
        return Response("ok", status=200)

    event = data.get("event", {})
    if event.get("type") != "reaction_added":
        return Response("ok", status=200)

    reaction   = event.get("reaction", "")
    item       = event.get("item", {})
    channel_id = item.get("channel", "")
    msg_ts     = item.get("ts", "")

    if reaction != TRIGGER_EMOJI:
        return Response("ok", status=200)

    dnc_channel = _env("DNC_SLACK_CHANNEL")
    if dnc_channel and channel_id != dnc_channel:
        log.debug(f"Skipping — not the DNC channel ({channel_id})")
        return Response("ok", status=200)

    bot_token = _env("SLACK_BOT_TOKEN")
    if not bot_token:
        log.error("SLACK_BOT_TOKEN not set — cannot process DNC reaction")
        return Response("ok", status=200)

    log.info(f"✔️  reaction in {channel_id} ts={msg_ts} — processing DNC...")

    text = _get_message_text(bot_token, channel_id, msg_ts)
    if text is None:
        return Response("ok", status=200)

    phones = extract_phones(text)
    if not phones:
        log.info(f"No phone number found in: {repr(text)}")
        _post_thread(bot_token, channel_id, msg_ts,
                     "⚠️ No phone number found in that message.")
        return Response("ok", status=200)

    log.info(f"Found {len(phones)} number(s): {phones}")
    results = {phone: dnc_number(phone) for phone in phones}
    all_ok  = all(results.values())

    # Log each result to portal DB
    try:
        from portal.db import log_dnc
        for phone, ok in results.items():
            log_dnc(phone, "success" if ok else "failed", source="slack", slack_channel=channel_id)
    except Exception as exc:
        log.warning(f"Could not write to DNC log: {exc}")

    react_result = _slack("reactions.add", bot_token, channel=channel_id, timestamp=msg_ts,
                          name="white_check_mark" if all_ok else "x")
    react_ok = react_result.get("ok") or react_result.get("error") == "already_reacted"

    if not all_ok:
        failed = [p for p, ok in results.items() if not ok]
        _post_thread(bot_token, channel_id, msg_ts,
                     f"⚠️ DNC failed for: {', '.join(failed)}")
    elif not react_ok:
        # Bot not in channel — post a thread reply as fallback confirmation
        succeeded = [p for p, ok in results.items() if ok]
        _post_thread(bot_token, channel_id, msg_ts,
                     f"✅ DNC'd {len(succeeded)} number(s): {', '.join(succeeded)}\n"
                     f"_(Tip: `/invite @Pipes DNC Bot` to `#test-hihi` to enable reaction feedback)_")
        log.warning(f"reactions.add failed ({react_result.get('error')}) — posted thread reply instead")
    else:
        log.info(f"DNC complete for {phones} — all succeeded ✅")

    return Response("ok", status=200)
