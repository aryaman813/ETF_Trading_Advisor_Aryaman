# IBKR Lite AI Alert Bot

This is an **alert-only** trading assistant for IBKR Lite.

It does **not** connect to IBKR and does **not** execute trades. It scans a watchlist, gets market data, asks OpenAI for a structured trade proposal, applies deterministic risk checks, sends an optional Telegram alert, and logs the signal for later evaluation.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your OpenAI API key.

## Run a scan

```bash
python main.py --scan
```

## Optional Telegram alerts

1. Open Telegram.
2. Message `@BotFather`.
3. Create a bot and copy the token.
4. Get your chat ID using a bot such as `@userinfobot`, or by using Telegram's `getUpdates` endpoint.
5. Put these in `.env`:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Evaluate past signals

After several days:

```bash
python main.py --evaluate 5
```

This checks approved BUY/SELL alerts against future closing prices.

## Important safety notes

- This is not financial advice.
- This app does not execute trades.
- Manually review every alert before entering anything in IBKR Lite.
- Start with tiny position sizes.
- `yfinance` is useful for prototyping but not execution-grade market data.
