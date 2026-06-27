from dataclasses import dataclass, field
from enum import Enum
import pandas as pd


class MarketType(str, Enum):
    IDX = "IDX"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"


# Timeframes yang kita support secara internal
VALID_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}

# TTL cache per timeframe (dalam detik)
CACHE_TTL: dict[str, int] = {
    "1m":  60,
    "5m":  300,
    "15m": 600,
    "30m": 900,
    "1h":  1800,
    "4h":  3600,
    "1d":  14400,
    "1w":  86400,
}


@dataclass
class OHLCVData:
    """
    Output standar dari semua sumber data.
    df selalu punya kolom: open, high, low, close, volume
    index: DatetimeIndex (timezone-aware, UTC)
    """
    symbol: str          # normalized symbol, e.g. "BBCA.JK", "EURUSD", "BTC/USDT"
    market: MarketType
    timeframe: str       # e.g. "1h", "4h", "1d"
    source: str          # e.g. "yfinance", "ccxt:binance"
    df: pd.DataFrame = field(repr=False)

    @property
    def latest(self) -> pd.Series:
        return self.df.iloc[-1]

    @property
    def latest_close(self) -> float:
        return float(self.df["close"].iloc[-1])

    @property
    def bar_count(self) -> int:
        return len(self.df)

    def __str__(self) -> str:
        latest = self.latest
        return (
            f"[{self.market.value}] {self.symbol} {self.timeframe} | "
            f"{self.bar_count} bars | "
            f"Last close: {latest['close']:.4f} @ {self.df.index[-1]}"
        )
