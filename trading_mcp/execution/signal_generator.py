"""
Jembatan antara analysis engine (sudah ada, read-only) dan execution engine (baru).
Tidak menduplikasi logika indikator/struktur — reuse langsung.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..data.fetcher import DataFetcher
from ..analysis.technical import TechnicalEngine
from ..analysis.structure import StructureEngine
from ..analysis.confluence import confluence_score
from .config import ExecutionConfig


@dataclass
class Signal:
    symbol: str
    direction: str  # "LONG_ENTRY" | "EXIT" | "NONE"
    score: int
    reasons: list[str]
    price: float
    atr: float


class SignalGenerator:
    """
    Spot-only, long-only: BULLISH confluence kuat -> LONG_ENTRY.
    BEARISH confluence kuat saat posisi terbuka -> EXIT.
    Selain itu -> NONE (tidak ada aksi).
    """

    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.fetcher = DataFetcher()
        self.tech = TechnicalEngine()
        self.struct = StructureEngine(swing_n=3)

    def generate(self, symbol: str) -> Signal:
        data = self.fetcher.get(
            symbol,
            self.config.timeframe,
            limit=250,
            exchange=self.config.exchange_id,
        )
        tech_result = self.tech.calculate(data)
        struct_result = self.struct.analyze(data)
        score, reasons = confluence_score(tech_result, struct_result)

        ind = tech_result.indicators
        direction = "NONE"

        if ind.trend_bias == "BULLISH" and score >= self.config.min_confluence_score:
            direction = "LONG_ENTRY"
        elif ind.trend_bias == "BEARISH" and score >= self.config.min_confluence_score:
            direction = "EXIT"

        return Signal(
            symbol=symbol,
            direction=direction,
            score=score,
            reasons=reasons,
            price=ind.close,
            atr=ind.atr,
        )
