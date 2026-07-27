# Telegram Price Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `telegram-price-bot` skill that lets the user type a product name into their existing Telegram bot and get back the top-5 cheapest exact-match offers with links, without editing any code per product.

**Architecture:** A new standalone script `receive.py` polls Telegram's `getUpdates` API and tracks which messages have already been handled in a local, gitignored state file. A new skill `telegram-price-bot` starts a fixed-interval `/loop` (every 3 minutes) that calls `receive.py`, and for every new message runs the same store-search steps already documented in `tracker/SKILL.md` (fallback web search + Ozon/Яндекс Маркет/Wildberries via browser, minus the fixed-URL-list and history/baseline machinery, which are specific to the Premier dog food product), then replies via the existing `send.py`.

> Amended after live end-to-end testing: use dynamic `/loop` (no fixed interval) instead — see the committed SKILL.md and the design spec, which had already specified ScheduleWakeup / dynamic mode correctly.

**Tech Stack:** Python 3 (stdlib only — `json`, `urllib`), Telegram Bot API (`getUpdates`, `sendMessage`), Claude Code `Skill`/`ScheduleWakeup`/`WebSearch`/`WebFetch`/`mcp__claude-in-chrome__*` tools.

## Global Constraints

- Reuse `send.py`'s existing `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) — do not introduce a second credentials file.
- Never commit `.env` or the new runtime state file to git (both must be listed in `.gitignore`).
- Do not duplicate the marketplace/fallback-search/exact-match instructions that already exist in `.claude/skills/tracker/SKILL.md` — the new skill must reference those sections by name, not copy their text.
- Reuse the `extract-price` skill as-is for pulling a price off a single URL — do not reimplement price parsing.
- No changes to `tracker/SKILL.md`, `KNOWLEDGE.md`, or `tracker-data` — this feature does not touch the recurring Premier-food tracker or its saved history.

---

### Task 1: `receive.py` — poll Telegram for new messages

**Files:**
- Create: `D:\07 vibecode\parcer\receive.py`
- Modify: `D:\07 vibecode\parcer\.gitignore`

