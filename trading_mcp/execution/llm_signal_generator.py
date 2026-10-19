"""
Signal generator mode "llm": konteks teknikal (reuse engine yang sama persis
dengan mode "rules") + berita terbaru, lalu Qwen yang memutuskan ARAH.

Menghasilkan Signal yang sama persis bentuknya dengan SignalGenerator biasa,
jadi OrderExecutor/RiskManager tidak perlu tahu atau peduli sinyalnya dari
rules atau dari LLM — gerbang risk tetap sama untuk keduanya.
"""

from __future__ import annotations

from typing import Callable

from ..data.fetcher import DataFetcher
from ..analysis.technical import TechnicalEngine
from ..analysis.structure import StructureEngine
from ..analysis.confluence import confluence_score
from .config import ExecutionConfig
from .llm_advisor import LLMAdvisor
from .news_feed import Headline, fetch_headlines
from .signal_generator import Signal


class LLMSignalGenerator:
    def __init__(
        self,
        config: ExecutionConfig,
        advisor: LLMAdvisor | None = None,
        news_fetcher: Callable[[str, int, int], list[Headline]] = fetch_headlines,
        fetcher: DataFetcher | None = None,
        tech: TechnicalEngine | None = None,
        struct: StructureEngine | None = None,
    ):
        self.config = config
        self.advisor = advisor or LLMAdvisor(config)
        self.news_fetcher = news_fetcher
        self.fetcher = fetcher or DataFetcher()
        self.tech = tech or TechnicalEngine()
        self.struct = struct or StructureEngine(swing_n=3)

    def generate(self, symbol: str) -> Signal:
        data = self.fetcher.get(
            symbol,
            self.config.timeframe,
            limit=250,
            exchange=self.config.exchange_id,
        )
        tech_result = self.tech.calculate(data)
        struct_result = self.struct.analyze(data)
        score, tech_reasons = confluence_score(tech_result, struct_result)
        ind = tech_result.indicators

        headlines = self.news_fetcher(
            symbol, self.config.news_max_headlines, self.config.news_lookback_hours
        )

        decision = self.advisor.decide(
            symbol=symbol,
            price=ind.close,
            trend_bias=ind.trend_bias,
            confluence_score=score,
            confluence_reasons=tech_reasons,
            headlines=headlines,
        )

        reasons = list(tech_reasons)
        reasons.append(
            f"[LLM {self.config.llm_model}] confidence={decision.confidence:.2f} — {decision.reasoning}"
        )

        return Signal(
            symbol=symbol,
            direction=decision.direction,
            score=score,
            reasons=reasons,
            price=ind.close,
            atr=ind.atr,
        )
