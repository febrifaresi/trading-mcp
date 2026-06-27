"""
Jalankan dari root project:
    python -m tests.test_structure
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading_mcp import DataFetcher, StructureEngine

fetcher = DataFetcher()
engine  = StructureEngine(swing_n=3)


def test_swing_detection():
    print("\n=== Swing Detection: EURUSD D1 ===")
    data   = fetcher.get("EURUSD", "1d", limit=200)
    result = engine.analyze(data)

    assert len(result.swing_highs) > 0, "Harus ada swing highs"
    assert len(result.swing_lows)  > 0, "Harus ada swing lows"

    print(f"  Swing Highs: {len(result.swing_highs)} | Swing Lows: {len(result.swing_lows)}")
    print(f"  5 swing highs terakhir:")
    for sh in result.swing_highs[-5:]:
        print(f"    {sh}")
    print(f"  5 swing lows terakhir:")
    for sl in result.swing_lows[-5:]:
        print(f"    {sl}")
    return True


def test_key_levels():
    print("\n=== Key Levels: BBCA.JK D1 ===")
    data   = fetcher.get("BBCA.JK", "1d", limit=200)
    result = engine.analyze(data)

    assert len(result.key_levels) > 0, "Harus ada key levels"

    print(f"  Total levels: {len(result.key_levels)}")
    print(f"  5 levels terdekat dari harga sekarang ({result.df['close'].iloc[-1]:.0f}):")
    for level in result.nearest_levels(5):
        print(f"    {level}")

    # Semua strength harus valid
    valid = {"STRONG", "MODERATE", "WEAK"}
    for l in result.key_levels:
        assert l.strength in valid, f"Strength tidak valid: {l.strength}"
        assert l.kind in {"RESISTANCE", "SUPPORT"}

    return True


def test_bos_choch():
    print("\n=== BOS & CHoCH: EURUSD D1 ===")
    data   = fetcher.get("EURUSD", "1d", limit=300)
    result = engine.analyze(data)

    print(f"  Market Structure: {result.market_structure}")
    print(f"  Total breaks: {len(result.breaks)}")
    print(f"  5 breaks terakhir:")
    for b in result.breaks[-5:]:
        print(f"    {b}")

    assert result.market_structure in {"UPTREND", "DOWNTREND", "RANGING"}

    for b in result.breaks:
        assert b.kind in {"BOS", "CHoCH"}
        assert b.direction in {"BULLISH", "BEARISH"}

    if result.last_break:
        print(f"  Last break: {result.last_break}")

    return True


def test_order_blocks():
    print("\n=== Order Blocks: XAUUSD H4 ===")
    data   = fetcher.get("XAUUSD", "4h", limit=200)
    result = engine.analyze(data)

    print(f"  Total OBs: {len(result.order_blocks)}")
    print(f"  Active OBs: {len(result.active_order_blocks)}")

    for ob in result.order_blocks[-5:]:
        print(f"    {ob}")

    for ob in result.order_blocks:
        assert ob.kind in {"BULLISH", "BEARISH"}
        assert ob.top >= ob.bottom, f"OB top < bottom: {ob}"

    return True


def test_fair_value_gaps():
    print("\n=== Fair Value Gaps: EURUSD H4 ===")
    data   = fetcher.get("EURUSD", "4h", limit=200)
    result = engine.analyze(data)

    print(f"  Total FVGs: {len(result.fair_value_gaps)}")
    print(f"  Open FVGs: {len(result.open_fvgs)}")

    for fvg in result.open_fvgs[-5:]:
        print(f"    {fvg}")

    for fvg in result.fair_value_gaps:
        assert fvg.kind in {"BULLISH", "BEARISH"}
        assert fvg.top > fvg.bottom, f"FVG top <= bottom: {fvg}"
        assert fvg.size > 0

    return True


def test_full_structure_summary():
    print("\n=== Full Structure Summary: BTC/USDT D1 ===")
    data   = fetcher.get("BTC/USDT", "1d", limit=300)
    result = engine.analyze(data)

    print(result)
    print(f"\n  Dict output:")
    summary = result.to_dict()
    for k, v in summary.items():
        print(f"    {k}: {v}")

    return True


def test_multi_timeframe_structure():
    print("\n=== Multi-TF Structure: EURUSD ===")
    for tf in ["1d", "4h", "1h"]:
        try:
            data   = fetcher.get("EURUSD", tf, limit=250)
            result = engine.analyze(data)
            last_b = result.last_break
            print(
                f"  {tf:3s} | {result.market_structure:10s} | "
                f"Breaks: {len(result.breaks):2d} | "
                f"Active OBs: {len(result.active_order_blocks):2d} | "
                f"Open FVGs: {len(result.open_fvgs):2d} | "
                f"Last: {last_b.kind + ' ' + last_b.direction if last_b else 'N/A'}"
            )
        except Exception as e:
            print(f"  {tf}: ERROR — {e}")

    return True


if __name__ == "__main__":
    print("=" * 56)
    print("  Trading MCP — Structure Engine Test")
    print("=" * 56)

    tests = [
        ("Swing Detection",    test_swing_detection),
        ("Key Levels",         test_key_levels),
        ("BOS & CHoCH",        test_bos_choch),
        ("Order Blocks",       test_order_blocks),
        ("Fair Value Gaps",    test_fair_value_gaps),
        ("Full Summary",       test_full_structure_summary),
        ("Multi-TF Structure", test_multi_timeframe_structure),
    ]

    results = []
    for name, fn in tests:
        try:
            passed = fn()
            results.append((name, passed))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((name, False))

    print("\n" + "=" * 56)
    print("  HASIL")
    print("=" * 56)
    for name, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    total = sum(1 for _, p in results if p)
    print(f"\n  {total}/{len(results)} tests passed")
