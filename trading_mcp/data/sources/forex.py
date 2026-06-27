import pandas as pd
import yfinance as yf

from ...models.ohlcv import MarketType, OHLCVData
from ...utils.symbol import to_yfinance_symbol

_TF_MAP = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1h":  "60m",
    "4h":  "60m",   # resample
    "1d":  "1d",
    "1w":  "1wk",
}

_MAX_PERIOD = {
    "1m":  "7d",
    "5m":  "60d",
    "15m": "60d",
    "30m": "60d",
    "1h":  "730d",
    "4h":  "730d",
    "1d":  "10y",
    "1w":  "20y",
}


def fetch(symbol: str, timeframe: str, limit: int = 200) -> OHLCVData:
    """
    Ambil OHLCV pasangan forex dari yfinance (e.g. EURUSD → EURUSD=X).
    Volume selalu 0 karena forex OTC tidak punya data volume sentral.
    """
    yf_symbol = to_yfinance_symbol(symbol, MarketType.FOREX)
    yf_interval = _TF_MAP.get(timeframe, "1d")
    period = _MAX_PERIOD.get(timeframe, "10y")
    needs_resample = timeframe == "4h"

    ticker = yf.Ticker(yf_symbol)
    raw: pd.DataFrame = ticker.history(period=period, interval=yf_interval, auto_adjust=True)

    if raw.empty:
        raise ValueError(f"Tidak ada data forex untuk {symbol} ({yf_symbol})")

    df = _normalize(raw)

    if needs_resample:
        df = _resample_4h(df)

    df = df.iloc[-limit:]

    return OHLCVData(
        symbol=symbol,
        market=MarketType.FOREX,
        timeframe=timeframe,
        source="yfinance",
        df=df,
    )


def _normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index, utc=True)
    # Forex dari yfinance kadang punya bar dengan close=0, filter
    df = df[df["close"] > 0].dropna(subset=["open", "close"])
    return df


def _resample_4h(df: pd.DataFrame) -> pd.DataFrame:
    return df.resample("4h", closed="left", label="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna(subset=["open"])
