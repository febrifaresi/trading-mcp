"""
Remote MCP Server — HTTP/SSE transport untuk Railway deployment.
Orang lain connect via URL tanpa perlu install Python.

Environment variables:
  PORT              Port yang dipakai (Railway set otomatis)
  API_KEYS          Kunci akses dipisah koma: "key1,key2,key3"
  RATE_LIMIT_PER_MIN  Max request per menit per API key (default: 20)

Cara run lokal untuk test:
  API_KEYS=testkey python server_remote.py

Cara connect dari Claude Desktop:
  {
    "mcpServers": {
      "trading-analysis": {
        "type": "http",
        "url": "https://your-app.up.railway.app/mcp",
        "headers": { "Authorization": "Bearer YOUR_API_KEY" }
      }
    }
  }
"""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from trading_mcp.mcp_server import mcp

# ------------------------------------------------------------------
# Config dari environment
# ------------------------------------------------------------------

PORT      = int(os.environ.get("PORT", 8000))
HOST      = os.environ.get("HOST", "0.0.0.0")
API_KEYS  = {k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()}
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MIN", "20"))

# ------------------------------------------------------------------
# Rate limiter — sliding window per API key (in-memory)
# ------------------------------------------------------------------

_call_windows: dict[str, list[float]] = defaultdict(list)


def _is_rate_limited(api_key: str) -> bool:
    now = time.monotonic()
    wins = _call_windows[api_key]
    # Buang entri yang sudah lebih dari 60 detik
    _call_windows[api_key] = [t for t in wins if now - t < 60]
    if len(_call_windows[api_key]) >= RATE_LIMIT:
        return True
    _call_windows[api_key].append(now)
    return False


# ------------------------------------------------------------------
# Auth + rate-limit middleware
# ------------------------------------------------------------------

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Cek Bearer token sebelum request masuk ke MCP tools.
    Path /health dan / dikecualikan (tidak perlu auth).
    Kalau API_KEYS env var tidak di-set, server terbuka (dev mode).
    """

    async def dispatch(self, request: Request, call_next):
        # Endpoint yang bebas auth
        if request.url.path in ("/health", "/"):
            return await call_next(request)

        # Dev mode — tidak ada API_KEYS yang dikonfigurasi
        if not API_KEYS:
            return await call_next(request)

        # Cek header
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(
                {"error": "Authorization header wajib ada. Format: Bearer YOUR_API_KEY"},
                status_code=401,
            )

        api_key = auth[7:].strip()
        if api_key not in API_KEYS:
            return JSONResponse(
                {"error": "API key tidak valid"},
                status_code=401,
            )

        if _is_rate_limited(api_key):
            return JSONResponse(
                {"error": f"Rate limit tercapai ({RATE_LIMIT} request/menit). Tunggu sebentar."},
                status_code=429,
            )

        return await call_next(request)


# ------------------------------------------------------------------
# Health endpoint — untuk Railway healthcheck + monitoring
# ------------------------------------------------------------------

@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({
        "status":        "ok",
        "service":       "Trading Analysis MCP",
        "version":       "1.0.0",
        "markets":       ["IDX", "Forex", "Crypto"],
        "tools":         ["analyze_symbol", "get_multi_timeframe_analysis",
                          "scan_setups", "calculate_rr", "get_market_session"],
        "auth_required": bool(API_KEYS),
        "rate_limit":    f"{RATE_LIMIT} req/min per key",
    })


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    auth_status = (
        f"ENABLED — {len(API_KEYS)} key(s) configured"
        if API_KEYS
        else "DISABLED (set API_KEYS env var sebelum deploy ke production)"
    )

    print("=" * 54)
    print("  Trading Analysis MCP — Remote Server")
    print("=" * 54)
    print(f"  Host       : {HOST}:{PORT}")
    print(f"  MCP URL    : http://{HOST}:{PORT}/mcp")
    print(f"  Health     : http://{HOST}:{PORT}/health")
    print(f"  Auth       : {auth_status}")
    print(f"  Rate limit : {RATE_LIMIT} req/min per key")
    print("=" * 54)

    mcp.add_middleware(Middleware(AuthMiddleware))
    app = mcp.http_app(path="/mcp")
    uvicorn.run(app, host=HOST, port=PORT)
