"""
Slack DNC Bot — Socket Mode (no public URL needed).

React ✔️  (heavy_check_mark) on any message containing a phone number
→ bot extracts the number, fires the DNC postback to Pipes,
  then reacts ✅ on success or ❌ on failure.

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

try:
    from portal.db import log_dnc as _db_log_dnc
    def _log_portal(phone: str, status: str, channel: str) -> None:
        _db_log_dnc(phone, status, source="slack", slack_channel=channel)
except Exception:
    def _log_portal(phone: str, status: str, channel: str) -> None:
        pass


# ── Phone extraction ───────────────────────────────────────────────────────────

def extract_phones(text: str) -> list[str]:
    """
    Return all unique 10-digit US numbers found in text.
    Handles: Slack tel: links, (XXX) XXX-XXXX, XXX-XXX-XXXX, raw 10/11-digit, multi-line.
    """
    found = []

    # Phase 1 — Slack auto-formats phones as <tel:5122227114|(512) 222-7114>
    for m in re.findall(r"<tel:(\d+)\|", text):
        digits = m
        if len(digits) == 11 and digits[0] == "1":
            digits = digits[1:]
        if len(digits) == 10:
            found.append(digits)

    # Phase 2 — raw 10/11-digit sequences
    for m in re.findall(r"\b\d{10,11}\b", text):
        if len(m) == 11 and m[0] == "1":
            m = m[1:]
        if len(m) == 10:
            found.append(m)

    # Phase 3 — formatted numbers like (XXX) XXX-XXXX or XXX-XXX-XXXX
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

def _startup_checks(bot_token: str, channel: str) -> None:
    """Verify bot auth and channel membership at startup."""
    try:
        r = httpx.get("https://slack.com/api/auth.test",
                      headers={"Authorization": f"Bearer {bot_token}"})
        d = r.json()
        if not d.get("ok"):
            log.warning(f"Slack auth failed: {d.get('error')} — check SLACK_BOT_TOKEN")
            return
        bot_id = d.get("user_id", "")
        log.info(f"Slack: authenticated as @{d.get('user')} ({bot_id}) in {d.get('team')}")

        if not channel:
            log.warning("DNC_SLACK_CHANNEL not set — watching ALL channels (not recommended for production)")
            return

        ri = httpx.get(f"https://slack.com/api/conversations.info?channel={channel}",
                       headers={"Authorization": f"Bearer {bot_token}"})
        ci = ri.json()
        if not ci.get("ok"):
            log.error(
                f"Channel {channel} not found (error={ci.get('error')}).\n"
                f"  Fix: Open the channel in Slack → /invite @{d.get('user')} → copy the channel ID.\n"
                f"  Then update DNC_SLACK_CHANNEL in .env and restart."
            )
            return

        ch = ci.get("channel", {})
        if ch.get("is_member"):
            log.info(f"Bot is a member of #{ch.get('name')} ({channel}) ✅")
        else:
            log.error(
                f"Bot is NOT in #{ch.get('name')} ({channel}).\n"
                f"  Fix: In Slack, open #{ch.get('name')} and type:  /invite @{d.get('user')}\n"
                f"  Then restart the bot."
            )
    except Exception as exc:
        log.warning(f"Startup check error: {exc}")


def main():
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    app_token = os.environ.get("SLACK_APP_TOKEN", "")

    if not bot_token or not app_token:
        print("❌  SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in .env")
        print("    See /dnc:slack-bot for setup instructions.")
        raise SystemExit(1)

    _startup_checks(bot_token, DNC_CHANNEL)

    app = App(token=bot_token)

    TRIGGER_REACTION = "heavy_check_mark"  # ✔️  — react this to DNC a number

    @app.event("reaction_added")
    def handle_reaction(event, client):
        reaction   = event.get("reaction", "")
        item       = event.get("item", {})
        channel_id = item.get("channel", "")
        msg_ts     = item.get("ts", "")

        if reaction != TRIGGER_REACTION:
            return

        if DNC_CHANNEL and channel_id != DNC_CHANNEL:
            log.debug(f"Skipping — not the DNC channel ({channel_id})")
            return

        log.info(f"✔️  reaction in {channel_id} on ts={msg_ts} — fetching message...")

        # Fetch the original message text
        try:
            result = client.conversations_history(
                channel=channel_id,
                latest=msg_ts,
                inclusive=True,
                limit=1,
            )
            messages = result.get("messages", [])
            if not messages:
                log.warning("Could not fetch original message")
                return
            text = messages[0].get("text", "")
        except Exception as exc:
            log.error(f"conversations_history error: {exc}")
            return

        phones = extract_phones(text)
        if not phones:
            log.info(f"No phone number found in message: {repr(text)}")
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=msg_ts,
                    text="⚠️ No phone number found in that message.",
                )
            except Exception:
                pass
            return

        log.info(f"Found {len(phones)} number(s): {phones}")
        results = {phone: dnc_number(phone) for phone in phones}
        all_ok  = all(results.values())

        for phone, ok in results.items():
            _log_portal(phone, "success" if ok else "failed", channel_id)

        try:
            client.reactions_add(
                channel=channel_id,
                timestamp=msg_ts,
                name="white_check_mark" if all_ok else "x",
            )
            log.info(f"Reacted {'✅' if all_ok else '❌'}")
        except Exception as exc:
            log.warning(f"Could not add reaction: {exc}")

        if not all_ok:
            failed = [p for p, ok in results.items() if not ok]
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=msg_ts,
                    text=f"⚠️ DNC failed for: {', '.join(failed)}",
                )
            except Exception as exc:
                log.warning(f"Could not post thread reply: {exc}")

    # Ignore plain messages (no auto-DNC on post)
    @app.event("message")
    def handle_message(event):
        pass

    channel_label = DNC_CHANNEL or "(all channels — set DNC_SLACK_CHANNEL to restrict)"
    print(f"  DNC bot starting — watching: {channel_label}")
    print(f"  Trigger: react ✔️  (heavy_check_mark) on any message with a phone number")
    print(f"  DNC endpoint: {DNC_URL}")
    print(f"  Press Ctrl+C to stop.\n")

    SocketModeHandler(app, app_token).start()


if __name__ == "__main__":
    main()
