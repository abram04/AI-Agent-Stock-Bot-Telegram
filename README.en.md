# Stock Analysis Bot

A multi-agent Telegram bot that analyzes stocks in parallel using 5 AI agents, each with a distinct investment philosophy. Supports both Indonesian (IDX) and US (NYSE/NASDAQ) stocks.

## Features

- **5 Parallel Agents** — every stock is analyzed simultaneously by 5 unique perspectives
- **Up to 10 stocks at once** — all processed in parallel via `asyncio`
- **1-year price chart** — sent as a photo to Telegram (MA20, MA50, volume bars)
- **Technical indicators** — RSI, MACD, Moving Averages 20/50/200
- **DCF Valuation** — automatic intrinsic value calculation + margin of safety
- **1-hour caching** — same ticker is not re-fetched within the same hour
- **Realtime progress** — step-by-step status updates in Telegram
- **Comparison table** — BUY/HOLD/SELL summary when analyzing multiple stocks
- **Bilingual** — auto-detects Bahasa Indonesia or English from user message
- **LangSmith tracing** — full observability for every run

## The 5 Investment Agents

| Agent | Philosophy | Focus |
|-------|-----------|-------|
| 🎩 Warren Buffett | Value investing | Moat, ROE, FCF, long-term earnings power |
| 🧮 Joel Greenblatt | Magic Formula | Earnings yield + Return on capital |
| 📚 Benjamin Graham | Defensive value | Margin of safety, Graham Number, NCAV |
| 👔 25-Year Veteran | Battle-tested experience | Macro context, bull/base/bear scenarios |
| 📊 Quant + News | Data & sentiment fusion | Financial trends + news sentiment analysis |

## Tech Stack

- **LangGraph** — workflow orchestration with full `asyncio` parallelism
- **Google Gemini** — LLM powering all 5 agents
- **python-telegram-bot** — Telegram interface
- **yfinance** — financial statements, price history, key metrics
- **DuckDuckGo Search (ddgs)** — real-time news and web search
- **matplotlib** — price chart generation (thread-safe)
- **LangSmith** — tracing and monitoring

## Project Structure

```
stock-bot/
├── main.py                 # Entry point
├── bot/
│   └── handlers.py         # Telegram handlers + streaming progress
├── graph/
│   ├── state.py            # LangGraph TypedDict state
│   ├── nodes.py            # 4 nodes: parse → fetch → analyze → synthesize
│   └── workflow.py         # Graph assembly
├── agents/
│   └── prompts.py          # System prompts for all 5 agents
├── tools/
│   ├── financial.py        # yfinance + technicals + DCF + cache
│   ├── search.py           # DuckDuckGo news + cache
│   ├── chart.py            # Thread-safe price chart generator
│   └── cache.py            # In-memory TTL cache (1 hour)
└── utils/
    └── formatter.py        # Telegram HTML formatter + comparison table
```

## Installation

```bash
git clone <repo-url>
cd stock-bot
pip install -r requirements.txt
```

Create a `.env` file:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=stock_bot
TELEGRAM_TOKEN=your_telegram_bot_token
GOOGLE_API_KEY=your_google_ai_key
GEMINI_MODEL=gemini-3-flash-preview
```

Run:

```bash
python main.py
```

## Usage

Send a message to your Telegram bot:

```
Analisis BBCA dan TLKM
Analyze AAPL, MSFT, NVDA
GOTO.JK, BREN.JK, AAPL, TSLA
Compare Apple and Microsoft
```

The bot responds with:
1. Realtime progress updates
2. 1-year price chart per stock (photo)
3. Analysis from all 5 agents
4. Final synthesis + price prediction
5. Comparison table (if more than 1 stock)

## How It Works

```
User Message
    │
    ▼
parse_stocks   →  Extract tickers, detect language (Gemini)
    │
    ▼
fetch_data     →  yfinance + DuckDuckGo for all stocks in parallel
    │              [chart generation starts in background]
    ▼
analyze_stocks →  5 agents × N stocks = all parallel (asyncio.gather)
    │
    ▼
synthesize     →  Per-stock synthesis + price prediction (parallel)
    │
    ▼
Telegram       →  Chart photo + analysis text + comparison table
```

## Notes

- Gemini API Tier 1 rate limits apply — recommended max 5 stocks per request
- Financial data from yfinance may be incomplete for some IDX tickers
- Cache is in-memory and resets when the bot restarts
- Keep your `.env` file private — never commit API keys to version control
