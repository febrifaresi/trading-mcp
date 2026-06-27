import pandas as pd
import yfinance as yf
import ccxt

from ...models.ohlcv import MarketType, OHLCVData

# ccxt timeframe IDs
_TF_MAP = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1d",
    "1w":  "1w",
}

# Exchange default: Bybit (lebih accessible dari Indonesia vs Binance yang sering diblok)
_DEFAULT_EXCHANGE = "bybit"

# Fallback order jika exchange utama gagal
_FALLBACK_EXCHANGES = ["bybit", "okx", "kucoin", "gateio"]


def fetch(
    symbol: str,
    timeframe: str,
    limit: int = 200,
    exchange_id: str = _DEFAULT_EXCHANGE,
) -> OHLCVData:
    """
    Ambil OHLCV crypto dari ccxt. Default: Bybit (accessible dari Indonesia).
    Otomatis fallback ke exchange lain jika gagal.
    Tidak butuh API key — hanya membaca data publik.

    symbol: format "BTC/USDT"
    """
    ccxt_tf = _TF_MAP.get(timeframe)
    if ccxt_tf is None:
        raise ValueError(f"Timeframe tidak valid: {timeframe}")

    # Susun urutan exchange: yang diminta dulu, lalu fallback
    exchanges_to_try = [exchange_id] + [
        ex for ex in _FALLBACK_EXCHANGES if ex != exchange_id
    ]

    last_error: Exception | None = None

    for ex_id in exchanges_to_try:
        try:
            exchange_class = getattr(ccxt, ex_id, None)
            if exchange_class is None:
                continue

            exchange: ccxt.Exchange = exchange_class({"enableRateLimit": True})

            if not exchange.has.get("fetchOHLCV"):
                continue

            raw = exchange.fetch_ohlcv(symbol, timeframe=ccxt_tf, limit=limit)

            if not raw:
                continue

            df = _to_dataframe(raw)
            return OHLCVData(
                symbol=symbol,
                market=MarketType.CRYPTO,
                timeframe=timeframe,
                source=f"ccxt:{ex_id}",
                df=df,
            )

        except Exception as e:
            last_error = e
            print(f"[WARN] {ex_id} gagal untuk {symbol}: {type(e).__name__} — coba exchange berikutnya")
            continue

    # Last resort: yfinance (lewat server Yahoo, jarang diblok)
    print(f"[WARN] Semua ccxt exchange gagal — mencoba yfinance sebagai fallback...")
    try:
        return _fetch_yfinance(symbol, timeframe, limit)
    except Exception as e:
        last_error = e

    raise ConnectionError(
        f"Semua sumber gagal untuk {symbol} {timeframe}. "
        f"Error terakhir: {last_error}"
    )


def _fetch_yfinance(symbol: str, timeframe: str, limit: int) -> OHLCVData:
    """
    Fallback: ambil crypto via yfinance (Yahoo Finance).
    Yahoo hanya punya pasangan USD (bukan USDT), jadi BTC/USDT → BTC-USD.
    Volume kurang akurat tapi OHLCV cukup reliable untuk analisa.
    """
    yf_symbol = _to_yfinance_crypto(symbol)

    # Mapping timeframe internal → yfinance interval
    yf_tf_map = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "60m", "4h": "60m", "1d": "1d", "1w": "1wk",
    }
    yf_period_map = {
        "1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d",
        "1h": "730d", "4h": "730d", "1d": "5y", "1w": "10y",
    }

    yf_interval = yf_tf_map.get(timeframe, "1d")
    period = yf_period_map.get(timeframe, "5y")
    needs_resample = timeframe == "4h"

    ticker = yf.Ticker(yf_symbol)
    raw: pd.DataFrame = ticker.history(period=period, interval=yf_interval, auto_adjust=True)

    if raw.empty:
        raise ValueError(f"yfinance tidak punya data untuk {yf_symbol}")

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index, utc=True)
    df = df[df["close"] > 0].dropna()

    if needs_resample:
        df = df.resample("4h", closed="left", label="left").agg(
            open=("open", "first"), high=("high", "max"),
            low=("low", "min"), close=("close", "last"),
            volume=("volume", "sum"),
        ).dropna(subset=["open"])

    df = df.iloc[-limit:]

    return OHLCVData(
        symbol=symbol,
        market=MarketType.CRYPTO,
        timeframe=timeframe,
        source="yfinance",
        df=df,
    )


def _to_yfinance_crypto(symbol: str) -> str:
    """
    Konversi format ccxt ke format yfinance untuk crypto.
    BTC/USDT  → BTC-USD
    ETH/USDT  → ETH-USD
    BTC/IDR   → BTC-IDR  (tetap, Yahoo support beberapa IDR pairs)
    BTCUSDT   → BTC-USD
    """
    s = symbol.upper().strip()

    # Sudah format yfinance (BTC-USD)
    if "-" in s:
        return s

    # Format slash: BTC/USDT, ETH/BTC
    if "/" in s:
        base, quote = s.split("/", 1)
        # USDT dan stablecoin lain → USD untuk Yahoo
        if quote in {"USDT", "USDC", "BUSD"}:
            quote = "USD"
        return f"{base}-{quote}"

    # Format tanpa separator: BTCUSDT
    for quote in ["USDT", "USDC", "BUSD", "BTC", "ETH", "IDR", "USD"]:
        if s.endswith(quote) and len(s) > len(quote):
            base = s[: -len(quote)]
            yf_quote = "USD" if quote in {"USDT", "USDC", "BUSD"} else quote
            return f"{base}-{yf_quote}"

    return s


def _to_dataframe(raw: list) -> pd.DataFrame:
    """
    ccxt mengembalikan list of [timestamp_ms, open, high, low, close, volume].
    Kita konversi ke DataFrame dengan index DatetimeIndex UTC.
    """
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df = df[df["close"] > 0].dropna()
    return df


def list_exchanges_with_ohlcv() -> list[str]:
    """Daftar exchange ccxt yang mendukung fetchOHLCV (untuk referensi)."""
    return [
        ex for ex in ccxt.exchanges
        if getattr(getattr(ccxt, ex, None), "has", {}).get("fetchOHLCV", False)
    ]
