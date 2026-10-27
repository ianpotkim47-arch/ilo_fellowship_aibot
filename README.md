# ILO Discord FAQ Bot + Dashboard

> **Note:** This is a cleaned-up / updated version of the repository. The main sensitive
> parts of the code (OpenAI API key, Discord bot token) have been **redacted** and moved
> to environment variables, so no private credentials are committed here. The entry point
> `app.py` reads everything from the environment; the older `chatbot.py` is kept only for
> reference and should **not** be used as-is.

## Overview

An auto-reply **Discord bot** for the **International Logic Olympiad (ILO)** community,
paired with a small **Flask web dashboard**.

When a member asks a question in the Discord server, the bot answers it automatically from
a curated FAQ knowledge base using OpenAI (`gpt-4o-mini`). If a question isn't covered by
the FAQ, it falls back to a polite "a support team will get back to you soon" message so a
human can follow up. Every conversation is logged, and the dashboard turns those logs into
live stats.

## Features

- **Automatic FAQ answers** — GPT is constrained to the FAQ data (registration, exam
  schedule, eligibility, team formation, results, visa/Final Round, etc.), so it stays
  accurate and on-topic.
- **Safe fallback** — unknown questions get a fixed hand-off message and are flagged as
  unanswered for the support team.
- **Slash-style commands**
  - `!exam_start` — posts the Round 1 start date.
  - `!stats` — posts total messages, AI-answered count, and fallback count.
- **Logging** — every message/reply is stored in SQLite (`database.db`) and appended to
  `chat_log.csv`.
- **Web dashboard** (Flask) — totals, resolution rate, messages-per-day, top users,
  recent chats, and FAQ category breakdown, served at `/` with a JSON API at
  `/api/dashboard-stats`.

## Tech Stack

- Python
- [`discord.py`](https://pypi.org/project/discord.py/) — the bot
- [OpenAI Python SDK](https://pypi.org/project/openai/) — answer generation
- Flask — dashboard + JSON API
- SQLite + CSV — logging

## Project Structure

```
PythonProject5/
├── app.py          # Main entry: Flask dashboard + Discord bot (uses env vars)
├── chatbot.py      # Older standalone bot version (reference only)
├── database.db     # SQLite chat log (auto-created)
├── templates/
│   └── index.html  # Dashboard UI
└── README.md
```

## Setup

1. **Install dependencies**

   ```bash
   pip install discord.py openai flask
   ```

2. **Set your credentials as environment variables** (never hard-code them)

   ```bash
   export OPENAI_API_KEY="your-openai-key"
   export DISCORD_BOT_TOKEN="your-discord-bot-token"
   ```

3. **Run**

   ```bash
   python app.py
   ```

   This starts the Discord bot (in a background thread) and the Flask dashboard at
   `http://localhost:8080`.

## How It Works

1. A user posts a message in the Discord server.
2. `generate_bot_reply()` sends the message to GPT with a system prompt locked to the FAQ
   data and strict rules (no follow-up questions, exact fallback text for unknowns).
3. The bot replies in the channel and logs the exchange to SQLite and CSV, tagging whether
   it was answered or fell back.
4. The Flask dashboard reads those logs and renders live statistics.

## Security Note

If you fork or extend this project, keep all keys and tokens in environment variables (or a
`.env` file that is git-ignored). Do not commit real credentials — rotate any token that has
ever been exposed.
