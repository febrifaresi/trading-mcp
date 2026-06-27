"""
Trading Analysis MCP Server — entry point.

Cara run:
    python server.py

Cara daftarkan ke Claude Desktop:
    Lihat README.md bagian "Configuration"
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_mcp.mcp_server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
