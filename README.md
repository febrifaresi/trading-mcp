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

## ⚠️ Automation (eksekusi order sungguhan)

Selain MCP server (analisa saja, tidak pernah eksekusi), repo ini juga punya
**automation bot** (`run_bot.py`) yang bisa scan pasar dan **mengirim order
sungguhan ke Bybit secara otonom** — tanpa perlu kamu di depan chat.

**Ini menyentuh uang asli. Baca bagian ini sebelum menyalakan apa pun.**

### Default-nya aman

- `TRADING_MODE=dry_run` — bot jalan penuh (fetch data, hitung sinyal, "eksekusi"),
  tapi order **tidak pernah** benar-benar dikirim ke exchange. Semua disimulasikan
  dan dicatat ke `trade_log.jsonl` persis seperti kalau live, supaya kamu bisa
  evaluasi strategi dulu sebelum pakai uang sungguhan.
- `BYBIT_TESTNET=true` — kalaupun kamu isi API key, defaultnya tetap testnet
  (uang virtual Bybit), bukan akun sungguhan.
- Spot only, long only — tidak ada leverage/margin/futures. Short tidak mungkin
  di spot, jadi sinyal bearish hanya memicu **exit** posisi yang sudah ada, bukan short baru.

Untuk benar-benar live: set `TRADING_MODE=live`, `BYBIT_TESTNET=false`, dan isi
`BYBIT_API_KEY`/`BYBIT_API_SECRET` di `.env`. Bot akan menolak jalan (raise error di startup)
kalau kombinasi env-nya kontradiktif (misal `TRADING_MODE=live` tapi testnet masih `true`,
atau live tapi API key kosong).

### Risk control yang selalu aktif (tidak bisa dimatikan dari sinyal)

| Kontrol | Env var | Default |
|---|---|---|
| Max ukuran posisi per trade | `MAX_POSITION_USD` | $50 |
| Circuit breaker rugi harian | `MAX_DAILY_LOSS_USD` | $25 — begitu tercapai, entry baru diblokir otomatis sampai hari UTC berikutnya |
| Max posisi terbuka bersamaan | `MAX_OPEN_POSITIONS` | 3 |
| Risk per trade (dari balance) | `RISK_PER_TRADE_PCT` | 1% |
| Minimum confluence score untuk entry | `MIN_CONFLUENCE_SCORE` | 6/8 |

Semua posisi pakai stop-loss & take-profit berbasis ATR (`ATR_STOP_MULTIPLIER`,
`ATR_TARGET_MULTIPLIER`) yang dihitung otomatis saat entry — bukan opsional.

### Kill switch

```bash
touch KILL_SWITCH
```

Begitu file `KILL_SWITCH` ada di root project, bot **langsung berhenti membuka
posisi baru** pada putaran berikutnya (polling, bukan instan — tunggu sampai
`POLL_INTERVAL_SECONDS` berlalu). Posisi yang sudah terbuka tetap dikelola
(stop-loss/take-profit tetap bisa jalan) supaya modal yang sudah di pasar tidak
dibiarkan tanpa pengaman. Hapus file itu untuk melanjutkan.

```bash
rm KILL_SWITCH   # lanjutkan bot
```

### Jalankan

```bash
python run_bot.py
```

Semua keputusan (sinyal masuk, kena risk limit, order terkirim, posisi ditutup)
dicatat satu baris JSON per event ke `trade_log.jsonl` — termasuk yang **ditolak**
oleh risk manager, supaya ada jejak audit lengkap baik di dry_run maupun live.

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
               ├── StructureEngine  (SMC/ICT)
               │     └── Swings · S/R · BOS/CHoCH · Order Blocks · FVG
               │
               └── confluence_score()  — dipakai ulang oleh automation bot

run_bot.py  (automation — eksekusi order sungguhan, terpisah dari MCP server)
    │
    └─ AutomationBot (loop polling per watchlist)
          ├── SignalGenerator    → reuse TechnicalEngine + StructureEngine + confluence_score
          ├── RiskManager        → kill switch, circuit breaker, position sizing, state (JSON)
          ├── OrderExecutor      → risk check → (dry_run: simulasi | live: ccxt order)
          ├── ExchangeClient     → wrapper ccxt.bybit (testnet toggle)
          └── TradeLogger        → audit log JSONL (trade_log.jsonl)
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Atau per file:

```bash
python -m tests.test_fetcher
python -m tests.test_technical
python -m tests.test_structure
python -m tests.test_mcp_tools
python -m pytest tests/test_risk_manager.py tests/test_order_executor.py
```

---

## License

MIT — free to use, modify, and share.
