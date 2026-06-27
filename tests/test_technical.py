"""
Jalankan dari root project:
    python -m tests.test_technical
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading_mcp import DataFetcher, TechnicalEngine


fetcher = DataFetcher()
engine  = TechnicalEngine()


def test_idx_technical():
    print("\n=== IDX: BBCA.JK Daily ===")
    data   = fetcher.get("BBCA.JK", "1d", limit=250)
    result = engine.calculate(data)
    print(result)
    ind = result.indicators
    assert ind.rsi > 0,      "RSI harus > 0"
    assert ind.atr > 0,      "ATR harus > 0"
    assert ind.ema50 > 0,    "EMA50 harus > 0"
    assert ind.trend_bias in {"BULLISH", "BEARISH", "NEUTRAL"}
    print(f"\n  Detail: {ind.to_dict()}")
    return True


def test_forex_technical():
    print("\n=== FOREX: EURUSD H4 ===")
    data   = fetcher.get("EURUSD", "4h", limit=250)
    result = engine.calculate(data)
    print(result)
    ind = result.indicators
    assert 0 < ind.rsi < 100, "RSI harus 0-100"
    assert ind.atr > 0,       "ATR harus > 0"
    assert ind.bb_upper > ind.bb_lower, "BB upper harus > lower"
    return True


def test_ema_stack():
    print("\n=== EMA Stack Logic ===")
    data   = fetcher.get("EURUSD", "1d", limit=250)
    result = engine.calculate(data)
    ind    = result.indicators

    # EMA stack harus salah satu dari nilai valid
    assert ind.ema_stack in {"FULL_BULL", "FULL_BEAR", "MIXED"}, \
        f"EMA stack tidak valid: {ind.ema_stack}"

    # Verifikasi konsistensi: jika FULL_BULL, EMA8 harus > EMA200
    if ind.ema_stack == "FULL_BULL":
        assert ind.ema8 > ind.ema200, "FULL_BULL tapi EMA8 < EMA200?"
    if ind.ema_stack == "FULL_BEAR":
        assert ind.ema8 < ind.ema200, "FULL_BEAR tapi EMA8 > EMA200?"

    print(f"  EMA8={ind.ema8:.5f} | EMA21={ind.ema21:.5f} | "
          f"EMA50={ind.ema50:.5f} | EMA200={ind.ema200:.5f}")
    print(f"  Stack: {ind.ema_stack} | Bias: {ind.trend_bias}")
    return True


def test_rsi_condition():
    print("\n=== RSI Condition Mapping ===")
    data   = fetcher.get("BBCA.JK", "1d", limit=250)
    result = engine.calculate(data)
    ind    = result.indicators

    rsi = ind.rsi
    cond = ind.rsi_condition
    if rsi >= 70:
        assert cond == "OVERBOUGHT", f"RSI {rsi} harusnya OVERBOUGHT, dapat {cond}"
    elif rsi <= 30:
        assert cond == "OVERSOLD",   f"RSI {rsi} harusnya OVERSOLD, dapat {cond}"
    else:
        assert cond == "NEUTRAL",    f"RSI {rsi} harusnya NEUTRAL, dapat {cond}"

    print(f"  RSI: {rsi:.1f} -> {cond}  [OK]")
    return True


def test_df_columns():
    print("\n=== DataFrame Columns ===")
    data   = fetcher.get("EURUSD", "1d", limit=250)
    result = engine.calculate(data)
    df     = result.df

    expected_cols = [
        "open", "high", "low", "close", "volume",
        "ema8", "ema21", "ema50", "ema200",
        "rsi", "macd", "macd_hist", "macd_signal",
        "bb_upper", "bb_mid", "bb_lower",
        "atr", "vol_ma20", "vol_ratio",
    ]
    missing = [c for c in expected_cols if c not in df.columns]
    assert not missing, f"Kolom tidak ada: {missing}"

    print(f"  Semua {len(expected_cols)} kolom tersedia di DataFrame")
    print(f"  Shape: {df.shape}")
    return True


def test_multi_timeframe_technical():
    print("\n=== Multi-Timeframe: XAUUSD ===")
    mtf = fetcher.get_multi_timeframe("XAUUSD", ["1d", "4h", "1h"], limit=250)
    for tf, data in mtf.items():
        result = engine.calculate(data)
        ind = result.indicators
        print(f"  {tf:3s} | Bias: {ind.trend_bias:8s} | "
              f"RSI: {ind.rsi:5.1f} | MACD: {ind.macd_cross}")
    return True


if __name__ == "__main__":
    print("=" * 52)
    print("  Trading MCP — Technical Engine Test")
    print("=" * 52)

    tests = [
        ("IDX Technical",        test_idx_technical),
        ("Forex Technical",       test_forex_technical),
        ("EMA Stack Logic",       test_ema_stack),
        ("RSI Condition",         test_rsi_condition),
        ("DataFrame Columns",     test_df_columns),
        ("Multi-TF Technical",    test_multi_timeframe_technical),
    ]

    results = []
    for name, fn in tests:
        try:
            passed = fn()
            results.append((name, passed))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((name, False))

    print("\n" + "=" * 52)
    print("  HASIL")
    print("=" * 52)
    for name, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    total = sum(1 for _, p in results if p)
    print(f"\n  {total}/{len(results)} tests passed")
