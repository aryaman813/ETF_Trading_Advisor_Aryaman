# IBKR Lite AI Alert Bot

This is an **alert-only** trading assistant for IBKR Lite.

It does **not** connect to IBKR and does **not** execute trades. It scans a watchlist, gets market data, asks OpenAI for a structured trade proposal, applies deterministic risk checks, sends an optional Telegram alert, and logs the signal for later evaluation.

## What Each File Does

- [main.py](main.py) is the entry point. It runs scans, signal evaluation, and the ETF backtest from the command line.
- [config.py](config.py) loads environment variables and the watchlist.
- [market_data.py](market_data.py) downloads price history and builds a market snapshot.
- [indicators.py](indicators.py) contains SMA, RSI, and percentage-change helpers.
- [llm.py](llm.py) sends the market snapshot to the model and parses the structured trade proposal.
- [schemas.py](schemas.py) defines the data models used across the app.
- [risk.py](risk.py) applies deterministic allowlist, sizing, confidence, and limit-price checks.
- [notifier.py](notifier.py) formats alerts and sends optional Telegram messages.
- [logger.py](logger.py) writes scan events and signal logs to the `logs/` folder.
- [performance.py](performance.py) evaluates logged signals after the fact.
- [backtest.py](backtest.py) runs the ETF strategy backtest over a fixed universe and date range.

## How To Run Everything

The normal workflow is:

1. Set up the Python environment.
2. Add your API keys and optional Telegram settings.
3. Run a live scan to generate alerts.
4. Evaluate logged signals after they have had time to mature.
5. Run the ETF backtest for a research-style summary.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your OpenAI API key. If you want Telegram alerts, also set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

Recommended environment variables:

```env
GEMINI_API_KEY=your_api_key_here
MODEL=gemma-4-31b-it
WATCHLIST=AAPL,MSFT,SPY,QQQ
BASE_CURRENCY=USD
TELEGRAM_BOT_TOKEN=optional
TELEGRAM_CHAT_ID=optional
```

## 1. Run A Scan

```bash
python main.py --scan
```

This scans the watchlist, requests a proposal, applies the risk checks, prints the alert, optionally sends Telegram, and logs the result.

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

## 2. Evaluate Past Signals

After a few trading days, evaluate the signals you already logged:

```bash
python main.py --evaluate 5 --cost-bps 10
```

This checks approved BUY/SELL alerts against future closing prices and prints a research summary with the universe, testing period, signal definition, hit rate, Sharpe ratio, confidence IC, drawdown, and cumulative return after costs.

## 3. Run the ETF Backtest

To generate a real strategy report with a fixed ETF universe and benchmark comparisons:

```bash
python main.py --backtest --start 2023-01-01 --end 2026-07-17 --universe SPY,QQQ,IWM,XLK,XLF,XLY,XLE,IEF,TLT,GLD --hold-days 5 --cost-bps 10
```

This runs a transparent momentum/trend strategy: go long when 5-day momentum is positive, price is above the 20-day and 50-day SMA, and RSI(14) is below 70. The `--cost-bps` value is treated as a round-trip trading cost, so `10` means 10 basis points total, which is 0.10% deducted from each trade's gross return. The report includes trade hit rate, Sharpe ratio, IC, drawdown, strategy return after costs, buy-and-hold, and equal-weight benchmark returns.

It also saves charts in `logs/backtest_plots/`, including an equity curve, trade return distribution, average return by symbol, and signal-score scatter plot.

## Output Files

- `logs/events.jsonl` stores scan and error events.
- `logs/signals.csv` stores each logged signal for later evaluation.

## Suggested Working Order

If you are starting from scratch on a new machine, run the project in this order:

1. Create and activate the virtual environment.
2. Install dependencies.
3. Set up `.env`.
4. Run `python main.py --scan`.
5. Let a few trading days pass.
6. Run `python main.py --evaluate 5 --cost-bps 10`.
7. Run `python main.py --backtest --start YYYY-MM-DD --end YYYY-MM-DD` to produce the research report for your universe.

## How to make the package stronger

If you want report-ready results, the next step is to turn the current alert stream into a real backtest:

- Define one fixed ETF universe and one fixed testing window.
- Log every candidate signal, not only approved trades.
- Store entry time, exit time, entry price, exit price, and transaction cost assumptions.
- Separate the predictive signal from the risk filter so you can measure both raw model quality and tradable quality.
- Add benchmark comparisons against buy-and-hold and a simple moving-average or momentum baseline.
- Save the evaluation summary to CSV or JSON so each run is reproducible.

## Important safety notes

- This is not financial advice.
- This app does not execute trades.
- Manually review every alert before entering anything in IBKR Lite.
- Start with tiny position sizes.
- `yfinance` is useful for prototyping but not execution-grade market data.
