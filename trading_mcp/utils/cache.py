import time
from typing import Any, Optional


class TTLCache:
    """
    In-memory cache dengan TTL per entry.
    Thread-safe untuk single-process (GIL Python cukup di sini).
    """

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def _make_key(self, symbol: str, timeframe: str, limit: int) -> str:
        return f"{symbol}::{timeframe}::{limit}"

    def get(self, symbol: str, timeframe: str, limit: int) -> Optional[Any]:
        key = self._make_key(symbol, timeframe, limit)
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, symbol: str, timeframe: str, limit: int, value: Any, ttl: int):
        key = self._make_key(symbol, timeframe, limit)
        self._store[key] = (value, time.time() + ttl)

    def invalidate(self, symbol: str):
        """Hapus semua cache entries untuk simbol tertentu."""
        keys_to_delete = [k for k in self._store if k.startswith(f"{symbol}::")]
        for k in keys_to_delete:
            del self._store[k]

    def clear(self):
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)
