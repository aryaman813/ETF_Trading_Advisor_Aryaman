from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

from indicators import rsi_series


DEFAULT_ETF_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "XLK",
    "XLF",
    "XLY",
    "XLE",
    "IEF",
    "TLT",
    "GLD",
]

PLOTS_DIR = Path("logs/backtest_plots")


@dataclass(frozen=True)
class BacktestConfig:
    universe: list[str]
    start_date: str
    end_date: str
    hold_days: int = 5
    cost_bps_round_trip: float = 10.0


def load_backtest_universe(raw: str | None = None) -> list[str]:
    universe_raw = raw or ""
    if not universe_raw.strip():
        return DEFAULT_ETF_UNIVERSE.copy()
    return [symbol.strip().upper() for symbol in universe_raw.split(",") if symbol.strip()]


def _normalize_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    hist = yf.Ticker(symbol).history(start=start_date, end=end_date, interval="1d", auto_adjust=True)
    if hist.empty:
        return hist

    hist = hist.reset_index()
    if "Date" not in hist.columns:
        hist = hist.rename(columns={hist.columns[0]: "Date"})

    hist["Date"] = pd.to_datetime(hist["Date"])
    hist["DateOnly"] = hist["Date"].dt.date
    return hist


def _strategy_signal_score(hist: pd.DataFrame) -> pd.DataFrame:
    hist = hist.copy()
    close = hist["Close"]
    hist["sma_20"] = close.rolling(20).mean()
    hist["sma_50"] = close.rolling(50).mean()
    hist["rsi_14"] = rsi_series(close, 14)
    hist["momentum_5d_pct"] = close.pct_change(5) * 100
    hist["trend_spread_pct"] = (close / hist["sma_20"] - 1) * 100
    hist["signal_score"] = hist["momentum_5d_pct"].fillna(0) + hist["trend_spread_pct"].fillna(0)
    hist["enter_long"] = (
        (hist["momentum_5d_pct"] > 0)
        & (close > hist["sma_20"])
        & (close > hist["sma_50"])
        & (hist["rsi_14"] < 70)
    )
    return hist


