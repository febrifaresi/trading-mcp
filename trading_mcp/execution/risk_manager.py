"""
Risk manager — satu-satunya tempat yang memutuskan boleh/tidaknya sebuah order dieksekusi.
Semua limit di sini bersifat hard-stop: kalau gagal satu cek, order TIDAK dieksekusi, titik.

Kill switch: menghentikan ENTRY baru (posisi baru). Posisi yang sudah terbuka tetap
dikelola (stop-loss/take-profit tetap bisa exit) supaya modal yang sudah di pasar
tidak dibiarkan tanpa pengaman saat kamu sedang investigasi masalah.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from .config import ExecutionConfig


@dataclass
class PositionState:
    symbol: str
    entry_price: float
    qty: float
    stop_price: float
    target_price: float
    opened_at: str


class StateStore:
    """Persist posisi terbuka + realized PnL harian ke file JSON lokal."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            with open(self.path, "r") as f:
                return json.load(f)
        return {"positions": {}, "daily_pnl": {"date": "", "realized": 0.0}}

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2, default=str)

    @property
    def positions(self) -> dict[str, dict]:
        return self._data["positions"]

    def get_position(self, symbol: str) -> PositionState | None:
        raw = self.positions.get(symbol)
        return PositionState(**raw) if raw else None

    def open_position(self, pos: PositionState) -> None:
        self._data["positions"][pos.symbol] = asdict(pos)
        self._save()

    def close_position(self, symbol: str) -> None:
        self._data["positions"].pop(symbol, None)
        self._save()

    def open_position_count(self) -> int:
        return len(self._data["positions"])

    def today_realized_pnl(self) -> float:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._data["daily_pnl"].get("date") != today:
            self._data["daily_pnl"] = {"date": today, "realized": 0.0}
            self._save()
        return float(self._data["daily_pnl"]["realized"])

    def add_realized_pnl(self, amount: float) -> None:
        # Pastikan tanggal up to date dulu (reset jika hari baru)
        self.today_realized_pnl()
        self._data["daily_pnl"]["realized"] += amount
        self._save()


class RiskManager:
    def __init__(self, config: ExecutionConfig, state: StateStore | None = None):
        self.config = config
        self.state = state or StateStore(config.state_path)

    # ------------------------------------------------------------------
    # Gate checks — semua harus lolos sebelum entry baru dieksekusi
    # ------------------------------------------------------------------

    def kill_switch_active(self) -> bool:
        return os.path.exists(self.config.kill_switch_path)

    def daily_loss_breached(self) -> bool:
        realized = self.state.today_realized_pnl()
        return realized <= -abs(self.config.max_daily_loss_usd)

    def can_open_new_position(self, symbol: str) -> tuple[bool, str]:
        if self.kill_switch_active():
            return False, f"Kill switch aktif ({self.config.kill_switch_path} ditemukan) — entry baru diblokir."

        if self.daily_loss_breached():
            return False, (
                f"Circuit breaker: realized loss hari ini sudah mencapai limit "
                f"(${self.state.today_realized_pnl():.2f} <= -${self.config.max_daily_loss_usd:.2f})."
            )

        if self.state.get_position(symbol) is not None:
            return False, f"Sudah ada posisi terbuka untuk {symbol}."

        if self.state.open_position_count() >= self.config.max_open_positions:
            return False, (
                f"Sudah mencapai max_open_positions ({self.config.max_open_positions})."
            )

        return True, "OK"

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def calculate_position_size(
        self,
        balance_quote: float,
        entry_price: float,
        atr: float,
    ) -> tuple[float, float, float]:
        """
        Hitung ukuran posisi berbasis risk % dari balance dan jarak stop (ATR).
        Return: (qty_base, stop_price, target_price)
        """
        if entry_price <= 0 or atr <= 0:
            return 0.0, 0.0, 0.0

        stop_distance = atr * self.config.atr_stop_multiplier
        target_distance = atr * self.config.atr_target_multiplier

        stop_price = round(entry_price - stop_distance, 8)
        target_price = round(entry_price + target_distance, 8)

        risk_amount_usd = balance_quote * (self.config.risk_per_trade_pct / 100.0)
        stop_distance_pct = stop_distance / entry_price
        if stop_distance_pct <= 0:
            return 0.0, stop_price, target_price

        position_usd = risk_amount_usd / stop_distance_pct

        # Hard caps: tidak boleh lebih dari max_position_usd, dan tidak boleh lebih dari balance tersedia
        position_usd = min(position_usd, self.config.max_position_usd, balance_quote)

        if position_usd <= 0:
            return 0.0, stop_price, target_price

        qty_base = position_usd / entry_price
        return qty_base, stop_price, target_price

    # ------------------------------------------------------------------
    # State mutation
    # ------------------------------------------------------------------

    def register_open(self, symbol: str, entry_price: float, qty: float, stop_price: float, target_price: float) -> None:
        self.state.open_position(PositionState(
            symbol=symbol,
            entry_price=entry_price,
            qty=qty,
            stop_price=stop_price,
            target_price=target_price,
            opened_at=datetime.now(timezone.utc).isoformat(),
        ))

    def register_close(self, symbol: str, exit_price: float) -> float:
        """Hitung realized PnL, catat ke daily tracker, hapus posisi. Return realized PnL (USD)."""
        pos = self.state.get_position(symbol)
        if pos is None:
            return 0.0
        pnl = (exit_price - pos.entry_price) * pos.qty
        self.state.add_realized_pnl(pnl)
        self.state.close_position(symbol)
        return pnl

    def get_position(self, symbol: str) -> PositionState | None:
        return self.state.get_position(symbol)