**Interfaces:**
- Produces (consumed by Task 2):
  - CLI: `python receive.py` → prints a JSON array to stdout, one object per new message: `{"update_id": <int>, "text": "<str>"}`. Empty array `[]` if nothing new.
  - CLI: `python receive.py --init` → does not print message data; prints `Initialized. last_update_id=<N>`. Marks all currently-pending Telegram updates as seen without treating any of them as "new" — used once when the listening loop starts, so old chat history isn't replayed.
  - State file `telegram_bot_state.json` (same directory as the script): `{"last_update_id": <int>}`. Created/updated automatically by both invocations above — callers never read or write it directly.
  - Exit code 1 + stderr message on missing credentials or Telegram API/network errors (mirrors `send.py`'s existing error-reporting style).

- [ ] **Step 1: Write `receive.py`**

```python
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
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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
        print(json.dumps(messages, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add the state file to `.gitignore`**

Current contents of `.gitignore`:

```
.env
```

New contents:

```
.env
telegram_bot_state.json
```

- [ ] **Step 3: Run `--init` for real and verify it doesn't crash**

Run: `cd "D:\07 vibecode\parcer" && python receive.py --init`

Expected: prints `Initialized. last_update_id=<some integer, possibly 0>` and creates `telegram_bot_state.json` in the project root containing `{"last_update_id": <that same integer>}`.

- [ ] **Step 4: Verify a no-op check returns an empty array**

Run: `cd "D:\07 vibecode\parcer" && python receive.py`

Expected: prints `[]` (assuming no one has messaged the bot since Step 3's `--init`) and exits 0.

- [ ] **Step 5: Verify a real message is picked up**

Send any text message to the Telegram bot from the phone/app, then run:

`cd "D:\07 vibecode\parcer" && python receive.py`

Expected: prints a JSON array with one object, e.g. `[{"update_id": 123456789, "text": "тестовое сообщение"}]`. Run `python receive.py` a second time immediately after — expected: `[]` (the message isn't returned twice, and `telegram_bot_state.json`'s `last_update_id` now equals that message's `update_id`).

- [ ] **Step 6: Commit**

```bash
git add receive.py .gitignore
git commit -m "Add receive.py to poll Telegram for new messages"
```

---

### Task 2: `telegram-price-bot` skill — start/check/stop flow

**Files:**
- Create: `D:\07 vibecode\parcer\.claude\skills\telegram-price-bot\SKILL.md`

**Interfaces:**
- Consumes (from Task 1): `python receive.py` / `python receive.py --init` CLI contract described above.
- Consumes (existing, unmodified): `extract-price` skill (`{ url } → { regular_price, sale_price }` or "товар не найден"); `tracker/SKILL.md` sections "Общее правило точного совпадения", "Порядок действий: Ozon (только если доступен браузер)", "Порядок действий: Яндекс Маркет (только если доступен браузер)", "Порядок действий: Wildberries (только если доступен браузер)", "Порядок действий: fallback-поиск сторонних магазинов", "Шаг 0: проверка браузера"; `send.py` (`python send.py "<text>"`).
- Produces: two trigger phrases the user types in chat — «слушай телеграм» (start) and «хватит слушать» (stop) — matched via this skill's `description` frontmatter, same mechanism `tracker`/`extract-price` already use for their own triggering.

- [ ] **Step 1: Write the skill file**

```markdown
---
name: telegram-price-bot
description: |
  Слушает Telegram-бота (тот же бот и .env, что использует tracker/send.py) на новые сообщения с названием товара и присылает в ответ топ-5 самых дешёвых точных совпадений со ссылками. В отличие от tracker (зашитый товар, зашитый список URL, история прогонов в tracker-data) — это разовый поиск по произвольному товару из текста сообщения, без сохранения истории. Работает только пока запущен цикл проверки в открытой сессии Claude Code (через /loop) — без открытого чата не работает. Запускается фразой пользователя «слушай телеграм», останавливается фразой «хватит слушать».
---

# Telegram price bot

Даёт пользователю писать произвольное название товара в Telegram-бота и получать в ответ топ-5 самых дешёвых точных совпадений со ссылками. В отличие от `tracker` (один зашитый товар, зашитый список URL, история прогонов в `tracker-data`) — здесь товар каждый раз новый, из текста сообщения, история не сохраняется.

## Команда «слушай телеграм» (старт)

1. Сообщить пользователю обе команды: что для остановки нужно написать «хватит слушать», и что слушать он начинает прямо сейчас.
2. Выполнить `cd "D:\07 vibecode\parcer" && python receive.py --init` — это помечает всю текущую переписку с ботом как уже прочитанную, чтобы не реагировать на сообщения, отправленные до старта.
3. Запустить регулярную проверку вызовом skill `loop` с фиксированным интервалом 3 минуты и промптом, который указывает выполнить раздел «Проверка (что делать на каждой проверке)» этого файла (`.claude/skills/telegram-price-bot/SKILL.md`).
4. Подтвердить пользователю, что проверка запущена (раз в ~3 минуты) и что для остановки — «хватит слушать».

## Команда «хватит слушать» (стоп)

1. Вызвать инструмент `ScheduleWakeup` с `stop: true` — это отменяет все запланированные проверки.
2. Подтвердить пользователю, что опрос Telegram-бота остановлен.

## Проверка (что делать на каждой проверке)

Выполняется каждый раз, когда срабатывает цикл, запущенный на шаге «старт».

1. Выполнить `cd "D:\07 vibecode\parcer" && python receive.py` и разобрать JSON-массив из stdout.
2. Массив пустой → ничего не писать в чат и не в Telegram, просто дождаться следующего срабатывания цикла.
3. Массив не пустой → обработать каждый объект по порядку (по возрастанию `update_id`):
   a. `text` — это название/описание нужного товара.
   b. Проверить браузер (см. `tracker/SKILL.md`, «Шаг 0: проверка браузера»), чтобы знать, доступны ли Ozon/Яндекс Маркет/Wildberries в этот раз.
   c. Найти источники **без использования зашитого списка URL из `tracker`** — вместо него выполнить шаги «Порядок действий: fallback-поиск сторонних магазинов» из `tracker/SKILL.md` (веб-поиск, исключая ozon.ru/market.yandex.ru/wildberries.ru) и, если браузер доступен, «Порядок действий: Ozon», «Порядок действий: Яндекс Маркет», «Порядок действий: Wildberries» — все три тоже из `tracker/SKILL.md`, использовать как есть, не копировать и не менять их текст.
   d. Применить «Общее правило точного совпадения» (`tracker/SKILL.md`) — отсеять варианты, не совпадающие по весу/вкусу/размеру/модификации с тем, что просил пользователь.
   e. Для каждого оставшегося кандидата вызвать skill `extract-price`, получить `{ regular_price, sale_price }` либо `товар не найден`.
   f. Из результатов со статусом `ok` (цена получена) и точным совпадением отсортировать по цене (`sale_price`, если есть, иначе `regular_price`) по возрастанию, взять первые 5.
   g. Собрать текст ответа:
      - Есть хотя бы один результат → первая строка `Нашёл по запросу «<text>»:`, дальше на каждый источник — блок из двух строк: `<источник>: <цена> ₽` и на следующей строке ссылка на карточку; блоки разделены пустой строкой (тот же формат, что уже использует `tracker` для сводки в Telegram).
      - Ни одного точного совпадения не найдено → текст ответа строго: `По запросу «<text>» ничего подходящего найти не удалось`.
   h. Отправить: `cd "D:\07 vibecode\parcer" && python send.py "<текст ответа>"`.
4. Обновление `last_update_id` в состоянии уже сделано скриптом `receive.py` сам по себе (шаг 1) — отдельно ничего сохранять не нужно.

## Обработка ошибок

- `receive.py` вернул ошибку (ненулевой код возврата / текст ошибки в stderr — например, сеть недоступна) → не считать это сбоем всего цикла: пропустить эту проверку молча, следующая проверка наступит через 3 минуты сама (цикл продолжает работать). Не писать пользователю об единичной заминке.
- По конкретному товару ни одного точного совпадения не нашлось → явно ответить пользователю (см. шаг 3.g выше), не подставлять случайную/неточную цену вместо честного «не нашёл».
- `send.py` вернул ошибку (сообщение не отправилось) → не считать сбоем всего цикла, не пытаться отправить в обход `send.py` другим способом; цикл проверки продолжает работать дальше.
- Несколько сообщений накопилось между проверками → обработать все по очереди (шаг 3), на каждое отправить отдельный ответ через `send.py` — ни один запрос не должен быть молча проигнорирован.
```

- [ ] **Step 2: Verify the frontmatter parses and the skill is listed**

Run: start a new Claude Code turn (or use whatever mechanism this environment uses to refresh the skill list) and confirm `telegram-price-bot` appears in the available-skills listing with the description above. If the skill listing doesn't auto-refresh mid-session, this check happens naturally in Task 3 when the skill is actually invoked.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/telegram-price-bot/SKILL.md
git commit -m "Add telegram-price-bot skill for on-demand product price lookup"
```

---

### Task 3: End-to-end manual verification

**Files:** none (no code changes — this task exercises Task 1 + Task 2 together in a live session).

**Interfaces:**
- Consumes: everything produced by Task 1 and Task 2.

- [ ] **Step 1: Start listening**

In a Claude Code chat with the `D:\07 vibecode\parcer` project open and Claude in Chrome connected, type: `слушай телеграм`

Expected: Claude confirms both commands («слушай телеграм» / «хватит слушать»), runs `python receive.py --init`, and confirms the 3-minute check loop has started.

- [ ] **Step 2: Ask for a product that should have easy-to-find matches**

From the Telegram app, send the bot a message with a common product name, e.g. `корм Royal Canin для кошек 2 кг`.

Expected: within about 3–6 minutes (one or two check cycles), the bot replies in Telegram with either a top-5 list (store name, price, link per block) or, if nothing matched closely enough, the exact phrase `По запросу «корм Royal Canin для кошек 2 кг» ничего подходящего найти не удалось`.

- [ ] **Step 3: Verify old messages aren't replayed**

Without sending anything new, wait for one more check cycle (~3 minutes) and confirm no duplicate reply arrives in Telegram.

- [ ] **Step 4: Ask for a nonsense product (no-match path)**

Send the bot a message that can't plausibly match any real product, e.g. `zzqxvnonexistentproduct12345`.

Expected: the bot replies with `По запросу «zzqxvnonexistentproduct12345» ничего подходящего найти не удалось` — not a fabricated price.

- [ ] **Step 5: Stop listening**

In the Claude Code chat, type: `хватит слушать`

Expected: Claude calls `ScheduleWakeup` with `stop: true` and confirms the check loop has stopped.

- [ ] **Step 6: Confirm the loop actually stopped**

Send the bot one more product name and wait ~6 minutes. Expected: no reply arrives, confirming no further checks are running.

- [ ] **Step 7: Record the outcome**

If all of Steps 1–6 behaved as expected, no further action needed. If anything diverged (e.g. wrong reply format, duplicate replies, loop didn't stop), note the specific divergence — that's a bug to fix in Task 1 or Task 2's file before considering this plan done.
