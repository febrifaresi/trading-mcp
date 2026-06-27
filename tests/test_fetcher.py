"""
Jalankan dari root project:
    pip install -r requirements.txt
    python -m tests.test_fetcher
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading_mcp import DataFetcher
from trading_mcp.utils.symbol import detect_market, normalize_symbol


def test_symbol_detection():
    print("\n=== Symbol Detection ===")
    cases = [
        ("BBCA.JK",  "IDX"),
        ("BBCA",     "IDX"),
        ("TLKM.JK",  "IDX"),
        ("EURUSD",   "FOREX"),
        ("EUR/USD",  "FOREX"),
        ("XAUUSD",   "FOREX"),
        ("GBPJPY",   "FOREX"),
        ("BTC/USDT", "CRYPTO"),
        ("BTCUSDT",  "CRYPTO"),
        ("ETHUSDT",  "CRYPTO"),
        ("SOL/USDT", "CRYPTO"),
    ]
    all_pass = True
    for symbol, expected in cases:
        result = detect_market(symbol).value
        status = "OK" if result == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {symbol:12s} -> {result} (expected: {expected})")
    return all_pass


def test_fetch_idx():
    print("\n=== IDX: BBCA.JK Daily ===")
    fetcher = DataFetcher()
    data = fetcher.get("BBCA.JK", "1d", limit=10)
    print(f"  {data}")
    print(f"  5 bar terakhir:\n{data.df.tail(5)[['open','high','low','close','volume']].to_string()}")
    return True


def test_fetch_forex():
    print("\n=== FOREX: EURUSD H4 ===")
    fetcher = DataFetcher()
    data = fetcher.get("EURUSD", "4h", limit=10)
    print(f"  {data}")
    print(f"  5 bar terakhir:\n{data.df.tail(5)[['open','high','low','close']].to_string()}")
    return True


def test_fetch_crypto():
    print("\n=== CRYPTO: BTC/USDT H1 ===")
    fetcher = DataFetcher()
    data = fetcher.get("BTC/USDT", "1h", limit=10)
    print(f"  {data}")
    print(f"  5 bar terakhir:\n{data.df.tail(5)[['open','high','low','close','volume']].to_string()}")
    return True


def test_multi_timeframe():
    print("\n=== Multi-Timeframe: EURUSD (D1, H4, H1) ===")
    fetcher = DataFetcher()
    mtf = fetcher.get_multi_timeframe("EURUSD", ["1d", "4h", "1h"], limit=5)
    for tf, data in mtf.items():
        print(f"  {tf}: {data.bar_count} bars | last close = {data.latest_close:.5f}")
    return True


def test_cache():
    print("\n=== Cache Test ===")
    fetcher = DataFetcher()
    # First fetch
    fetcher.get("BBCA.JK", "1d", limit=5)
    size_after_first = fetcher.cache_size
    # Second fetch (should hit cache)
    fetcher.get("BBCA.JK", "1d", limit=5)
    size_after_second = fetcher.cache_size
    hit = size_after_first == size_after_second
    print(f"  Cache size: {size_after_first} | Cache hit: {'YES' if hit else 'NO'}")
    return hit


if __name__ == "__main__":
    print("=" * 50)
    print("  Trading MCP — Data Fetcher Test")
    print("=" * 50)

    results = []
    results.append(("Symbol Detection", test_symbol_detection()))

    try:
        results.append(("IDX Fetch",        test_fetch_idx()))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append(("IDX Fetch", False))

    try:
        results.append(("Forex Fetch",      test_fetch_forex()))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append(("Forex Fetch", False))

    try:
        results.append(("Crypto Fetch",     test_fetch_crypto()))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append(("Crypto Fetch", False))

    try:
        results.append(("Multi-Timeframe",  test_multi_timeframe()))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append(("Multi-Timeframe", False))

    try:
        results.append(("Cache",            test_cache()))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append(("Cache", False))

    print("\n" + "=" * 50)
    print("  HASIL")
    print("=" * 50)
    for name, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    total = sum(1 for _, p in results if p)
    print(f"\n  {total}/{len(results)} tests passed")
