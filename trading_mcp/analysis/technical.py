import pandas as pd
import pandas_ta as ta
from dataclasses import dataclass, field

from ..models.ohlcv import OHLCVData, MarketType
from .indicators import Indicators


@dataclass
class TechnicalResult:
    """Output dari TechnicalEngine.calculate()."""
    symbol: str
    market: MarketType
    timeframe: str
    indicators: Indicators
    df: pd.DataFrame = field(repr=False)  # OHLCV + semua kolom indikator

    def __str__(self) -> str:
        return (
            f"[{self.market.value}] {self.symbol} {self.timeframe}\n"
            f"{self.indicators}"
        )


class TechnicalEngine:
    """
    Kalkulasi indikator teknikal dari OHLCVData.
    Semua menggunakan pandas-ta — tidak perlu install TA-Lib.

    Indikator yang dihitung:
      Trend     : EMA 8/21/50/200
      Momentum  : RSI 14, MACD 12/26/9
      Volatility: Bollinger Bands 20/2, ATR 14
      Volume    : Volume MA 20, Volume Ratio
    """

    def __init__(
        self,
        ema_periods: list[int] | None = None,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0,
        atr_period: int = 14,
        vol_ma_period: int = 20,
    ):
        self.ema_periods = ema_periods or [8, 21, 50, 200]
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.atr_period = atr_period
        self.vol_ma_period = vol_ma_period

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(self, data: OHLCVData) -> TechnicalResult:
        """
        Hitung semua indikator dari OHLCVData.
        Butuh minimal ~200 bar untuk indikator yang akurat.
        """
        if len(data.df) < 30:
            raise ValueError(
                f"Data terlalu sedikit ({len(data.df)} bar). "
                "Butuh minimal 30 bar untuk kalkulasi indikator."
            )

        df = data.df.copy()

        self._add_ema(df)
        self._add_rsi(df)
        self._add_macd(df)
        self._add_bbands(df)
        self._add_atr(df)
        self._add_volume(df)

        indicators = self._extract_latest(df)

        return TechnicalResult(
            symbol=data.symbol,
            market=data.market,
            timeframe=data.timeframe,
            df=df,
            indicators=indicators,
        )

    # ------------------------------------------------------------------
    # Indicator calculators
    # ------------------------------------------------------------------

    def _add_ema(self, df: pd.DataFrame):
        for period in self.ema_periods:
            df[f"ema{period}"] = ta.ema(df["close"], length=period)

    def _add_rsi(self, df: pd.DataFrame):
        df["rsi"] = ta.rsi(df["close"], length=self.rsi_period)

    def _add_macd(self, df: pd.DataFrame):
        macd_df = ta.macd(
            df["close"],
            fast=self.macd_fast,
            slow=self.macd_slow,
            signal=self.macd_signal,
        )
        if macd_df is not None and not macd_df.empty:
            # pandas-ta column names: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
            df["macd"] = macd_df.iloc[:, 0]
            df["macd_hist"] = macd_df.iloc[:, 1]
            df["macd_signal"] = macd_df.iloc[:, 2]

    def _add_bbands(self, df: pd.DataFrame):
        bb_df = ta.bbands(df["close"], length=self.bb_period, std=self.bb_std)
        if bb_df is not None and not bb_df.empty:
            # Columns: BBL, BBM, BBU, BBB, BBP
            df["bb_lower"] = bb_df.iloc[:, 0]
            df["bb_mid"]   = bb_df.iloc[:, 1]
            df["bb_upper"] = bb_df.iloc[:, 2]
            df["bb_width"] = bb_df.iloc[:, 3]  # bandwidth %
            df["bb_pct"]   = bb_df.iloc[:, 4]  # %B (0=lower, 1=upper)

    def _add_atr(self, df: pd.DataFrame):
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=self.atr_period)

    def _add_volume(self, df: pd.DataFrame):
        df["vol_ma20"] = ta.sma(df["volume"], length=self.vol_ma_period)
        df["vol_ratio"] = df["volume"] / df["vol_ma20"].replace(0, float("nan"))

    # ------------------------------------------------------------------
    # Snapshot extraction & interpretation
    # ------------------------------------------------------------------

    def _extract_latest(self, df: pd.DataFrame) -> Indicators:
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        close = float(last["close"])

        # EMA values
        ema_vals = {p: self._safe(last, f"ema{p}") for p in self.ema_periods}

        # ATR
        atr = self._safe(last, "atr")
        atr_pct = round(atr / close * 100, 3) if close else 0.0

        # BB
        bb_upper = self._safe(last, "bb_upper")
        bb_mid   = self._safe(last, "bb_mid")
        bb_lower = self._safe(last, "bb_lower")
        bb_width = self._safe(last, "bb_width")

        # Volume
        volume   = self._safe(last, "volume")
        vol_ma20 = self._safe(last, "vol_ma20")
        vol_ratio = round(self._safe(last, "vol_ratio"), 2)

        # MACD
        macd       = self._safe(last, "macd")
        macd_sig   = self._safe(last, "macd_signal")
        macd_hist  = self._safe(last, "macd_hist")
        prev_macd  = self._safe(prev, "macd")
        prev_sig   = self._safe(prev, "macd_signal")

        return Indicators(
            close=round(close, 5),
            ema8=round(ema_vals.get(8, 0), 5),
            ema21=round(ema_vals.get(21, 0), 5),
            ema50=round(ema_vals.get(50, 0), 5),
            ema200=round(ema_vals.get(200, 0), 5),
            trend_bias=self._trend_bias(close, ema_vals),
            ema_stack=self._ema_stack(ema_vals),
            rsi=round(self._safe(last, "rsi"), 1),
            rsi_condition=self._rsi_condition(self._safe(last, "rsi")),
            macd=round(macd, 5),
            macd_signal_line=round(macd_sig, 5),
            macd_hist=round(macd_hist, 5),
            macd_cross=self._macd_cross(macd, macd_sig, prev_macd, prev_sig),
            bb_upper=round(bb_upper, 5),
            bb_mid=round(bb_mid, 5),
            bb_lower=round(bb_lower, 5),
            bb_width_pct=round(bb_width, 2),
            bb_position=self._bb_position(close, bb_upper, bb_mid, bb_lower),
            atr=round(atr, 5),
            atr_pct=atr_pct,
            volume=round(volume, 2),
            vol_ma20=round(vol_ma20, 2),
            vol_ratio=vol_ratio,
            vol_spike=vol_ratio > 2.0,
        )

    # ------------------------------------------------------------------
    # Interpretation helpers
    # ------------------------------------------------------------------

    def _trend_bias(self, close: float, ema: dict[int, float]) -> str:
        e50  = ema.get(50, 0)
        e200 = ema.get(200, 0)
        e21  = ema.get(21, 0)
        e8   = ema.get(8, 0)

        if not all([e50, e200, e21, e8]):
            return "NEUTRAL"

        bull = close > e21 > e50 > e200
        bear = close < e21 < e50 < e200

        if bull:
            return "BULLISH"
        if bear:
            return "BEARISH"
        return "NEUTRAL"

    def _ema_stack(self, ema: dict[int, float]) -> str:
        """Cek apakah EMA 8 > 21 > 50 > 200 (full bull) atau sebaliknya."""
        vals = [ema.get(p, 0) for p in sorted(self.ema_periods)]
        if all(v > 0 for v in vals):
            if vals == sorted(vals, reverse=True):
                return "FULL_BULL"
            if vals == sorted(vals):
                return "FULL_BEAR"
        return "MIXED"

    def _rsi_condition(self, rsi: float) -> str:
        if rsi >= 70:
            return "OVERBOUGHT"
        if rsi <= 30:
            return "OVERSOLD"
        return "NEUTRAL"

    def _macd_cross(
        self,
        macd: float, sig: float,
        prev_macd: float, prev_sig: float,
    ) -> str:
        """Deteksi golden cross / death cross pada bar terakhir."""
        if prev_macd <= prev_sig and macd > sig:
            return "BULLISH_CROSS"
        if prev_macd >= prev_sig and macd < sig:
            return "BEARISH_CROSS"
        if macd > sig:
            return "ABOVE_SIGNAL"
        if macd < sig:
            return "BELOW_SIGNAL"
        return "NONE"

    def _bb_position(
        self,
        close: float,
        upper: float, mid: float, lower: float,
    ) -> str:
        if close > upper:
            return "ABOVE_UPPER"
        if close > mid:
            return "UPPER"
        if close > lower:
            return "LOWER"
        return "BELOW_LOWER"

    @staticmethod
    def _safe(row: pd.Series, col: str) -> float:
        """Ambil nilai float dari Series, return 0.0 jika NaN/missing."""
        val = row.get(col, 0.0)
        try:
            f = float(val)
            return 0.0 if pd.isna(f) else f
        except (TypeError, ValueError):
            return 0.0
