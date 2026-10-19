"""
Confluence scorer — dipakai bersama oleh MCP server (analisa manual)
dan execution engine (automation). Dipindah ke sini supaya automation
tidak perlu import mcp_server.py.
"""

from __future__ import annotations

from .technical import TechnicalResult
from .structure import StructureResult


def confluence_score(
    tech_result: TechnicalResult,
    struct_result: StructureResult,
) -> tuple[int, list[str]]:
    """
    Hitung confluence score 0-8 berdasarkan alignment indikator + struktur.
    """
    ind     = tech_result.indicators
    current = ind.close
    score   = 0
    reasons: list[str] = []

    # 1. EMA stack aligned
    if ind.ema_stack in ("FULL_BULL", "FULL_BEAR"):
        score += 1
        reasons.append(f"EMA stack sejajar ({ind.ema_stack})")

    # 2. Trend bias clear
    if ind.trend_bias != "NEUTRAL":
        score += 1
        reasons.append(f"Trend bias jelas: {ind.trend_bias}")

    # 3. RSI di zona yang tepat
    if ind.trend_bias == "BULLISH" and 40 <= ind.rsi <= 65:
        score += 1
        reasons.append(f"RSI {ind.rsi:.1f} — zona pullback sehat (bullish)")
    elif ind.trend_bias == "BEARISH" and 35 <= ind.rsi <= 60:
        score += 1
        reasons.append(f"RSI {ind.rsi:.1f} — zona bounce sehat (bearish)")
    elif ind.rsi_condition == "OVERSOLD" and ind.trend_bias != "BEARISH":
        score += 1
        reasons.append(f"RSI {ind.rsi:.1f} — oversold, potensi reversal naik")
    elif ind.rsi_condition == "OVERBOUGHT" and ind.trend_bias != "BULLISH":
        score += 1
        reasons.append(f"RSI {ind.rsi:.1f} — overbought, potensi reversal turun")

    # 4. MACD aligned dengan trend
    if ind.trend_bias == "BULLISH" and ind.macd_cross in ("ABOVE_SIGNAL", "BULLISH_CROSS"):
        score += 1
        reasons.append(f"MACD bullish ({ind.macd_cross})")
    elif ind.trend_bias == "BEARISH" and ind.macd_cross in ("BELOW_SIGNAL", "BEARISH_CROSS"):
        score += 1
        reasons.append(f"MACD bearish ({ind.macd_cross})")

    # 5. BOS/CHoCH terbaru aligned
    last_b = struct_result.last_break
    if last_b:
        if ind.trend_bias == "BULLISH" and last_b.direction == "BULLISH":
            score += 1
            reasons.append(f"Struktur {last_b.kind} konfirmasi bullish")
        elif ind.trend_bias == "BEARISH" and last_b.direction == "BEARISH":
            score += 1
            reasons.append(f"Struktur {last_b.kind} konfirmasi bearish")

    # 6. Active Order Block dalam jangkauan (2x ATR)
    atr = ind.atr or (current * 0.003)
    for ob in struct_result.active_order_blocks:
        if abs(ob.midpoint - current) <= atr * 2:
            score += 1
            reasons.append(f"OB {ob.kind} aktif dekat harga ({ob.midpoint:,.5f})")
            break

    # 7. Open FVG dalam jangkauan (3x ATR)
    for fvg in struct_result.open_fvgs:
        if abs(fvg.midpoint - current) <= atr * 3:
            score += 1
            reasons.append(f"FVG {fvg.kind} belum terisi ({fvg.midpoint:,.5f})")
            break

    # 8. Volume spike
    if ind.vol_spike:
        score += 1
        reasons.append(f"Volume spike ({ind.vol_ratio:.1f}x rata-rata)")

    return score, reasons
