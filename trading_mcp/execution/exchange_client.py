"""
Wrapper tipis di atas ccxt untuk order execution.
Satu-satunya tempat yang boleh menyentuh API trading exchange sungguhan.
"""

from __future__ import annotations

import ccxt

from .config import ExecutionConfig


class ExchangeClient:
    """
    Wrap ccxt exchange instance untuk eksekusi order.
    Tidak pernah dipanggil langsung saat dry_run — order_executor yang memutuskan itu.
    """

    def __init__(self, config: ExecutionConfig):
        self.config = config
        exchange_class = getattr(ccxt, config.exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"ccxt tidak punya exchange '{config.exchange_id}'")

        self._exchange: ccxt.Exchange = exchange_class({
            "apiKey": config.api_key,
            "secret": config.api_secret,
            "enableRateLimit": True,
        })

        if config.use_testnet:
            self._exchange.set_sandbox_mode(True)

    @property
    def exchange_id(self) -> str:
        return self.config.exchange_id

    def fetch_balance_quote(self, quote: str = "USDT") -> float:
        """Ambil available balance untuk currency quote (default USDT)."""
        balance = self._exchange.fetch_balance()
        free = balance.get("free", {}) or {}
        return float(free.get(quote, 0.0))

    def fetch_open_positions_count(self) -> int:
        """
        Hitung berapa simbol yang masih punya saldo base currency > 0 (spot = posisi terbuka).
        Untuk spot, "posisi" didekati dari holdings non-quote yang bukan debu (dust).
        """
        balance = self._exchange.fetch_balance()
        free = balance.get("free", {}) or {}
        dust_threshold = 1e-6
        return sum(
            1 for ccy, amount in free.items()
            if ccy not in ("USDT", "USD", "USDC") and amount > dust_threshold
        )

    def create_market_buy(self, symbol: str, amount: float) -> dict:
        """Market buy. amount dalam base currency (misal BTC untuk BTC/USDT)."""
        return self._exchange.create_order(symbol, "market", "buy", amount)

    def create_market_sell(self, symbol: str, amount: float) -> dict:
        """Market sell (dipakai untuk exit posisi long yang sudah dibuka)."""
        return self._exchange.create_order(symbol, "market", "sell", amount)

    def fetch_ticker_price(self, symbol: str) -> float:
        ticker = self._exchange.fetch_ticker(symbol)
        return float(ticker["last"])
