from dataclasses import dataclass


@dataclass
class Indicators:
    """
    Snapshot nilai semua indikator pada bar terakhir.
    Semua float sudah di-round untuk readability.
    """

    # --- Trend ---
    close: float
    ema8: float
    ema21: float
    ema50: float
    ema200: float
    trend_bias: str      # "BULLISH" | "BEARISH" | "NEUTRAL"
    ema_stack: str       # "FULL_BULL" | "FULL_BEAR" | "MIXED"

    # --- Momentum ---
    rsi: float
    rsi_condition: str   # "OVERBOUGHT" | "OVERSOLD" | "NEUTRAL"
    macd: float
    macd_signal_line: float
    macd_hist: float
    macd_cross: str      # "BULLISH_CROSS" | "BEARISH_CROSS" | "NONE"

    # --- Volatility ---
    bb_upper: float
    bb_mid: float
    bb_lower: float
    bb_width_pct: float  # (upper-lower)/mid * 100 — ukuran volatilitas BB
    bb_position: str     # "ABOVE_UPPER" | "UPPER" | "MIDDLE" | "LOWER" | "BELOW_LOWER"
    atr: float
    atr_pct: float       # ATR / close * 100 — volatilitas relatif

    # --- Volume ---
    volume: float
    vol_ma20: float
    vol_ratio: float     # volume / vol_ma20
    vol_spike: bool      # True jika ratio > 2.0

    def to_dict(self) -> dict:
        return {
            "trend": {
                "bias": self.trend_bias,
                "ema_stack": self.ema_stack,
                "close": self.close,
                "ema8": self.ema8,
                "ema21": self.ema21,
                "ema50": self.ema50,
                "ema200": self.ema200,
            },
            "momentum": {
                "rsi": self.rsi,
                "rsi_condition": self.rsi_condition,
                "macd": self.macd,
                "macd_signal": self.macd_signal_line,
                "macd_hist": self.macd_hist,
                "macd_cross": self.macd_cross,
            },
            "volatility": {
                "bb_upper": self.bb_upper,
                "bb_mid": self.bb_mid,
                "bb_lower": self.bb_lower,
                "bb_width_pct": self.bb_width_pct,
                "bb_position": self.bb_position,
                "atr": self.atr,
                "atr_pct": self.atr_pct,
            },
            "volume": {
                "current": self.volume,
                "ma20": self.vol_ma20,
                "ratio": self.vol_ratio,
                "spike": self.vol_spike,
            },
        }

    def __str__(self) -> str:
        vol_tag = " [VOLUME SPIKE]" if self.vol_spike else ""
        return (
            f"Trend : {self.trend_bias} ({self.ema_stack})\n"
            f"RSI   : {self.rsi:.1f} [{self.rsi_condition}]\n"
            f"MACD  : {self.macd:.4f} | hist {self.macd_hist:.4f} | {self.macd_cross}\n"
            f"BB    : {self.bb_position} | width {self.bb_width_pct:.1f}%\n"
            f"ATR   : {self.atr:.4f} ({self.atr_pct:.2f}% of price){vol_tag}"
        )
