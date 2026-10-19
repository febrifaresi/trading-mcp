"""
Konfigurasi execution engine — semua dari environment variables.
Default selalu paling aman (dry_run, testnet) — harus sengaja diubah untuk live trading.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _float_env(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


def _int_env(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


@dataclass
class ExecutionConfig:
    exchange_id: str = "bybit"

    api_key: str = ""
    api_secret: str = ""

    # Testnet ON secara default. Harus eksplisit di-set false untuk pakai exchange sungguhan.
    use_testnet: bool = True

    # "dry_run" (default, tidak pernah kirim order sungguhan) atau "live".
    trading_mode: str = "dry_run"

    # Watchlist simbol crypto, format ccxt "BASE/QUOTE". Pisah koma di env.
    watchlist: list[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])

    timeframe: str = "1h"
    poll_interval_seconds: int = 300

    # Minimum confluence score (0-8) sebelum sinyal dianggap valid untuk eksekusi.
    min_confluence_score: int = 6

    # --- Risk limits ---
    max_position_usd: float = 50.0
    max_daily_loss_usd: float = 25.0
    max_open_positions: int = 3
    risk_per_trade_pct: float = 1.0  # % dari balance quote currency

    # ATR multiplier untuk stop-loss & take-profit
    atr_stop_multiplier: float = 1.5
    atr_target_multiplier: float = 2.5

    kill_switch_path: str = "KILL_SWITCH"
    state_path: str = "execution_state.json"
    log_path: str = "trade_log.jsonl"

    # Balance simulasi dipakai saat dry_run TANPA API key (supaya bisa dicoba tanpa akun exchange).
    dry_run_balance_usd: float = 1000.0

    # --- Signal source: "rules" (default, deterministic confluence score) atau "llm" (Qwen via OpenRouter) ---
    signal_source: str = "rules"
    openrouter_api_key: str = ""
    llm_model: str = "qwen/qwen3-30b-a3b-instruct-2507"
    llm_timeout_seconds: float = 20.0
    news_max_headlines: int = 8
    news_lookback_hours: int = 24

    @property
    def is_live(self) -> bool:
        return self.trading_mode.strip().lower() == "live"

    @classmethod
    def from_env(cls) -> "ExecutionConfig":
        watchlist_raw = os.getenv("WATCHLIST", "")
        watchlist = (
            [s.strip() for s in watchlist_raw.split(",") if s.strip()]
            if watchlist_raw
            else cls().watchlist
        )

        return cls(
            exchange_id=os.getenv("EXECUTION_EXCHANGE", "bybit"),
            api_key=os.getenv("BYBIT_API_KEY", ""),
            api_secret=os.getenv("BYBIT_API_SECRET", ""),
            use_testnet=_bool_env("BYBIT_TESTNET", True),
            trading_mode=os.getenv("TRADING_MODE", "dry_run"),
            watchlist=watchlist,
            timeframe=os.getenv("EXECUTION_TIMEFRAME", "1h"),
            poll_interval_seconds=_int_env("POLL_INTERVAL_SECONDS", 300),
            min_confluence_score=_int_env("MIN_CONFLUENCE_SCORE", 6),
            max_position_usd=_float_env("MAX_POSITION_USD", 50.0),
            max_daily_loss_usd=_float_env("MAX_DAILY_LOSS_USD", 25.0),
            max_open_positions=_int_env("MAX_OPEN_POSITIONS", 3),
            risk_per_trade_pct=_float_env("RISK_PER_TRADE_PCT", 1.0),
            atr_stop_multiplier=_float_env("ATR_STOP_MULTIPLIER", 1.5),
            atr_target_multiplier=_float_env("ATR_TARGET_MULTIPLIER", 2.5),
            kill_switch_path=os.getenv("KILL_SWITCH_PATH", "KILL_SWITCH"),
            state_path=os.getenv("EXECUTION_STATE_PATH", "execution_state.json"),
            log_path=os.getenv("TRADE_LOG_PATH", "trade_log.jsonl"),
            dry_run_balance_usd=_float_env("DRY_RUN_BALANCE_USD", 1000.0),
            signal_source=os.getenv("SIGNAL_SOURCE", "rules"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", "qwen/qwen3-30b-a3b-instruct-2507"),
            llm_timeout_seconds=_float_env("LLM_TIMEOUT_SECONDS", 20.0),
            news_max_headlines=_int_env("NEWS_MAX_HEADLINES", 8),
            news_lookback_hours=_int_env("NEWS_LOOKBACK_HOURS", 24),
        )

    def validate_signal_source(self) -> None:
        if self.signal_source not in ("rules", "llm"):
            raise ValueError(f"SIGNAL_SOURCE tidak dikenal: '{self.signal_source}' (harus 'rules' atau 'llm')")
        if self.signal_source == "llm" and not self.openrouter_api_key:
            raise ValueError(
                "SIGNAL_SOURCE=llm tapi OPENROUTER_API_KEY belum di-set. "
                "Isi dulu di .env, atau pakai SIGNAL_SOURCE=rules."
            )

    def validate_for_live(self) -> None:
        """Pengecekan wajib sebelum boleh jalan di mode live. Raise jika tidak lolos."""
        if not self.is_live:
            return
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "TRADING_MODE=live tapi BYBIT_API_KEY/BYBIT_API_SECRET belum di-set."
            )
        if self.use_testnet:
            raise ValueError(
                "TRADING_MODE=live tapi BYBIT_TESTNET masih true — ini kontradiktif. "
                "Set BYBIT_TESTNET=false untuk benar-benar live, atau TRADING_MODE=dry_run untuk simulasi."
            )
        if self.max_position_usd <= 0 or self.max_daily_loss_usd <= 0:
            raise ValueError("MAX_POSITION_USD dan MAX_DAILY_LOSS_USD harus > 0 untuk live trading.")
