from ..models.ohlcv import MarketType, OHLCVData, VALID_TIMEFRAMES, CACHE_TTL
from ..utils.symbol import detect_market, normalize_symbol
from ..utils.cache import TTLCache
from . import sources


class DataFetcher:
    """
    Satu-satunya pintu masuk untuk mengambil data OHLCV.

    Penggunaan:
        fetcher = DataFetcher()
        data = fetcher.get("BBCA.JK", "1d")
        data = fetcher.get("EURUSD", "4h")
        data = fetcher.get("BTC/USDT", "1h")
    """

    def __init__(self):
        self._cache = TTLCache()

    def get(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 200,
        market: MarketType | None = None,
        force_refresh: bool = False,
        exchange: str = "binance",
    ) -> OHLCVData:
        """
        Ambil OHLCV data untuk simbol apapun.

        Args:
            symbol:        Simbol dalam format apapun (BBCA.JK / EURUSD / BTC/USDT)
            timeframe:     1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
            limit:         Jumlah bar yang diinginkan (max bergantung sumber)
            market:        Override deteksi otomatis pasar (opsional)
            force_refresh: Abaikan cache dan fetch ulang
            exchange:      Exchange untuk crypto (default: binance)
        """
        if timeframe not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Timeframe '{timeframe}' tidak valid. "
                f"Pilihan: {sorted(VALID_TIMEFRAMES)}"
            )

        detected_market = market or detect_market(symbol)
        normalized = normalize_symbol(symbol, detected_market)

        # Cek cache dulu
        if not force_refresh:
            cached = self._cache.get(normalized, timeframe, limit)
            if cached is not None:
                return cached

        # Fetch dari sumber yang sesuai
        data = self._fetch(normalized, detected_market, timeframe, limit, exchange)

        # Simpan ke cache
        ttl = CACHE_TTL.get(timeframe, 300)
        self._cache.set(normalized, timeframe, limit, data, ttl)

        return data

    def get_multi_timeframe(
        self,
        symbol: str,
        timeframes: list[str] | None = None,
        limit: int = 200,
    ) -> dict[str, OHLCVData]:
        """
        Ambil beberapa timeframe sekaligus untuk satu simbol.
        Default: D1, H4, H1 — cocok untuk analisa top-down.
        """
        if timeframes is None:
            timeframes = ["1d", "4h", "1h"]

        result = {}
        for tf in timeframes:
            try:
                result[tf] = self.get(symbol, tf, limit)
            except Exception as e:
                print(f"[WARN] Gagal fetch {symbol} {tf}: {e}")

        return result

    def clear_cache(self, symbol: str | None = None):
        if symbol:
            detected = detect_market(symbol)
            normalized = normalize_symbol(symbol, detected)
            self._cache.invalidate(normalized)
        else:
            self._cache.clear()

    @property
    def cache_size(self) -> int:
        return self._cache.size

    # ------------------------------------------------------------------
    # Internal routing
    # ------------------------------------------------------------------

    def _fetch(
        self,
        symbol: str,
        market: MarketType,
        timeframe: str,
        limit: int,
        exchange: str,
    ) -> OHLCVData:
        if market == MarketType.IDX:
            return sources.idx.fetch(symbol, timeframe, limit)

        if market == MarketType.FOREX:
            return sources.forex.fetch(symbol, timeframe, limit)

        if market == MarketType.CRYPTO:
            return sources.crypto.fetch(symbol, timeframe, limit, exchange_id=exchange)

        raise ValueError(f"Market type tidak dikenali: {market}")
