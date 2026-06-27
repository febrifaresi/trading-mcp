"""
python -m tests.test_mcp_tools
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading_mcp.mcp_server import (
    analyze_symbol,
    get_multi_timeframe_analysis,
    scan_setups,
    calculate_rr,
    get_market_session,
)


def test_analyze_idx():
    print("\n=== analyze_symbol: BBCA.JK D1 ===")
    result = analyze_symbol("BBCA.JK", "1d")
    print(result)
    assert "ANALISA" in result
    assert "CONFLUENCE" in result
    assert "[ERROR]" not in result
    return True


def test_analyze_forex():
    print("\n=== analyze_symbol: EURUSD H4 ===")
    result = analyze_symbol("EURUSD", "4h")
    print(result)
    assert "ANALISA" in result
    assert "[ERROR]" not in result
    return True


def test_multi_timeframe():
    print("\n=== get_multi_timeframe_analysis: XAUUSD ===")
    result = get_multi_timeframe_analysis("XAUUSD", "1d,4h,1h")
    print(result)
    assert "MULTI-TIMEFRAME" in result
    assert "1D" in result.upper() and "4H" in result.upper()
    return True


def test_scan_setups():
    print("\n=== scan_setups: Forex majors ===")
    result = scan_setups("EURUSD,GBPUSD,USDJPY,XAUUSD", "1d")
    print(result)
    assert "SCANNER" in result
    assert "Score" in result or "score" in result
    return True


def test_calculate_rr():
    print("\n=== calculate_rr ===")

    # Test LONG valid
    r1 = calculate_rr(1.1000, 1.0950, 1.1100)
    print(r1)
    assert "LONG" in r1
    assert "2.00" in r1   # RR = (1.1100-1.1000) / (1.1000-1.0950) = 100/50 = 2.0

    # Test SHORT
    r2 = calculate_rr(1.1000, 1.1060, 1.0940)
    print(r2)
    assert "SHORT" in r2

    # Test dengan risk_amount
    r3 = calculate_rr(1.1000, 1.0950, 1.1200, risk_amount=100)
    print(r3)
    assert "Modal" in r3 or "Proyeksi" in r3

    return True


def test_market_session():
    print("\n=== get_market_session ===")
    result = get_market_session()
    print(result)
    assert "SESSION" in result.upper()
    assert "WIB" in result
    assert "UTC" in result
    return True


def test_error_handling():
    print("\n=== Error Handling: simbol invalid ===")
    result = analyze_symbol("INVALID_SYMBOL_XYZ_123", "1d")
    print(result)
    assert "[ERROR]" in result
    return True


if __name__ == "__main__":
    print("=" * 54)
    print("  Trading MCP — MCP Tools Layer Test")
    print("=" * 54)

    tests = [
        ("analyze_symbol IDX",      test_analyze_idx),
        ("analyze_symbol Forex",    test_analyze_forex),
        ("multi_timeframe",         test_multi_timeframe),
        ("scan_setups",             test_scan_setups),
        ("calculate_rr",            test_calculate_rr),
        ("market_session",          test_market_session),
        ("error_handling",          test_error_handling),
    ]

    results = []
    for name, fn in tests:
        try:
            passed = fn()
            results.append((name, passed))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((name, False))

    print("\n" + "=" * 54)
    print("  HASIL")
    print("=" * 54)
    for name, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    total = sum(1 for _, p in results if p)
    print(f"\n  {total}/{len(tests)} tests passed")
