import yfinance as yf
from schemas import MarketSnapshot
from indicators import sma, rsi, pct_change, average_volume

def get_snapshot(symbol: str, period: str = "6mo") -> MarketSnapshot:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period, interval="1d", auto_adjust=True)

    if hist.empty:
        raise RuntimeError(f"No market data returned for {symbol}")

    close = hist["Close"]
    volume = hist["Volume"]

    return MarketSnapshot(
        symbol=symbol.upper(),
        last_close=float(close.iloc[-1]),
        sma_20=sma(close, 20),
        sma_50=sma(close, 50),
        rsi_14=rsi(close, 14),
        average_volume_20=average_volume(volume, 20),
        latest_volume=float(volume.iloc[-1]) if len(volume.dropna()) else None,
        pct_change_1d=pct_change(close, 1),
        pct_change_5d=pct_change(close, 5),
    )
