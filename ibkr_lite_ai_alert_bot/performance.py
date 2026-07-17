from pathlib import Path
import pandas as pd
import yfinance as yf


SIGNALS_PATH = Path("logs/signals.csv")


def evaluate_signals(days_forward: int = 5) -> pd.DataFrame:
    if not SIGNALS_PATH.exists():
        raise RuntimeError("No signals.csv found. Run the scanner first.")

    signals = pd.read_csv(SIGNALS_PATH)
    actionable = signals[(signals["approved"] == True) & (signals["action"].isin(["BUY", "SELL"]))].copy()

    results = []
    for _, row in actionable.iterrows():
        symbol = row["symbol"]
        signal_time = pd.to_datetime(row["timestamp_utc"]).tz_convert(None).date()

        hist = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=True)
        if hist.empty:
            continue

        hist = hist.reset_index()
        hist["DateOnly"] = pd.to_datetime(hist["Date"]).dt.date

        after = hist[hist["DateOnly"] > signal_time].head(days_forward)
        if len(after) < days_forward:
            continue

        entry = float(row["limit_price"])
        exit_price = float(after.iloc[-1]["Close"])

        if row["action"] == "BUY":
            return_pct = (exit_price / entry - 1) * 100
        else:
            return_pct = (entry / exit_price - 1) * 100

        results.append({
            "timestamp_utc": row["timestamp_utc"],
            "symbol": symbol,
            "action": row["action"],
            "entry_limit": entry,
            f"close_after_{days_forward}d": exit_price,
            f"return_{days_forward}d_pct": return_pct,
            "confidence": row["confidence"],
        })

    return pd.DataFrame(results)
