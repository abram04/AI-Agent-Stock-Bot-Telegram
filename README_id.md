# Stock Analysis Bot

Multi-agent Telegram bot yang menganalisis saham secara paralel menggunakan 5 agen AI dengan filosofi investasi berbeda. Mendukung saham Indonesia (IDX) dan AS (NYSE/NASDAQ).

## Fitur

- **5 Agen Paralel** — setiap saham dianalisis secara bersamaan oleh 5 perspektif unik
- **Hingga 10 saham sekaligus** — semua diproses paralel menggunakan `asyncio`
- **Chart harga 1 tahun** — dikirim sebagai foto ke Telegram (MA20, MA50, volume)
- **Technical indicators** — RSI, MACD, Moving Average 20/50/200
- **DCF Valuation** — intrinsic value otomatis + margin of safety
- **Caching 1 jam** — data yang sama tidak di-fetch ulang
- **Progress realtime** — update status di Telegram setiap tahap
- **Tabel perbandingan** — ringkasan BUY/HOLD/SELL untuk multi-saham
- **Bilingual** — deteksi otomatis Bahasa Indonesia / English
- **LangSmith tracing** — monitoring penuh setiap run

## 5 Agen Investasi

| Agen | Filosofi | Fokus |
|------|----------|-------|
| 🎩 Warren Buffett | Value investing | Moat, ROE, FCF, long-term earnings |
| 🧮 Joel Greenblatt | Magic Formula | Earnings yield + Return on capital |
| 📚 Benjamin Graham | Defensive value | Margin of safety, Graham Number |
| 👔 25-Year Veteran | Battle-tested experience | Macro, skenario bull/base/bear |
| 📊 Quant + News | Data & sentiment | Tren finansial + analisis berita |

## Stack

- **LangGraph** — orkestrasi workflow dengan `asyncio`
- **Google Gemini** — model LLM untuk semua agen
- **python-telegram-bot** — interface Telegram
- **yfinance** — data keuangan, laporan, harga historis
- **DuckDuckGo Search (ddgs)** — berita terkini
- **matplotlib** — chart harga
- **LangSmith** — tracing & monitoring

## Struktur

```
stock-bot/
├── main.py                 # Entry point
├── bot/
│   └── handlers.py         # Telegram handlers + progress streaming
├── graph/
│   ├── state.py            # LangGraph state
│   ├── nodes.py            # 4 node: parse → fetch → analyze → synthesize
│   └── workflow.py         # Graph assembly
├── agents/
│   └── prompts.py          # System prompt 5 agen
├── tools/
│   ├── financial.py        # yfinance + technicals + DCF + cache
│   ├── search.py           # DuckDuckGo news + cache
│   ├── chart.py            # Price chart generator (thread-safe)
│   └── cache.py            # In-memory TTL cache (1 jam)
└── utils/
    └── formatter.py        # Telegram HTML formatter + comparison table
```

## Instalasi

```bash
git clone <repo-url>
cd stock-bot
pip install -r requirements.txt
```

Buat file `.env`:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=stock_bot
TELEGRAM_TOKEN=your_telegram_bot_token
GOOGLE_API_KEY=your_google_ai_key
GEMINI_MODEL=gemini-3-flash-preview
```

Jalankan:

```bash
python main.py
```

## Cara Pakai

Kirim pesan ke bot Telegram:

```
Analisis BBCA dan TLKM
Analyze AAPL, MSFT, NVDA
GOTO.JK, BREN.JK, AAPL, TSLA
Bandingkan Apple dan Microsoft
```

Bot akan membalas dengan:
1. Progress update realtime
2. Chart harga 1 tahun per saham
3. Analisis dari 5 agen
4. Sintesis akhir + prediksi harga
5. Tabel perbandingan (jika >1 saham)

## Alur Kerja

```
User Message
    │
    ▼
parse_stocks  →  Ekstrak ticker, deteksi bahasa
    │
    ▼
fetch_data    →  yfinance + DuckDuckGo (semua saham paralel)
    │            [chart generation dimulai di background]
    ▼
analyze_stocks → 5 agen × N saham = semua paralel (asyncio.gather)
    │
    ▼
synthesize    →  Sintesis per saham (paralel)
    │
    ▼
Telegram      →  Chart foto + analisis teks + tabel perbandingan
```

## Catatan

- Tier 1 Gemini API: rate limit berlaku, disarankan max 5 saham per request
- Data keuangan dari yfinance bisa tidak lengkap untuk saham IDX tertentu
- Cache berlaku 1 jam per ticker (in-memory, reset saat bot restart)
