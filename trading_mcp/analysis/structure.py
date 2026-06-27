from __future__ import annotations

import pandas as pd
from dataclasses import dataclass, field
from typing import Any

from ..models.ohlcv import OHLCVData, MarketType


# ------------------------------------------------------------------
# Data models
# ------------------------------------------------------------------

@dataclass
class SwingPoint:
    bar_idx:   int
    timestamp: Any        # pd.Timestamp
    price:     float
    kind:      str        # "HIGH" | "LOW"

    def __str__(self) -> str:
        return f"Swing {self.kind} @ {self.price:.5f} ({self.timestamp.date()})"


@dataclass
class KeyLevel:
    price:    float
    kind:     str         # "RESISTANCE" | "SUPPORT"
    touches:  int
    strength: str         # "STRONG" | "MODERATE" | "WEAK"

    def __str__(self) -> str:
        return f"{self.strength} {self.kind} @ {self.price:.5f} ({self.touches}x tested)"


@dataclass
class StructureBreak:
    timestamp:     Any
    broken_price:  float
    kind:          str    # "BOS" | "CHoCH"
    direction:     str    # "BULLISH" | "BEARISH"

    def __str__(self) -> str:
        return (
            f"{self.kind} {self.direction} — broke {self.broken_price:.5f} "
            f"@ {self.timestamp.date()}"
        )


@dataclass
class OrderBlock:
    timestamp: Any
    top:       float
    bottom:    float
    kind:      str        # "BULLISH" | "BEARISH"
    mitigated: bool

    @property
    def midpoint(self) -> float:
        return round((self.top + self.bottom) / 2, 5)

    def __str__(self) -> str:
        status = "MITIGATED" if self.mitigated else "ACTIVE"
        return (
            f"{self.kind} OB [{status}] {self.bottom:.5f}–{self.top:.5f} "
            f"@ {self.timestamp.date()}"
        )


@dataclass
class FairValueGap:
    timestamp: Any
    top:       float
    bottom:    float
    kind:      str        # "BULLISH" | "BEARISH"
    filled:    bool

    @property
    def midpoint(self) -> float:
        return round((self.top + self.bottom) / 2, 5)

    @property
    def size(self) -> float:
        return round(self.top - self.bottom, 5)

    def __str__(self) -> str:
        status = "FILLED" if self.filled else "OPEN"
        return (
            f"{self.kind} FVG [{status}] {self.bottom:.5f}–{self.top:.5f} "
            f"(size {self.size:.5f}) @ {self.timestamp.date()}"
        )


@dataclass
class StructureResult:
    symbol:           str
    market:           MarketType
    timeframe:        str
    market_structure: str         # "UPTREND" | "DOWNTREND" | "RANGING"
    swing_highs:      list[SwingPoint]
    swing_lows:       list[SwingPoint]
    key_levels:       list[KeyLevel]
    breaks:           list[StructureBreak]
    order_blocks:     list[OrderBlock]
    fair_value_gaps:  list[FairValueGap]
    df:               pd.DataFrame = field(repr=False)

    # -- convenience properties --

    @property
    def active_order_blocks(self) -> list[OrderBlock]:
        return [ob for ob in self.order_blocks if not ob.mitigated]

    @property
    def open_fvgs(self) -> list[FairValueGap]:
        return [fvg for fvg in self.fair_value_gaps if not fvg.filled]

    @property
    def last_break(self) -> StructureBreak | None:
        return self.breaks[-1] if self.breaks else None

    def nearest_levels(self, n: int = 5) -> list[KeyLevel]:
        current = float(self.df["close"].iloc[-1])
        return sorted(self.key_levels, key=lambda l: abs(l.price - current))[:n]

    def to_dict(self) -> dict:
        current = float(self.df["close"].iloc[-1])
        return {
            "market_structure": self.market_structure,
            "current_price":    round(current, 5),
            "last_break":       str(self.last_break) if self.last_break else None,
            "recent_breaks":    [str(b) for b in self.breaks[-3:]],
            "nearest_levels":   [str(l) for l in self.nearest_levels(5)],
            "active_obs":       [str(ob) for ob in self.active_order_blocks[-3:]],
            "open_fvgs":        [str(f) for f in self.open_fvgs[-3:]],
            "swing_high_count": len(self.swing_highs),
            "swing_low_count":  len(self.swing_lows),
        }

    def __str__(self) -> str:
        lines = [
            f"[{self.market.value}] {self.symbol} {self.timeframe} — {self.market_structure}",
        ]
        if self.last_break:
            lines.append(f"Last break : {self.last_break}")

        nearest = self.nearest_levels(3)
        if nearest:
            lines.append("Nearest S/R:")
            for l in nearest:
                lines.append(f"  {l}")

        active_obs = self.active_order_blocks[-2:]
        if active_obs:
            lines.append("Active OBs :")
            for ob in active_obs:
                lines.append(f"  {ob}")

        open_fvgs = self.open_fvgs[-2:]
        if open_fvgs:
            lines.append("Open FVGs  :")
            for fvg in open_fvgs:
                lines.append(f"  {fvg}")

        return "\n".join(lines)