def _max_drawdown_pct(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0

    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1
    return float(drawdown.min() * 100)


def _trade_metrics(trades: pd.DataFrame, cost_bps_round_trip: float) -> dict[str, float | int | None]:
    if trades.empty:
        return {
            "n_trades": 0,
            "hit_rate_pct": 0.0,
            "avg_gross_return_pct": 0.0,
            "avg_net_return_pct": 0.0,
            "gross_sharpe_ratio": None,
            "net_sharpe_ratio": None,
            "confidence_ic": None,
            "max_drawdown_pct": 0.0,
            "cumulative_return_pct": 0.0,
        }

    ordered = trades.sort_values(["entry_date", "symbol"]).copy()
    ordered["gross_return_pct"] = ordered["gross_return_pct"].astype(float)
    ordered["net_return_pct"] = ordered["gross_return_pct"] - (cost_bps_round_trip / 100)

    gross_returns = ordered["gross_return_pct"] / 100
    net_returns = ordered["net_return_pct"] / 100

    gross_std = gross_returns.std(ddof=1)
    net_std = net_returns.std(ddof=1)

    gross_sharpe = None
    net_sharpe = None
    if len(gross_returns) >= 2 and pd.notna(gross_std) and gross_std > 0:
        gross_sharpe = float(gross_returns.mean() / gross_std * math.sqrt(len(gross_returns)))
    if len(net_returns) >= 2 and pd.notna(net_std) and net_std > 0:
        net_sharpe = float(net_returns.mean() / net_std * math.sqrt(len(net_returns)))

    confidence_ic = None
    if ordered["signal_score"].nunique(dropna=True) > 1 and ordered["net_return_pct"].nunique(dropna=True) > 1:
        confidence_ic = float(ordered["signal_score"].corr(ordered["net_return_pct"]))

    equity = (1 + net_returns).cumprod()

    return {
        "n_trades": int(len(ordered)),
        "hit_rate_pct": float((ordered["net_return_pct"] > 0).mean() * 100),
        "avg_gross_return_pct": float(ordered["gross_return_pct"].mean()),
        "avg_net_return_pct": float(ordered["net_return_pct"].mean()),
        "gross_sharpe_ratio": gross_sharpe,
        "net_sharpe_ratio": net_sharpe,
        "confidence_ic": confidence_ic,
        "max_drawdown_pct": _max_drawdown_pct(equity),
        "cumulative_return_pct": float((equity.iloc[-1] - 1) * 100),
    }


def _build_trade_rows(hist: pd.DataFrame, symbol: str, cfg: BacktestConfig) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    usable = hist.dropna(subset=["Close", "sma_20", "sma_50", "momentum_5d_pct", "rsi_14"]).copy()
    if usable.empty:
        return rows

    idx = 0
    while idx < len(usable) - (cfg.hold_days + 1):
        signal_row = usable.iloc[idx]
        if not bool(signal_row["enter_long"]):
            idx += 1
            continue

        entry_idx = idx + 1
        exit_idx = entry_idx + cfg.hold_days
        if exit_idx >= len(usable):
            break

        entry_row = usable.iloc[entry_idx]
        exit_row = usable.iloc[exit_idx]

        entry_price = float(entry_row["Close"])
        exit_price = float(exit_row["Close"])
        gross_return_pct = (exit_price / entry_price - 1) * 100

        rows.append(
            {
                "symbol": symbol,
                "signal_date": signal_row["DateOnly"],
                "entry_date": entry_row["DateOnly"],
                "exit_date": exit_row["DateOnly"],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "signal_score": float(signal_row["signal_score"]),
                "momentum_5d_pct": float(signal_row["momentum_5d_pct"]),
                "trend_spread_pct": float(signal_row["trend_spread_pct"]),
                "gross_return_pct": gross_return_pct,
                "hold_days": cfg.hold_days,
            }
        )

        idx = exit_idx + 1

    return rows


def _buy_and_hold_metrics(histories: dict[str, pd.DataFrame]) -> dict[str, float]:
    returns = []
    for symbol, hist in histories.items():
        clean = hist.dropna(subset=["Close"])
        if clean.empty:
            continue
        first_close = float(clean.iloc[0]["Close"])
        last_close = float(clean.iloc[-1]["Close"])
        returns.append((last_close / first_close - 1) * 100)

    if not returns:
        return {"buy_and_hold_return_pct": 0.0}

    series = pd.Series(returns, dtype=float)
    return {
        "buy_and_hold_return_pct": float(series.mean()),
    }


def _equal_weight_benchmark(histories: dict[str, pd.DataFrame]) -> dict[str, float]:
    if not histories:
        return {"equal_weight_return_pct": 0.0, "equal_weight_sharpe_ratio": None, "equal_weight_max_drawdown_pct": 0.0}

    daily_returns = []
    for symbol, hist in histories.items():
        clean = hist.dropna(subset=["Close"]).copy()
        if clean.empty:
            continue
        close = clean.set_index(pd.to_datetime(clean["DateOnly"]))["Close"]
        daily_returns.append(close.pct_change().rename(symbol))

    if not daily_returns:
        return {"equal_weight_return_pct": 0.0, "equal_weight_sharpe_ratio": None, "equal_weight_max_drawdown_pct": 0.0}

    returns_frame = pd.concat(daily_returns, axis=1).dropna(how="all")
    returns_frame = returns_frame.fillna(0)
    portfolio_returns = returns_frame.mean(axis=1)
    equity = (1 + portfolio_returns).cumprod()

    sharpe = None
    std = portfolio_returns.std(ddof=1)
    if len(portfolio_returns) >= 2 and pd.notna(std) and std > 0:
        sharpe = float(portfolio_returns.mean() / std * math.sqrt(252))

    return {
        "equal_weight_return_pct": float((equity.iloc[-1] - 1) * 100),
        "equal_weight_sharpe_ratio": sharpe,
        "equal_weight_max_drawdown_pct": _max_drawdown_pct(equity),
    }


def _build_equal_weight_curve(histories: dict[str, pd.DataFrame]) -> pd.Series:
    daily_returns = []
    for symbol, hist in histories.items():
        clean = hist.dropna(subset=["Close"]).copy()
        if clean.empty:
            continue
        close = clean.set_index(pd.to_datetime(clean["DateOnly"]))["Close"]
        daily_returns.append(close.pct_change().rename(symbol))

    if not daily_returns:
        return pd.Series(dtype=float)

    returns_frame = pd.concat(daily_returns, axis=1).dropna(how="all").fillna(0)
    portfolio_returns = returns_frame.mean(axis=1)
    return (1 + portfolio_returns).cumprod()


def _plot_backtest_outputs(
    trades: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    summary: dict[str, object],
) -> list[str]:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    saved_files: list[str] = []

    if trades.empty:
        return saved_files

    ordered = trades.sort_values(["entry_date", "symbol"]).copy()
    ordered["net_return_pct"] = ordered["gross_return_pct"] - (float(summary["cost_bps_round_trip"]) / 100)
    ordered["equity_curve"] = (1 + ordered["net_return_pct"] / 100).cumprod()

    equity_path = PLOTS_DIR / "equity_curve.png"
    plt.figure(figsize=(10, 5))
    plt.plot(ordered["entry_date"], ordered["equity_curve"], label="Strategy equity", linewidth=2)
    equal_weight_curve = _build_equal_weight_curve(histories)
    if not equal_weight_curve.empty:
        plt.plot(equal_weight_curve.index, equal_weight_curve.values, label="Equal-weight benchmark", linewidth=2)
    plt.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    plt.title("ETF Backtest Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Growth of $1")
    plt.legend()
    plt.tight_layout()
    plt.savefig(equity_path, dpi=150)
    plt.close()
    saved_files.append(str(equity_path))

    histogram_path = PLOTS_DIR / "trade_return_distribution.png"
    plt.figure(figsize=(10, 5))
    plt.hist(ordered["net_return_pct"], bins=min(20, max(5, len(ordered) // 2)), alpha=0.85, color="#2f6fed")
    plt.title("Distribution of Net Trade Returns")
    plt.xlabel("Net return (%)")
    plt.ylabel("Trades")
    plt.tight_layout()
    plt.savefig(histogram_path, dpi=150)
    plt.close()
    saved_files.append(str(histogram_path))

    symbol_returns = ordered.groupby("symbol")["net_return_pct"].mean().sort_values(ascending=False)
    symbol_path = PLOTS_DIR / "average_return_by_symbol.png"
    plt.figure(figsize=(10, 5))
    plt.bar(symbol_returns.index, symbol_returns.values, color="#1f9d55")
    plt.title("Average Net Return by Symbol")
    plt.xlabel("Symbol")
    plt.ylabel("Average net return (%)")
    plt.tight_layout()
    plt.savefig(symbol_path, dpi=150)
    plt.close()
    saved_files.append(str(symbol_path))

    score_path = PLOTS_DIR / "signal_score_vs_return.png"
    plt.figure(figsize=(10, 5))
    plt.scatter(ordered["signal_score"], ordered["net_return_pct"], alpha=0.75, color="#b45309")
    plt.title("Signal Score vs Net Return")
    plt.xlabel("Signal score")
    plt.ylabel("Net return (%)")
    plt.tight_layout()
    plt.savefig(score_path, dpi=150)
    plt.close()
    saved_files.append(str(score_path))

    return saved_files


def run_etf_backtest(cfg: BacktestConfig) -> dict[str, object]:
    histories: dict[str, pd.DataFrame] = {}
    all_trades: list[dict[str, object]] = []

    for symbol in cfg.universe:
        hist = _normalize_history(symbol, cfg.start_date, cfg.end_date)
        if hist.empty:
            continue

        hist = _strategy_signal_score(hist)
        histories[symbol] = hist
        all_trades.extend(_build_trade_rows(hist, symbol, cfg))

    trades = pd.DataFrame(all_trades)
    trade_metrics = _trade_metrics(trades, cfg.cost_bps_round_trip)
    buy_and_hold = _buy_and_hold_metrics(histories)
    equal_weight = _equal_weight_benchmark(histories)
    plot_files = _plot_backtest_outputs(trades, histories, {"cost_bps_round_trip": cfg.cost_bps_round_trip})

    summary = {
        "universe": cfg.universe,
        "testing_period": {
            "start": cfg.start_date,
            "end": cfg.end_date,
            "hold_days": cfg.hold_days,
        },
        "signal_definition": (
            "Go long when 5-day momentum is positive, price is above the 20-day and 50-day SMA, "
            "and RSI(14) is below 70. Enter on the next close and exit after a fixed holding period."
        ),
        "cost_bps_round_trip": cfg.cost_bps_round_trip,
        **trade_metrics,
        **buy_and_hold,
        **equal_weight,
        "trades": trades,
        "plot_files": plot_files,
    }
    return summary
