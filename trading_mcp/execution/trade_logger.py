"""
Audit log append-only. Setiap keputusan (sinyal masuk, hasil risk check, hasil order)
dicatat sebagai satu baris JSON — baik di dry_run maupun live, supaya ada jejak lengkap
untuk evaluasi/debug, termasuk keputusan yang DITOLAK risk manager.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class TradeLogger:
    def __init__(self, path: str):
        self.path = Path(path)

    def _write(self, event: dict) -> None:
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(self.path, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def log_signal(self, symbol: str, direction: str, score: int, reasons: list[str]) -> None:
        self._write({
            "event": "signal",
            "symbol": symbol,
            "direction": direction,
            "score": score,
            "reasons": reasons,
        })

    def log_risk_rejected(self, symbol: str, reason: str) -> None:
        self._write({
            "event": "risk_rejected",
            "symbol": symbol,
            "reason": reason,
        })

    def log_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        mode: str,
        order_result: dict | None = None,
    ) -> None:
        self._write({
            "event": "order",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "mode": mode,  # "dry_run" | "live"
            "order_result": order_result,
        })

    def log_close(self, symbol: str, exit_price: float, pnl: float, reason: str, mode: str) -> None:
        self._write({
            "event": "close",
            "symbol": symbol,
            "exit_price": exit_price,
            "pnl": pnl,
            "reason": reason,  # "stop_loss" | "take_profit" | "signal_exit"
            "mode": mode,
        })

    def log_error(self, symbol: str, message: str) -> None:
        self._write({
            "event": "error",
            "symbol": symbol,
            "message": message,
        })
