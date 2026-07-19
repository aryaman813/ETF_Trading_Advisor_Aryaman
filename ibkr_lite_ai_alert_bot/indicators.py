import pandas as pd


def sma(series: pd.Series, window: int) -> float | None:
    # check if the length of the series after dropping NaN values is less than the window, then return None
    if len(series.dropna()) < window:
        return None
    # Else, return the last value of the rolling mean of the series with the specified window
    return float(series.rolling(window).mean().iloc[-1])


def rsi(series: pd.Series, window: int = 14) -> float | None:
    # First clean the series of prices by dropping NaN values
    clean = series.dropna()
    # If the length of the cleaned series of prices is less than or equal to the window, return None
    if len(clean) <= window:
        return None
    # Calculate the difference between consecutive prices in the cleaned series
    delta = clean.diff()
    # Calculate the gain series from the delta by clipping the negative values to 0, and the loss series by clipping the positive values to 0 and negating it
    gain = delta.clip(lower=0)
    # Calculate the loss series from the delta by clipping the positive values to 0 and negating it
    loss = -delta.clip(upper=0)

    # Calculate the average gain series by taking the rolling mean of the gain series with the specified window
    avg_gain = gain.rolling(window).mean()
    # Calculate the average loss series by taking the rolling mean of the loss series with the specified window
    avg_loss = loss.rolling(window).mean()

    # assign the last value of the average loss series to a variable
    last_loss = avg_loss.iloc[-1]
    # If the last value of the average loss series is 0, return 100.0 (indicating that the RSI is at its maximum value)
    if last_loss == 0:
        return 100.0
    # Else, calculate the relative strength (RS) by dividing the last value of the average gain series by the last value of the average loss series
    rs = avg_gain.iloc[-1] / last_loss
    # Return the RSI value using the formula: 100 - (100 / (1 + RS))
    # If RS is very large, gains domonate losses, so (100 / (1 + RS)) approaches 0.
    # Hence, RSI approaches 100.
    # If RS is = 1, gains and losses are equal, so (100 / (1 + RS)) approaches 50.
    # Hence, RSI approaches 50.
    # If RS is very small, losses dominate gains, so (100 / (1 + RS)) approaches 100.
    # Hence, RSI approaches 0.
    return float(100 - (100 / (1 + rs)))


def rsi_series(series: pd.Series, window: int = 14) -> pd.Series:
    # Clean the series of prices by dropping NaN values.
    clean = series.dropna()
    # Creating a series to hold the RSI values, with the same index as the original series and a float data type.
    result = pd.Series(index=series.index, dtype=float)
    # If the length of the cleaned series of prices is less than or equal to the window,
    # Then return the result series (which will be filled with NaN values).
    if len(clean) <= window:
        return result

    # Create a series of the differences between consecutive prices in the cleaned series.
    delta = clean.diff()

    # Calculate the gain series from the delta by clipping the negative values to 0.
    gain = delta.clip(lower=0)
    # Calculate the loss series from the delta by clipping the positive values to 0 and negating it.
    loss = -delta.clip(upper=0)

    # Calculate the average gain series by taking the rolling mean of the gain series with the specified window
    avg_gain = gain.rolling(window).mean()
    # Calculate the average loss series by taking the rolling mean of the loss series with the specified window
    avg_loss = loss.rolling(window).mean()

    # Calculate the relative strength (RS) series by dividing the average gain series by the average loss series.
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    # Calculate the RSI values using the formula: 100 - (100 / (1 + RS))
    values = 100 - (100 / (1 + rs))
    # Assign the calculated RSI values to the corresponding indices in the result series.
    result.loc[clean.index] = values
    return result


def pct_change(series: pd.Series, periods: int) -> float | None:
    # Clean the series of prices by dropping NaN values
    clean = series.dropna()
    # If the length of the cleaned series of prices is less than or equal to the specified number of periods, return None
    if len(clean) <= periods:
        return None
    # Else, calculate the percentage change over the specified number of periods and return it as a float
    return float((clean.iloc[-1] / clean.iloc[-1 - periods] - 1) * 100)

def average_volume(series: pd.Series, window: int) -> float | None:
    # Clean the series of volumes by dropping NaN values
    clean = series.dropna()
    # If the length of the cleaned series of volumes is less than or equal to the specified window, return None
    if len(clean) <= window:
        return None
    # Else, calculate the average volume over the specified window and return it as a float
    return float(clean.rolling(window).mean().iloc[-1])