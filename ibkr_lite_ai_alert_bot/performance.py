from pathlib import Path
import math
import pandas as pd
import yfinance as yf

from config import load_watchlist
from risk import ALLOWED_SYMBOLS, MAX_LIMIT_DISTANCE_PCT, MAX_NOTIONAL_USD, MIN_CONFIDENCE, MIN_NOTIONAL_USD


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
            gross_return_pct = (exit_price / entry - 1) * 100
        else:
            gross_return_pct = (entry / exit_price - 1) * 100

        results.append({
            "timestamp_utc": row["timestamp_utc"],
            "symbol": symbol,
            "action": row["action"],
            "entry_limit": entry,
            f"close_after_{days_forward}d": exit_price,
            f"gross_return_{days_forward}d_pct": gross_return_pct,
            "confidence": row["confidence"],
        })

    return pd.DataFrame(results)


def signal_definition() -> str:
    return (
        "Approved BUY/SELL alerts only, after deterministic risk checks: allowed symbol, "
        f"STK, LMT, confidence >= {MIN_CONFIDENCE:.2f}, quantity within 0.0001-1.0 shares, "
        f"notional between ${MIN_NOTIONAL_USD:.2f} and ${MAX_NOTIONAL_USD:.2f}, and limit price "
        f"within {MAX_LIMIT_DISTANCE_PCT:.2f}% of last close."
    )


def _max_drawdown_pct(returns_pct: pd.Series) -> float:
    if returns_pct.empty:
        return 0.0

    equity = (1 + returns_pct.fillna(0) / 100).cumprod()
    running_max = equity.cummax()
    drawdowns = equity / running_max - 1
    return float(drawdowns.min() * 100)


def build_evaluation_summary(df: pd.DataFrame, days_forward: int, cost_bps: float) -> dict[str, object]:
    if df.empty:
        return {}

    ordered = df.sort_values("timestamp_utc").copy()
    ordered["net_return_pct"] = ordered[f"gross_return_{days_forward}d_pct"] - (cost_bps / 100)

    gross_returns = ordered[f"gross_return_{days_forward}d_pct"] / 100
    net_returns = ordered["net_return_pct"] / 100

    gross_sharpe = None
    net_sharpe = None
    gross_std = gross_returns.std(ddof=1)
    net_std = net_returns.std(ddof=1)
    if len(gross_returns) >= 2 and pd.notna(gross_std) and gross_std > 0:
        gross_sharpe = float(gross_returns.mean() / gross_std * math.sqrt(len(gross_returns)))
    if len(net_returns) >= 2 and pd.notna(net_std) and net_std > 0:
        net_sharpe = float(net_returns.mean() / net_std * math.sqrt(len(net_returns)))

    confidence_ic = None
    if ordered["confidence"].nunique(dropna=True) > 1 and ordered["net_return_pct"].nunique(dropna=True) > 1:
        confidence_ic = float(ordered["confidence"].corr(ordered["net_return_pct"]))

    testing_start = pd.to_datetime(ordered["timestamp_utc"]).min()
    testing_end = pd.to_datetime(ordered["timestamp_utc"]).max()

    if isinstance(testing_start, pd.Timestamp):
        testing_start = testing_start.isoformat()
    if isinstance(testing_end, pd.Timestamp):
        testing_end = testing_end.isoformat()

    gross_equity = (1 + gross_returns).cumprod()
    net_equity = (1 + net_returns).cumprod()

    return {
        "universe": sorted(ordered["symbol"].dropna().astype(str).str.upper().unique().tolist()),
        "watchlist": load_watchlist(),
        "testing_period": {
            "start": testing_start,
            "end": testing_end,
            "forward_days": days_forward,
        },
        "signal_definition": signal_definition(),
        "n_signals": int(len(ordered)),
        "hit_rate_pct": float((ordered["net_return_pct"] > 0).mean() * 100),
        "avg_gross_return_pct": float(ordered[f"gross_return_{days_forward}d_pct"].mean()),
        "avg_net_return_pct_after_costs": float(ordered["net_return_pct"].mean()),
        "median_net_return_pct_after_costs": float(ordered["net_return_pct"].median()),
        "gross_sharpe_ratio": gross_sharpe,
        "net_sharpe_ratio": net_sharpe,
        "confidence_ic": confidence_ic,
        "max_drawdown_pct_after_costs": _max_drawdown_pct(ordered["net_return_pct"]),
        "cumulative_return_pct_after_costs": float((net_equity.iloc[-1] - 1) * 100),
        "cumulative_return_pct_gross": float((gross_equity.iloc[-1] - 1) * 100),
        "cost_bps_round_trip": cost_bps,
        "allowed_symbols": sorted(ALLOWED_SYMBOLS),
    }
