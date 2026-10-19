"""
Order executor — satu-satunya tempat yang benar-benar memanggil create_order().
Dry-run dan live mode melewati jalur logika yang SAMA (risk check, sizing, logging);
bedanya cuma apakah order_result sungguhan dikirim ke exchange atau disimulasikan.
"""

from __future__ import annotations

from .config import ExecutionConfig
from .exchange_client import ExchangeClient
from .risk_manager import RiskManager
from .signal_generator import Signal, SignalGenerator
from .trade_logger import TradeLogger


class OrderExecutor:
    def __init__(
        self,
        config: ExecutionConfig,
        risk_manager: RiskManager,
        signal_generator: SignalGenerator,
        logger: TradeLogger,
        exchange_client: ExchangeClient | None = None,
    ):
        self.config = config
        self.risk_manager = risk_manager
        self.signal_generator = signal_generator
        self.logger = logger
        # exchange_client boleh None di dry_run tanpa API key sama sekali.
        self.exchange_client = exchange_client

    def process_symbol(self, symbol: str) -> None:
        try:
            signal = self.signal_generator.generate(symbol)
        except Exception as e:
            self.logger.log_error(symbol, f"Gagal generate signal: {e}")
            return

        self.logger.log_signal(symbol, signal.direction, signal.score, signal.reasons)

        existing = self.risk_manager.get_position(symbol)
        if existing is not None:
            self._manage_open_position(symbol, signal, existing)
        else:
            self._maybe_enter(symbol, signal)

    # ------------------------------------------------------------------

    def _maybe_enter(self, symbol: str, signal: Signal) -> None:
        if signal.direction != "LONG_ENTRY":
            return

        ok, reason = self.risk_manager.can_open_new_position(symbol)
        if not ok:
            self.logger.log_risk_rejected(symbol, reason)
            return

        balance = self._get_balance_quote()
        qty, stop_price, target_price = self.risk_manager.calculate_position_size(
            balance, signal.price, signal.atr
        )

        if qty <= 0:
            self.logger.log_risk_rejected(
                symbol, f"Ukuran posisi 0 — balance=${balance:.2f}, ATR tidak valid, atau cap terlalu kecil."
            )
            return

        order_result = None
        if self.config.is_live:
            self.config.validate_for_live()
            order_result = self.exchange_client.create_market_buy(symbol, qty)

        self.risk_manager.register_open(symbol, signal.price, qty, stop_price, target_price)
        self.logger.log_order(
            symbol, "buy", qty, signal.price,
            mode="live" if self.config.is_live else "dry_run",
            order_result=order_result,
        )

    def _manage_open_position(self, symbol: str, signal: Signal, position) -> None:
        exit_reason = None

        if signal.price <= position.stop_price:
            exit_reason = "stop_loss"
        elif signal.price >= position.target_price:
            exit_reason = "take_profit"
        elif signal.direction == "EXIT":
            exit_reason = "signal_exit"

        if exit_reason is None:
            return  # hold posisi, tidak ada aksi

        order_result = None
        if self.config.is_live:
            self.config.validate_for_live()
            order_result = self.exchange_client.create_market_sell(symbol, position.qty)

        pnl = self.risk_manager.register_close(symbol, signal.price)
        mode = "live" if self.config.is_live else "dry_run"
        self.logger.log_order(symbol, "sell", position.qty, signal.price, mode=mode, order_result=order_result)
        self.logger.log_close(symbol, signal.price, pnl, exit_reason, mode=mode)

    # ------------------------------------------------------------------

    def _get_balance_quote(self) -> float:
        if self.config.is_live and self.exchange_client is not None:
            return self.exchange_client.fetch_balance_quote()
        return self.config.dry_run_balance_usd
