"""Send a text message to a Telegram chat via the Bot API.

Usage:
    python send.py "message text"

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from the environment,
falling back to a .env file (KEY=VALUE per line) in the same
directory as this script if the variables aren't already set.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


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


def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    if len(sys.argv) != 2:
        print('Usage: python send.py "message text"', file=sys.stderr)
        sys.exit(1)

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

    text = sys.argv[1]

    try:
        result = send_message(token, chat_id, text)
    except urllib.error.HTTPError as e:
        print(f"Telegram API error {e.code}: {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(1)

    if not result.get("ok"):
        print(f"Telegram API returned failure: {result}", file=sys.stderr)
        sys.exit(1)

    print("Message sent.")


if __name__ == "__main__":
    main()
