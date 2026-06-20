"""
Slack DNC Bot — Socket Mode (no public URL needed).

Watches a Slack channel for phone numbers.
When a number is posted, it automatically fires a DNC postback to Pipes.
Reacts ✅ on success, ❌ on failure.

Run:
    uv run python -m integrations.slack_dnc

Requires in .env:
    SLACK_BOT_TOKEN   xoxb-...
    SLACK_APP_TOKEN   xapp-...
    DNC_SLACK_CHANNEL  C0XXXXXXXX  (channel ID, not name)
"""
import os
import re
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("slack_dnc")

DNC_URL     = "https://integrations.pipes.ai/api/lead/do-not-call/7l6OaLWvqXoBz9pDVeExbn3JwG2rP8jN"
DNC_CHANNEL = os.environ.get("DNC_SLACK_CHANNEL", "")


# ── Phone extraction ───────────────────────────────────────────────────────────

def extract_phones(text: str) -> list[str]:
    """
    Return all unique 10-digit US numbers found in text.
    Handles: (XXX) XXX-XXXX, XXX-XXX-XXXX, raw 10/11-digit, multi-line.
    """
    found = []

    # Phase 1 — raw 10/11-digit sequences (no spaces between digits)
    for m in re.findall(r"\b\d{10,11}\b", text):
        if len(m) == 11 and m[0] == "1":
            m = m[1:]
        if len(m) == 10:
            found.append(m)

    # Phase 2 — formatted numbers like (XXX) XXX-XXXX or XXX-XXX-XXXX
    for m in re.findall(r"\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}", text):
        digits = re.sub(r"\D", "", m)
        if len(digits) == 10:
            found.append(digits)

    return list(dict.fromkeys(found))  # deduplicate, preserve order


# ── DNC API call ───────────────────────────────────────────────────────────────

def dnc_number(phone: str) -> bool:
    try:
        r = httpx.post(DNC_URL, data={"phone": phone}, timeout=15)
        ok = r.status_code < 400
        log.info(f"DNC {phone} → HTTP {r.status_code} {'OK' if ok else 'FAIL'}")
        return ok
    except Exception as exc:
        log.error(f"DNC {phone} → error: {exc}")
        return False


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    app_token = os.environ.get("SLACK_APP_TOKEN", "")

    if not bot_token or not app_token:
        print("❌  SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in .env")
        print("    See /dnc:slack-bot for setup instructions.")
        raise SystemExit(1)

    app = App(token=bot_token)

    @app.event("message")
    def handle_message(event, client):
        if event.get("subtype"):
            return
        if DNC_CHANNEL and event.get("channel") != DNC_CHANNEL:
            return

        phones = extract_phones(event.get("text", ""))
        if not phones:
            return

        log.info(f"Found {len(phones)} number(s): {phones}")
        results = {phone: dnc_number(phone) for phone in phones}
        all_ok  = all(results.values())

        try:
            client.reactions_add(
                channel=event["channel"],
                timestamp=event["ts"],
                name="white_check_mark" if all_ok else "x",
            )
        except Exception as exc:
            log.warning(f"Could not add reaction: {exc}")

        if not all_ok:
            failed = [p for p, ok in results.items() if not ok]
            try:
                client.chat_postMessage(
                    channel=event["channel"],
                    thread_ts=event["ts"],
                    text=f"⚠️ DNC failed for: {', '.join(failed)}",
                )
            except Exception as exc:
                log.warning(f"Could not post thread reply: {exc}")

    channel_label = DNC_CHANNEL or "(all channels — set DNC_SLACK_CHANNEL to restrict)"
    print(f"  DNC bot starting — watching: {channel_label}")
    print(f"  DNC endpoint: {DNC_URL}")
    print(f"  Press Ctrl+C to stop.\n")

    SocketModeHandler(app, app_token).start()


if __name__ == "__main__":
    main()
