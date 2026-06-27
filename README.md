# Trading Analysis MCP

An MCP (Model Context Protocol) server that gives Claude the ability to analyze trading setups across **IDX (Indonesian stocks)**, **Forex**, and **Crypto** markets — without executing any trades.

Claude acts as your analyst: fetching live market data, calculating technical indicators, detecting market structure, and scoring setups by confluence. You make the final call.

---

## What Claude can do with this MCP

| Prompt example | Tool used |
|---|---|
| *"Analyze BBCA.JK on the daily chart"* | `analyze_symbol` |
| *"What's the multi-timeframe bias for EURUSD?"* | `get_multi_timeframe_analysis` |
| *"Scan EURUSD, GBPUSD, USDJPY — find the best setup"* | `scan_setups` |
| *"Calculate RR: entry 1.1000, SL 1.0950, TP 1.1200"* | `calculate_rr` |
| *"What trading session is active right now?"* | `get_market_session` |

Each analysis includes: **EMA stack**, **RSI**, **MACD**, **Bollinger Bands**, **ATR**, **Support/Resistance**, **BOS/CHoCH**, **Order Blocks**, **Fair Value Gaps**, and a **confluence score (0–8)**.

---

## Requirements

- Python 3.10+
- Claude Desktop (for local MCP)
- Internet connection (for live market data)

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/trading-mcp.git
cd trading-mcp
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Claude Desktop

Find your Claude Desktop config file:

| OS | Path |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

Add this entry (replace the path with your actual clone location):

**Windows:**
```json
{
  "mcpServers": {
    "trading-analysis": {
      "command": "python",
      "args": ["C:/path/to/trading-mcp/server.py"]
    }
  }
}
```

**macOS / Linux:**
```json
{
  "mcpServers": {
    "trading-analysis": {
      "command": "python3",
      "args": ["/path/to/trading-mcp/server.py"]
    }
  }
}
```

### 4. Restart Claude Desktop

The tools are now available. Try asking Claude:
> *"Scan EURUSD, GBPUSD, USDJPY for the best setup today"*

---

## Available MCP Tools

### `analyze_symbol`
Full technical + structure analysis for a single symbol.

```
Parameters:
  symbol     — e.g. BBCA.JK, EURUSD, BTC/USDT, XAUUSD
  timeframe  — 1m / 5m / 15m / 30m / 1h / 4h / 1d / 1w  (default: 1d)
  limit      — number of bars to load (default: 250)
```

Output includes: market structure, EMA stack, RSI, MACD, Bollinger Bands, ATR, volume ratio, key S/R levels, active Order Blocks, open Fair Value Gaps, and confluence score.

---

### `get_multi_timeframe_analysis`
Top-down analysis across multiple timeframes to confirm bias before entry.

```
Parameters:
  symbol     — e.g. EURUSD
  timeframes — comma-separated, large to small (default: "1d,4h,1h")
```

Output includes per-timeframe summary + HTF vs LTF synthesis.

---

### `scan_setups`
Scan a watchlist and rank symbols by confluence score.

```
Parameters:
  symbols    — comma-separated, e.g. "BBCA.JK,TLKM.JK,BMRI.JK"
  timeframe  — timeframe to scan (default: 1d)
```

Output: ranked table (score, structure, bias, RSI) + detailed breakdown of top 3.

---

### `calculate_rr`
Risk/Reward calculator with trade direction validation.

```
Parameters:
  entry        — entry price
  stop_loss    — stop loss price
  take_profit  — take profit price
  risk_amount  — (optional) capital at risk in USD/IDR for profit projection
```

---

### `get_market_session`
Current trading session info and which instruments to focus on.

Output: active sessions (Asian/London/NY/IDX), overlap status, recommended pairs.

---

## Supported Symbols

| Market | Format | Examples |
|---|---|---|
| IDX (Indonesian stocks) | `TICKER.JK` | `BBCA.JK`, `TLKM.JK`, `BMRI.JK` |
| Forex | `PAIR` or `BASE/QUOTE` | `EURUSD`, `XAUUSD`, `GBP/USD` |
| Crypto | `BASE/QUOTE` | `BTC/USDT`, `ETH/USDT`, `SOL/USDT` |

**Auto-detection**: just type the symbol in any format — the server detects the market automatically.

---

## Data Sources

| Market | Primary | Fallback |
|---|---|---|
| IDX | yfinance | — |
| Forex | yfinance | — |
| Crypto | Bybit → OKX → KuCoin → Gate.io | yfinance (BTC-USD) |

No API keys required for basic usage. All data is read-only.

---

## Analysis Concepts

This server implements **SMC (Smart Money Concepts) / ICT** principles algorithmically:

- **Swing High/Low** — pivot detection with configurable lookback
- **BOS (Break of Structure)** — trend continuation confirmation
- **CHoCH (Change of Character)** — trend reversal signal
- **Order Blocks** — institutional supply/demand zones
- **Fair Value Gaps** — price imbalances that tend to get filled

Combined with classic technical indicators (EMA stack, RSI, MACD, Bollinger Bands, ATR) to produce a **confluence score (0–8)**.

---

## Architecture

```
Claude Desktop
    │
    └─ MCP (stdio)
         │
         └─ Trading Analysis MCP Server
               ├── DataFetcher
               │     ├── yfinance  → IDX + Forex (+ crypto fallback)
               │     └── ccxt      → Crypto (Bybit, OKX, KuCoin, Gate.io)
               │
               ├── TechnicalEngine  (pandas-ta)
               │     └── EMA 8/21/50/200 · RSI · MACD · BB · ATR · Volume
               │
               └── StructureEngine  (SMC/ICT)
                     └── Swings · S/R · BOS/CHoCH · Order Blocks · FVG
```

---

## Option B — Remote MCP (Hosted on Railway)

Deploy once, share a URL. Others connect without installing Python.

### 1. Deploy to Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com)

1. Go to [railway.app](https://railway.app) and create a new project
2. Click **Deploy from GitHub repo** → select `trading-mcp`
3. Railway auto-detects `railway.toml` and starts `server_remote.py`

### 2. Set environment variables

In your Railway project → **Variables** tab, add:

```
API_KEYS=your_secret_key_here
```

Generate a secure key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

You can add multiple keys separated by commas: `key1,key2,key3`

Optional:
```
RATE_LIMIT_PER_MIN=20
```

### 3. Get your URL

After deploy, Railway gives you a URL like:
```
https://trading-mcp-production.up.railway.app
```

Health check: `GET /health` — should return `{"status": "ok", ...}`

### 4. Connect from Claude Desktop

```json
{
  "mcpServers": {
    "trading-analysis": {
      "type": "http",
      "url": "https://your-app.up.railway.app/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

Share the URL and API key with anyone — no Python installation needed on their end.

---

## Running Tests

```bash
python -m tests.test_fetcher
python -m tests.test_technical
python -m tests.test_structure
python -m tests.test_mcp_tools
```

---

## License

MIT — free to use, modify, and share.
