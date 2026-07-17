import pandas as pd


def sma(series: pd.Series, window: int) -> float | None:
    if len(series.dropna()) < window:
        return None
    return float(series.rolling(window).mean().iloc[-1])


def rsi(series: pd.Series, window: int = 14) -> float | None:
    clean = series.dropna()
    if len(clean) <= window:
        return None

    delta = clean.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()

    last_loss = avg_loss.iloc[-1]
    if last_loss == 0:
        return 100.0

    rs = avg_gain.iloc[-1] / last_loss
    return float(100 - (100 / (1 + rs)))


def pct_change(series: pd.Series, periods: int) -> float | None:
    clean = series.dropna()
    if len(clean) <= periods:
        return None
    return float((clean.iloc[-1] / clean.iloc[-1 - periods] - 1) * 100)
