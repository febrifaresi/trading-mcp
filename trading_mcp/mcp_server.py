"""
Trading Analysis MCP Server
Wrap DataFetcher + TechnicalEngine + StructureEngine jadi tools untuk Claude.

Cara run:
    python server.py

Cara daftarkan ke Claude Desktop:
    Tambahkan ke claude_desktop_config.json (lihat README atau server.py)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastmcp import FastMCP

from .data.fetcher import DataFetcher
from .analysis.technical import TechnicalEngine
from .analysis.structure import StructureEngine
from .analysis.confluence import confluence_score as _confluence_score

# ------------------------------------------------------------------
# Inisialisasi
# ------------------------------------------------------------------

mcp     = FastMCP("Trading Analysis MCP — IDX · Forex · Crypto")
fetcher = DataFetcher()
tech    = TechnicalEngine()
struct  = StructureEngine(swing_n=3)

_DEFAULT_LIMIT = 250


# ==================================================================
# TOOLS
# ==================================================================

@mcp.tool()
def analyze_symbol(
    symbol: str,
    timeframe: str = "1d",
    limit: int = _DEFAULT_LIMIT,
) -> str:
    """
    Analisa lengkap satu simbol: technical indicators + market structure (S/R, BOS/CHoCH, OB, FVG).
    Ini adalah tool utama — gunakan ini sebagai titik awal sebelum tools lainnya.

    Args:
        symbol   : Simbol dalam format apapun. Contoh: BBCA.JK, EURUSD, BTC/USDT, XAUUSD
        timeframe: 1m / 5m / 15m / 30m / 1h / 4h / 1d / 1w  (default: 1d)
        limit    : Jumlah bar data (default: 250)

    Returns:
        Laporan analisa lengkap siap dibaca.
    """
    try:
        data         = fetcher.get(symbol, timeframe, limit)
        tech_result  = tech.calculate(data)
        struct_result = struct.analyze(data)
        score, reasons = _confluence_score(tech_result, struct_result)

        ind = tech_result.indicators
        current = ind.close

        lines = [
            f"{'='*52}",
            f"  ANALISA: {symbol.upper()} | {timeframe.upper()}",
            f"  Market: {data.market.value} | Harga: {current:,.5f}",
            f"{'='*52}",
            "",
            "--- STRUKTUR PASAR ---",
            f"Struktur  : {struct_result.market_structure}",
            f"EMA Stack : {ind.ema_stack} | Bias: {ind.trend_bias}",
        ]

        if struct_result.last_break:
            lines.append(f"Last Break: {struct_result.last_break}")

        lines += [
            "",
            "--- INDIKATOR TEKNIKAL ---",
            f"RSI    : {ind.rsi:.1f} [{ind.rsi_condition}]",
            f"MACD   : {ind.macd_cross} | hist {ind.macd_hist:+.5f}",
            f"BB     : {ind.bb_position} | width {ind.bb_width_pct:.1f}%",
            f"ATR    : {ind.atr:.5f} ({ind.atr_pct:.2f}% of price)",
            f"Volume : ratio {ind.vol_ratio:.2f}x {'[SPIKE]' if ind.vol_spike else ''}",
            "",
            "--- EMA ---",
            f"EMA8: {ind.ema8:,.5f}  EMA21: {ind.ema21:,.5f}",
            f"EMA50: {ind.ema50:,.5f}  EMA200: {ind.ema200:,.5f}",
        ]

        nearest = struct_result.nearest_levels(5)
        if nearest:
            lines += ["", "--- KEY LEVELS (terdekat) ---"]
            for lv in nearest:
                dist_pct = abs(lv.price - current) / current * 100
                lines.append(f"  {lv.kind:11s} {lv.price:,.5f}  [{lv.strength}] {dist_pct:.2f}% away")

        active_obs = struct_result.active_order_blocks[-3:]
        if active_obs:
            lines += ["", "--- ACTIVE ORDER BLOCKS ---"]
            for ob in active_obs:
                lines.append(f"  {ob}")

        open_fvgs = struct_result.open_fvgs[-3:]
        if open_fvgs:
            lines += ["", "--- OPEN FAIR VALUE GAPS ---"]
            for fvg in open_fvgs:
                lines.append(f"  {fvg}")

        strength_label = (
            "KUAT" if score >= 6
            else "CUKUP" if score >= 4
            else "LEMAH"
        )
        lines += [
            "",
            "--- CONFLUENCE SCORE ---",
            f"Score : {score}/8  [{strength_label}]",
        ]
        for r in reasons:
            lines.append(f"  + {r}")

        return "\n".join(lines)

    except Exception as e:
        return f"[ERROR] Gagal analisa {symbol}: {e}"


# ------------------------------------------------------------------

@mcp.tool()
def get_multi_timeframe_analysis(
    symbol: str,
    timeframes: str = "1d,4h,1h",
) -> str:
    """
    Analisa top-down untuk beberapa timeframe sekaligus.
    Ideal untuk konfirmasi bias dari HTF sebelum cari entry di LTF.

    Args:
        symbol    : Simbol. Contoh: EURUSD, BBCA.JK, BTC/USDT
        timeframes: Timeframe dipisah koma, dari besar ke kecil.
                    Contoh: "1d,4h,1h"  atau  "4h,1h,15m"
    """
    try:
        tf_list = [t.strip() for t in timeframes.split(",")]
        lines   = [
            f"{'='*52}",
            f"  MULTI-TIMEFRAME: {symbol.upper()}",
            f"  Timeframes: {' > '.join(tf_list)}",
            f"{'='*52}",
        ]

        summaries = []
        for tf in tf_list:
            try:
                data         = fetcher.get(symbol, tf, _DEFAULT_LIMIT)
                tech_result  = tech.calculate(data)
                struct_result = struct.analyze(data)
                ind          = tech_result.indicators
                score, _     = _confluence_score(tech_result, struct_result)
                last_b       = struct_result.last_break

                lines += [
                    "",
                    f"=== {tf.upper()} ===",
                    f"Struktur : {struct_result.market_structure} | EMA: {ind.ema_stack} | Bias: {ind.trend_bias}",
                    f"RSI      : {ind.rsi:.1f} [{ind.rsi_condition}]  |  MACD: {ind.macd_cross}",
                    f"BB       : {ind.bb_position}  |  ATR: {ind.atr:.5f} ({ind.atr_pct:.2f}%)",
                    f"Score    : {score}/8",
                ]

                if last_b:
                    lines.append(f"Last BOS/CHoCH: {last_b}")

                nearest = struct_result.nearest_levels(3)
                if nearest:
                    lines.append("Key levels:")
                    for lv in nearest:
                        lines.append(f"  {lv}")

                summaries.append({
                    "tf": tf,
                    "structure": struct_result.market_structure,
                    "bias": ind.trend_bias,
                    "score": score,
                })

            except Exception as e:
                lines.append(f"\n=== {tf.upper()} ===\n  [ERROR] {e}")

        # Sintesis HTF vs LTF
        if len(summaries) >= 2:
            lines += ["", "--- SINTESIS ---"]
            htf = summaries[0]
            ltf = summaries[-1]
            if htf["structure"] == ltf["structure"]:
                lines.append(f"Semua TF aligned: {htf['structure']} — setup kuat")
            elif htf["bias"] != ltf["bias"]:
                lines.append(
                    f"Divergence: {htf['tf']} {htf['structure']} vs {ltf['tf']} {ltf['structure']}"
                    " — tunggu konfirmasi sebelum entry"
                )
            else:
                lines.append(
                    f"HTF {htf['tf']} {htf['structure']} | "
                    f"LTF {ltf['tf']} lagi pullback — potensi entry dengan HTF bias"
                )

        return "\n".join(lines)

    except Exception as e:
        return f"[ERROR] Multi-timeframe gagal untuk {symbol}: {e}"


# ------------------------------------------------------------------

@mcp.tool()
def scan_setups(
    symbols: str,
    timeframe: str = "1d",
) -> str:
    """
    Scan beberapa simbol sekaligus, ranking berdasarkan confluence score.
    Berguna untuk menemukan simbol terbaik dari watchlist.

    Args:
        symbols  : Simbol dipisah koma. Contoh: "BBCA.JK,TLKM.JK,BMRI.JK"
                   atau "EURUSD,GBPUSD,USDJPY"  atau "BTC/USDT,ETH/USDT"
        timeframe: Timeframe yang dipakai untuk scan (default: 1d)
    """
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    results     = []

    lines = [
        f"{'='*52}",
        f"  SETUP SCANNER | {timeframe.upper()} | {len(symbol_list)} simbol",
        f"{'='*52}",
    ]

    for symbol in symbol_list:
        try:
            data          = fetcher.get(symbol, timeframe, _DEFAULT_LIMIT)
            tech_result   = tech.calculate(data)
            struct_result = struct.analyze(data)
            score, reasons = _confluence_score(tech_result, struct_result)
            ind           = tech_result.indicators

            results.append({
                "symbol":    symbol,
                "score":     score,
                "structure": struct_result.market_structure,
                "bias":      ind.trend_bias,
                "rsi":       ind.rsi,
                "rsi_cond":  ind.rsi_condition,
                "macd":      ind.macd_cross,
                "reasons":   reasons,
                "close":     ind.close,
            })
        except Exception as e:
            lines.append(f"  [SKIP] {symbol}: {e}")

    # Sort by score desc
    results.sort(key=lambda r: r["score"], reverse=True)

    lines += ["", "  Rank | Symbol          | Score | Struktur   | Bias     | RSI"]
    lines.append("  " + "-" * 64)

    for i, r in enumerate(results, 1):
        strength = "***" if r["score"] >= 6 else "**" if r["score"] >= 4 else "*"
        lines.append(
            f"  {i:2d}.  {r['symbol']:15s}  {r['score']}/8  {strength:3s}  "
            f"{r['structure']:10s}  {r['bias']:8s}  {r['rsi']:.1f} [{r['rsi_cond']}]"
        )

    # Detail untuk top 3
    if results:
        lines += ["", "--- TOP SETUP DETAIL ---"]
        for r in results[:3]:
            lines += [
                f"\n{r['symbol']} (score {r['score']}/8):",
                f"  Harga: {r['close']:,.5f} | {r['structure']} | {r['bias']}",
                f"  MACD: {r['macd']}",
            ]
            for reason in r["reasons"]:
                lines.append(f"  + {reason}")

    return "\n".join(lines)


# ------------------------------------------------------------------

@mcp.tool()
def calculate_rr(
    entry: float,
    stop_loss: float,
    take_profit: float,
    risk_amount: float = 0,
) -> str:
    """
    Hitung Risk/Reward ratio dan validasi setup.

    Args:
        entry       : Harga entry
        stop_loss   : Harga stop loss
        take_profit : Harga take profit (bisa lebih dari satu, pisah koma di luar)
        risk_amount : Modal yang di-risk dalam USD/IDR (opsional, untuk hitung lot size)
    """
    try:
        risk   = abs(entry - stop_loss)
        reward = abs(take_profit - entry)

        if risk == 0:
            return "[ERROR] Stop loss sama dengan entry"

        rr     = reward / risk
        direction = "LONG" if take_profit > entry else "SHORT"

        # Validasi arah
        if direction == "LONG" and stop_loss > entry:
            return "[ERROR] LONG setup: stop loss harus di bawah entry"
        if direction == "SHORT" and stop_loss < entry:
            return "[ERROR] SHORT setup: stop loss harus di atas entry"

        lines = [
            f"=== RISK / REWARD CALCULATOR ===",
            f"Arah       : {direction}",
            f"Entry      : {entry:,.5f}",
            f"Stop Loss  : {stop_loss:,.5f}  (risk: {risk:,.5f})",
            f"Take Profit: {take_profit:,.5f}  (reward: {reward:,.5f})",
            f"R/R Ratio  : 1 : {rr:.2f}",
            "",
            f"Evaluasi   : {'LAYAK (RR >= 2)' if rr >= 2 else 'KURANG IDEAL (RR < 2)'}",
        ]

        if risk_amount > 0:
            potential_profit = risk_amount * rr
            lines += [
                "",
                f"--- Proyeksi Modal ---",
                f"Risk   : {risk_amount:,.2f}",
                f"Profit : {potential_profit:,.2f}  (jika TP tercapai)",
            ]

        return "\n".join(lines)

    except Exception as e:
        return f"[ERROR] Gagal kalkulasi RR: {e}"


# ------------------------------------------------------------------

@mcp.tool()
def get_market_session() -> str:
    """
    Info sesi trading yang aktif saat ini dan pair/saham yang sebaiknya difokuskan.
    Selalu panggil tool ini sebelum analisa untuk tahu konteks waktu trading.
    """
    now_utc  = datetime.now(timezone.utc)
    hour_utc = now_utc.hour + now_utc.minute / 60

    sessions = []

    # Sydney: 22:00 - 07:00 UTC
    if hour_utc >= 22 or hour_utc < 7:
        sessions.append("Sydney")

    # Tokyo/Asia: 00:00 - 09:00 UTC
    if 0 <= hour_utc < 9:
        sessions.append("Tokyo/Asian")

    # IDX: 02:00 - 08:49 UTC (09:00-15:49 WIB)
    if 2 <= hour_utc < 8.82:
        sessions.append("IDX (Bursa Indonesia)")

    # London: 08:00 - 17:00 UTC
    if 8 <= hour_utc < 17:
        sessions.append("London")

    # New York: 13:00 - 22:00 UTC
    if 13 <= hour_utc < 22:
        sessions.append("New York")

    # Overlap London-NY (paling likuid)
    overlap = 13 <= hour_utc < 17

    # Rekomendasi pair per sesi
    focus = []
    if "IDX (Bursa Indonesia)" in sessions:
        focus.append("IDX: BBCA.JK, TLKM.JK, BMRI.JK, BBRI.JK, ASII.JK")
    if "Tokyo/Asian" in sessions:
        focus.append("Forex: JPY pairs (USDJPY, EURJPY, GBPJPY), AUD, NZD pairs")
    if "London" in sessions and "New York" not in sessions:
        focus.append("Forex: EUR, GBP pairs (EURUSD, GBPUSD, EURGBP)")
    if "New York" in sessions:
        focus.append("Forex: USD pairs semua, terutama EUR/USD & GBP/USD")
        focus.append("Crypto: BTC & ETH — volume tinggi sesi NY")
    if overlap:
        focus.append("[OVERLAP] London-NY: Volatilitas tertinggi hari ini!")

    wib_hour = (now_utc.hour + 7) % 24
    wib_time = f"{wib_hour:02d}:{now_utc.minute:02d} WIB"

    lines = [
        f"=== MARKET SESSION INFO ===",
        f"Waktu UTC  : {now_utc.strftime('%Y-%m-%d %H:%M')} UTC",
        f"Waktu WIB  : {wib_time}",
        "",
        f"Sesi Aktif : {', '.join(sessions) if sessions else 'Market sepi (weekend atau gap)'}",
        f"Overlap    : {'London-NY (paling likuid)' if overlap else 'Tidak ada overlap saat ini'}",
        "",
        "Fokus trading:",
    ]
    for f in focus:
        lines.append(f"  • {f}")

    if not sessions:
        lines.append("  • Market sepi, hindari entry baru")
        lines.append("  • Waktu baik untuk analisa dan persiapan")

    # Weekend check
    if now_utc.weekday() >= 5:  # Sabtu=5, Minggu=6
        lines += [
            "",
            "[INFO] Hari ini weekend — forex dan IDX TUTUP.",
            "Crypto tetap buka 24/7.",
        ]

    return "\n".join(lines)
