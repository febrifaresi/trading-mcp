import re
from ..models.ohlcv import MarketType

# Pasangan forex yang umum diperdagangkan (tanpa separator)
_FOREX_PAIRS = {
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD",
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD", "GBPAUD", "CADJPY",
    "EURCHF", "GBPCHF", "AUDNZD", "AUDCAD", "GBPCAD", "EURCAD",
    "XAUUSD", "XAGUSD",   # Gold & Silver
    "USDIDR", "EURIDR",   # IDR pairs
    "US30", "US500", "NAS100", "GER40",  # indices
}

# Quote currency yang umum di crypto
_CRYPTO_QUOTES = {"USDT", "USDC", "BTC", "ETH", "BNB", "BUSD", "IDR", "USD"}


def detect_market(symbol: str) -> MarketType:
    """
    Deteksi jenis pasar dari string simbol.

    Rules (berurutan — urutan ini penting):
      1. Suffix .JK → IDX
      2. Bersihkan separator, cek known forex pairs DULU
      3. Slash + quote crypto (bukan forex) → CRYPTO
      4. Suffix crypto tanpa slash → CRYPTO
      5. 6 huruf alpha → FOREX
      6. Default → IDX
    """
    s = symbol.upper().strip()

    # 1. IDX
    if s.endswith(".JK"):
        return MarketType.IDX

    # Bersihkan: hapus "=X" hanya di akhir (yfinance suffix), lalu separator
    # JANGAN hapus huruf X dari tengah simbol (e.g. XAU dalam XAUUSD)
    clean = re.sub(r"=X$", "", s)
    clean = re.sub(r"[/\-_\.]", "", clean)

    # 2. Known forex pair — harus dicek SEBELUM logika crypto
    #    agar EUR/USD (clean=EURUSD) dan XAUUSD tidak salah ke CRYPTO
    if clean in _FOREX_PAIRS:
        return MarketType.FOREX

    # 3. Slash + quote crypto: BTC/USDT, SOL/IDR
    if "/" in s:
        quote = s.split("/")[-1].upper()
        if quote in _CRYPTO_QUOTES:
            return MarketType.CRYPTO

    # 4. Crypto tanpa slash: BTCUSDT, ETHUSDT
    for quote in _CRYPTO_QUOTES:
        if clean.endswith(quote) and len(clean) > len(quote):
            return MarketType.CRYPTO

    # 5. Pola forex 6 huruf (NZDUSD, CADJPY, dll)
    if len(clean) == 6 and clean.isalpha():
        return MarketType.FOREX

    return MarketType.IDX


def normalize_symbol(symbol: str, market: MarketType) -> str:
    """
    Kembalikan simbol dalam format kanonik per market:
      IDX    → "BBCA.JK"
      FOREX  → "EURUSD"  (tanpa separator, uppercase)
      CRYPTO → "BTC/USDT"
    """
    s = symbol.upper().strip()

    if market == MarketType.IDX:
        base = s.replace(".JK", "")
        return f"{base}.JK"

    if market == MarketType.FOREX:
        clean = re.sub(r"=X$", "", s)
        clean = re.sub(r"[/\-_\.]", "", clean)
        return clean[:6]

    if market == MarketType.CRYPTO:
        if "/" in s:
            return s
        for quote in _CRYPTO_QUOTES:
            if s.endswith(quote) and len(s) > len(quote):
                base = s[: -len(quote)]
                return f"{base}/{quote}"
        return s

    return s


# yfinance tidak support XAUUSD=X — harus pakai simbol futures/ETF
_YFINANCE_SPECIAL = {
    "XAUUSD": "GC=F",   # Gold Futures
    "XAGUSD": "SI=F",   # Silver Futures
    "XPTUSD": "PL=F",   # Platinum Futures
    "USOIL":  "CL=F",   # Crude Oil WTI
    "UKOIL":  "BZ=F",   # Brent Crude
    "US30":   "YM=F",   # Dow Jones Futures
    "US500":  "ES=F",   # S&P 500 Futures
    "NAS100": "NQ=F",   # Nasdaq Futures
    "GER40":  "GDAXI",  # DAX
}


def to_yfinance_symbol(symbol: str, market: MarketType) -> str:
    """Konversi ke format yang diterima yfinance."""
    if market == MarketType.IDX:
        return symbol  # sudah .JK

    if market == MarketType.FOREX:
        clean = re.sub(r"=X$", "", symbol.upper())
        clean = re.sub(r"[/\-_\.]", "", clean)

        # Cek special mapping dulu (Gold, Silver, Indices, Oil)
        if clean in _YFINANCE_SPECIAL:
            return _YFINANCE_SPECIAL[clean]

        return f"{clean}=X"

    return symbol  # crypto tidak pakai yfinance