# ------------------------------------------------------------------
# Engine
# ------------------------------------------------------------------

class StructureEngine:
    """
    Analisa struktur harga (SMC/ICT concepts):
      - Swing High/Low detection
      - Support & Resistance clustering
      - Break of Structure (BOS) & Change of Character (CHoCH)
      - Order Blocks
      - Fair Value Gaps (FVG)
    """

    def __init__(
        self,
        swing_n: int = 3,
        level_tolerance_pct: float = 0.3,
        min_fvg_atr_ratio: float = 0.1,
        max_order_blocks: int = 6,
        max_fvgs: int = 10,
    ):
        self.swing_n = swing_n
        self.level_tolerance_pct = level_tolerance_pct
        self.min_fvg_atr_ratio = min_fvg_atr_ratio
        self.max_order_blocks = max_order_blocks
        self.max_fvgs = max_fvgs

    def analyze(self, data: OHLCVData) -> StructureResult:
        if len(data.df) < self.swing_n * 2 + 5:
            raise ValueError(
                f"Data terlalu sedikit ({len(data.df)} bar). "
                f"Butuh minimal {self.swing_n * 2 + 5} bar."
            )

        df = data.df.copy()
        atr = self._calc_atr(df)

        highs, lows         = self._find_swings(df)
        key_levels          = self._cluster_levels(highs, lows, atr, df)
        market_structure, breaks = self._find_structure_breaks(highs, lows)
        order_blocks        = self._find_order_blocks(df, highs, lows, atr)
        fair_value_gaps     = self._find_fvgs(df, atr)

        return StructureResult(
            symbol=data.symbol,
            market=data.market,
            timeframe=data.timeframe,
            market_structure=market_structure,
            swing_highs=highs,
            swing_lows=lows,
            key_levels=key_levels,
            breaks=breaks,
            order_blocks=order_blocks,
            fair_value_gaps=fair_value_gaps,
            df=df,
        )

    # ------------------------------------------------------------------
    # 1. Swing detection
    # ------------------------------------------------------------------

    def _find_swings(
        self, df: pd.DataFrame
    ) -> tuple[list[SwingPoint], list[SwingPoint]]:
        n = self.swing_n
        highs: list[SwingPoint] = []
        lows: list[SwingPoint]  = []
        high_arr = df["high"].values
        low_arr  = df["low"].values

        for i in range(n, len(df) - n):
            h = high_arr[i]
            l = low_arr[i]

            is_sh = all(h >= high_arr[i - j] for j in range(1, n + 1)) and \
                    all(h >  high_arr[i + j] for j in range(1, n + 1))

            is_sl = all(l <= low_arr[i - j] for j in range(1, n + 1)) and \
                    all(l <  low_arr[i + j] for j in range(1, n + 1))

            if is_sh:
                highs.append(SwingPoint(i, df.index[i], round(h, 8), "HIGH"))
            if is_sl:
                lows.append(SwingPoint(i, df.index[i], round(l, 8), "LOW"))

        return highs, lows

    # ------------------------------------------------------------------
    # 2. Key level clustering
    # ------------------------------------------------------------------

    def _cluster_levels(
        self,
        highs: list[SwingPoint],
        lows: list[SwingPoint],
        atr: float,
        df: pd.DataFrame,
    ) -> list[KeyLevel]:
        current_price = float(df["close"].iloc[-1])
        # Tolerance: setengah ATR atau minimum 0.1% dari harga
        tolerance = max(atr * 0.5, current_price * self.level_tolerance_pct / 100)

        levels: list[KeyLevel] = []
        for swing_list, kind in [(highs, "RESISTANCE"), (lows, "SUPPORT")]:
            prices = sorted(s.price for s in swing_list)
            if not prices:
                continue

            clusters: list[list[float]] = [[prices[0]]]
            for price in prices[1:]:
                if price - clusters[-1][-1] <= tolerance:
                    clusters[-1].append(price)
                else:
                    clusters.append([price])

            for cluster in clusters:
                avg   = round(sum(cluster) / len(cluster), 8)
                count = len(cluster)
                strength = "STRONG" if count >= 3 else "MODERATE" if count >= 2 else "WEAK"
                levels.append(KeyLevel(avg, kind, count, strength))

        # Sort: kuat dulu, lalu yang paling dekat harga sekarang
        levels.sort(key=lambda l: (l.strength != "STRONG", abs(l.price - current_price)))
        return levels

    # ------------------------------------------------------------------
    # 3. Market structure + BOS / CHoCH
    # ------------------------------------------------------------------

    def _find_structure_breaks(
        self,
        highs: list[SwingPoint],
        lows: list[SwingPoint],
    ) -> tuple[str, list[StructureBreak]]:
        """
        Gabungkan highs dan lows secara kronologis, lalu track:
          HH + HL → UPTREND   |  LH + LL → DOWNTREND

        BOS   = konfirmasi trend berlanjut
        CHoCH = struktur berubah (reversal signal)
        """
        breaks: list[StructureBreak] = []

        if len(highs) < 2 or len(lows) < 2:
            return "RANGING", breaks

        all_swings = sorted(highs + lows, key=lambda s: s.bar_idx)

        prev_high: SwingPoint | None = None
        prev_low:  SwingPoint | None = None
        state = "UNKNOWN"  # "BULL" | "BEAR" | "UNKNOWN"

        for swing in all_swings:
            if swing.kind == "HIGH":
                if prev_high is not None:
                    if swing.price > prev_high.price:   # Higher High
                        if state == "BEAR":
                            breaks.append(StructureBreak(
                                swing.timestamp, prev_high.price, "CHoCH", "BULLISH"
                            ))
                        elif state == "BULL":
                            breaks.append(StructureBreak(
                                swing.timestamp, prev_high.price, "BOS", "BULLISH"
                            ))
                        state = "BULL"
                    else:                                # Lower High
                        if state == "BULL":
                            # LH dalam uptrend — belum CHoCH, tapi warning
                            pass
                        state = "BEAR" if state in ("BEAR", "UNKNOWN") else state
                prev_high = swing

            else:  # LOW
                if prev_low is not None:
                    if swing.price < prev_low.price:    # Lower Low
                        if state == "BULL":
                            breaks.append(StructureBreak(
                                swing.timestamp, prev_low.price, "CHoCH", "BEARISH"
                            ))
                        elif state == "BEAR":
                            breaks.append(StructureBreak(
                                swing.timestamp, prev_low.price, "BOS", "BEARISH"
                            ))
                        state = "BEAR"
                    else:                               # Higher Low
                        state = "BULL" if state in ("BULL", "UNKNOWN") else state
                prev_low = swing

        # Tentukan struktur akhir dari state + pola terakhir
        market_structure = self._classify_structure(state, highs[-3:], lows[-3:])
        return market_structure, breaks

    def _classify_structure(
        self,
        state: str,
        recent_highs: list[SwingPoint],
        recent_lows: list[SwingPoint],
    ) -> str:
        if state == "BULL":
            # Verifikasi: minimal HH + HL
            hh = len(recent_highs) >= 2 and recent_highs[-1].price > recent_highs[-2].price
            hl = len(recent_lows)  >= 2 and recent_lows[-1].price  > recent_lows[-2].price
            return "UPTREND" if hh or hl else "RANGING"

        if state == "BEAR":
            lh = len(recent_highs) >= 2 and recent_highs[-1].price < recent_highs[-2].price
            ll = len(recent_lows)  >= 2 and recent_lows[-1].price  < recent_lows[-2].price
            return "DOWNTREND" if lh or ll else "RANGING"

        return "RANGING"

    # ------------------------------------------------------------------
    # 4. Order Blocks
    # ------------------------------------------------------------------

    def _find_order_blocks(
        self,
        df: pd.DataFrame,
        highs: list[SwingPoint],
        lows: list[SwingPoint],
        atr: float,
    ) -> list[OrderBlock]:
        """
        Bullish OB : candle bearish terakhir sebelum impulse naik yang memecah swing high
        Bearish OB : candle bullish terakhir sebelum impulse turun yang memecah swing low
        """
        obs: list[OrderBlock] = []
        open_arr  = df["open"].values
        close_arr = df["close"].values
        high_arr  = df["high"].values
        low_arr   = df["low"].values
        current   = close_arr[-1]

        lookback = 5  # cari OB dalam N bar sebelum swing

        # Bullish OBs — dari swing highs
        for sh in highs[-(self.max_order_blocks):]:
            idx = sh.bar_idx
            start = max(0, idx - lookback)
            # Cari candle bearish terakhir sebelum swing high
            for j in range(idx - 1, start - 1, -1):
                if close_arr[j] < open_arr[j]:   # bearish candle
                    top    = round(float(open_arr[j]), 8)
                    bottom = round(float(close_arr[j]), 8)
                    if top <= bottom:
                        top, bottom = bottom, top
                    mitigated = current < top  # price kembali ke zona OB
                    obs.append(OrderBlock(df.index[j], top, bottom, "BULLISH", mitigated))
                    break

        # Bearish OBs — dari swing lows
        for sl in lows[-(self.max_order_blocks):]:
            idx = sl.bar_idx
            start = max(0, idx - lookback)
            # Cari candle bullish terakhir sebelum swing low
            for j in range(idx - 1, start - 1, -1):
                if close_arr[j] > open_arr[j]:   # bullish candle
                    top    = round(float(close_arr[j]), 8)
                    bottom = round(float(open_arr[j]), 8)
                    mitigated = current > bottom  # price kembali ke zona OB
                    obs.append(OrderBlock(df.index[j], top, bottom, "BEARISH", mitigated))
                    break

        # Sort chronologis, buang duplikat timestamp
        seen = set()
        unique_obs: list[OrderBlock] = []
        for ob in sorted(obs, key=lambda o: o.timestamp):
            key = (str(ob.timestamp), ob.kind)
            if key not in seen:
                seen.add(key)
                unique_obs.append(ob)

        return unique_obs

    # ------------------------------------------------------------------
    # 5. Fair Value Gaps
    # ------------------------------------------------------------------

    def _find_fvgs(self, df: pd.DataFrame, atr: float) -> list[FairValueGap]:
        """
        Bullish FVG : df['low'][i] > df['high'][i-2]  — gap ke atas
        Bearish FVG : df['high'][i] < df['low'][i-2]  — gap ke bawah
        Minimum size = min_fvg_atr_ratio * ATR
        """
        min_size = atr * self.min_fvg_atr_ratio
        high_arr  = df["high"].values
        low_arr   = df["low"].values
        close_arr = df["close"].values
        fvgs: list[FairValueGap] = []

        for i in range(2, len(df)):
            # Bullish FVG
            gap_top    = round(float(low_arr[i]), 8)
            gap_bottom = round(float(high_arr[i - 2]), 8)
            if gap_top > gap_bottom and (gap_top - gap_bottom) >= min_size:
                # Filled jika close pernah turun ke bawah gap_top setelah terbentuk
                filled = any(
                    low_arr[k] <= gap_top
                    for k in range(i + 1, len(df))
                )
                fvgs.append(FairValueGap(
                    df.index[i], gap_top, gap_bottom, "BULLISH", filled
                ))

            # Bearish FVG
            gap_top    = round(float(low_arr[i - 2]), 8)
            gap_bottom = round(float(high_arr[i]), 8)
            if gap_top > gap_bottom and (gap_top - gap_bottom) >= min_size:
                filled = any(
                    high_arr[k] >= gap_top
                    for k in range(i + 1, len(df))
                )
                fvgs.append(FairValueGap(
                    df.index[i], gap_top, gap_bottom, "BEARISH", filled
                ))

        # Urutkan kronologis, ambil yang terbaru
        fvgs.sort(key=lambda f: f.timestamp)
        return fvgs[-self.max_fvgs:]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_atr(df: pd.DataFrame, period: int = 14) -> float:
        if "atr" in df.columns:
            val = df["atr"].dropna().iloc[-1] if not df["atr"].dropna().empty else None
            if val and val > 0:
                return float(val)
        # Hitung ATR sederhana jika belum ada
        high  = df["high"]
        low   = df["low"]
        close = df["close"]
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low  - prev_close).abs(),
        ], axis=1).max(axis=1)
        return float(tr.rolling(period).mean().iloc[-1])
