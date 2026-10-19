"""
Loop utama automation bot. Jalankan via run_bot.py di root repo.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from .config import ExecutionConfig
from .exchange_client import ExchangeClient
from .order_executor import OrderExecutor
from .risk_manager import RiskManager
from .signal_generator import SignalGenerator
from .trade_logger import TradeLogger


class AutomationBot:
    def __init__(self, config: ExecutionConfig):
        self.config = config

        if config.is_live:
            # Gagal cepat di startup kalau config live tidak valid — jangan nunggu
            # sampai ada sinyal baru nemu masalahnya.
            config.validate_for_live()

        exchange_client = None
        if config.api_key and config.api_secret:
            exchange_client = ExchangeClient(config)

        risk_manager = RiskManager(config)
        signal_generator = SignalGenerator(config)
        logger = TradeLogger(config.log_path)

        self.executor = OrderExecutor(
            config=config,
            risk_manager=risk_manager,
            signal_generator=signal_generator,
            logger=logger,
            exchange_client=exchange_client,
        )
        self.risk_manager = risk_manager

    def run_once(self) -> None:
        """Satu putaran: proses semua simbol di watchlist."""
        mode = "LIVE — UANG SUNGGUHAN" if self.config.is_live else "dry_run (simulasi)"
        if self.risk_manager.kill_switch_active():
            print(f"[{self._now()}] KILL SWITCH AKTIF — entry baru diblokir, posisi terbuka tetap dikelola.")

        for symbol in self.config.watchlist:
            try:
                self.executor.process_symbol(symbol)
            except Exception as e:
                print(f"[{self._now()}] [ERROR] {symbol}: {e}")

    def run_forever(self, max_iterations: int | None = None) -> None:
        mode = "LIVE — UANG SUNGGUHAN" if self.config.is_live else "DRY_RUN (simulasi, tidak ada order sungguhan)"
        print(f"=== Trading Automation Bot — mode: {mode} ===")
        print(f"Exchange     : {self.config.exchange_id} (testnet={self.config.use_testnet})")
        print(f"Watchlist    : {', '.join(self.config.watchlist)}")
        print(f"Poll interval: {self.config.poll_interval_seconds}s")
        print(f"Risk limits  : max_position=${self.config.max_position_usd} "
              f"max_daily_loss=${self.config.max_daily_loss_usd} "
              f"max_open_positions={self.config.max_open_positions}")
        print(f"Kill switch  : hapus/hentikan dengan membuat file '{self.config.kill_switch_path}'")
        print()

        iteration = 0
        try:
            while max_iterations is None or iteration < max_iterations:
                self.run_once()
                iteration += 1
                if max_iterations is None or iteration < max_iterations:
                    time.sleep(self.config.poll_interval_seconds)
        except KeyboardInterrupt:
            print(f"\n[{self._now()}] Dihentikan manual (Ctrl+C).")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
