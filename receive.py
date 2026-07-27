"""Poll Telegram for new messages sent to the bot.

Usage:
    python receive.py           # print new messages since last check, as a JSON array
    python receive.py --init    # mark all pending messages as seen; print nothing new

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from the environment,
falling back to a .env file (KEY=VALUE per line) in the same
directory as this script if the variables aren't already set.

State (last processed update_id) is kept in telegram_bot_state.json
next to this script - not committed to git.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
STATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "telegram_bot_state.json"
)


def load_dotenv(path):
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def load_state():
    if not os.path.isfile(STATE_PATH):
        return {"last_update_id": 0}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
        state["last_update_id"]
        return state
    except (ValueError, KeyError, OSError):
        return {"last_update_id": 0}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


def get_updates(token, offset):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": 0}
    if offset is not None:
        params["offset"] = offset
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", method="GET")
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    init_mode = "--init" in sys.argv[1:]

    load_dotenv(ENV_PATH)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(
            "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID "
            "(set as environment variables or in .env)",
            file=sys.stderr,
        )
        sys.exit(1)

    state = load_state()
    offset = state["last_update_id"] + 1 if state["last_update_id"] else None

    try:
        result = get_updates(token, offset)
    except urllib.error.HTTPError as e:
        print(f"Telegram API error {e.code}: {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(1)

    if not result.get("ok"):
        print(f"Telegram API returned failure: {result}", file=sys.stderr)
        sys.exit(1)

    updates = result["result"]

    max_update_id = state["last_update_id"]
    messages = []
    for update in updates:
        max_update_id = max(max_update_id, update["update_id"])
        message = update.get("message")
        if not message or "text" not in message:
            continue
        if str(message["chat"]["id"]) != str(chat_id):
            continue
        if init_mode:
            continue
        messages.append({"update_id": update["update_id"], "text": message["text"]})

    save_state({"last_update_id": max_update_id})

    if init_mode:
        print(f"Initialized. last_update_id={max_update_id}")
    else:
        print(json.dumps(messages))


if __name__ == "__main__":
    main()
