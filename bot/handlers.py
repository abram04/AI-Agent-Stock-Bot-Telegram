import asyncio
from typing import Dict

from telegram import Update
from telegram.ext import ContextTypes

from graph.state import StockAnalysisState
from graph.workflow import workflow
from tools.chart import generate_chart
from utils.formatter import format_all, format_comparison

PROGRESS = {
    "parse_stocks": "🔍 <b>Mengidentifikasi saham...</b>",
    "fetch_data": "📥 <b>Mengambil data keuangan, teknikal &amp; berita...</b>",
    "analyze_stocks": (
        "🤖 <b>5 agen menganalisis secara paralel</b>\n"
        "<i>Warren Buffett · Greenblatt · Graham · Veteran · Quant+News</i>\n"
        "<i>Harap tunggu 30–60 detik...</i>"
    ),
    "synthesize": "🔮 <b>Menyintesis hasil dari semua agen...</b>",
}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>👋 Stock Analysis Bot</b>\n\n"
        "Analisis saham dengan <b>5 agen expert paralel</b>:\n\n"
        "🎩 Warren Buffett Agent — moat &amp; long-term value\n"
        "🧮 Joel Greenblatt Agent — Magic Formula\n"
        "📚 Benjamin Graham Agent — margin of safety\n"
        "👔 25-Year Veteran Analyst — macro + fundamental\n"
        "📊 Quant + News Analyst — data &amp; sentiment\n\n"
        "Setiap saham mendapat: <b>chart 1 tahun</b>, analisis 5 agen,\n"
        "<b>DCF valuation</b>, indikator teknikal (RSI, MACD, MA),\n"
        "dan <b>sintesis akhir + prediksi harga</b>.\n\n"
        "<b>Contoh:</b>\n"
        "• <code>Analisis BBCA dan TLKM</code>\n"
        "• <code>Analyze AAPL, MSFT, NVDA</code>\n"
        "• <code>GOTO.JK, BREN.JK, AAPL, TSLA</code>\n\n"
        "Maks <b>10 saham</b> per permintaan.",
        parse_mode="HTML",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    processing = await update.message.reply_text(
        "🔍 <b>Memulai analisis...</b>",
        parse_mode="HTML",
    )

    initial: StockAnalysisState = {
        "user_message": update.message.text,
        "language": "en",
        "tickers": [],
        "financial_data": {},
        "news_data": {},
        "agent_results": {},
        "synthesis": {},
        "error": None,
    }

    final_state: dict = dict(initial)
    chart_tasks: Dict[str, asyncio.Task] = {}

    try:
        async for chunk in workflow.astream(initial):
            for node_name, state_update in chunk.items():
                if node_name in PROGRESS:
                    try:
                        await processing.edit_text(PROGRESS[node_name], parse_mode="HTML")
                    except Exception:
                        pass

                if isinstance(state_update, dict):
                    final_state.update(state_update)

                # Kick off chart generation as soon as tickers are known
                if node_name == "parse_stocks":
                    for ticker in final_state.get("tickers", []):
                        if ticker not in chart_tasks:
                            chart_tasks[ticker] = asyncio.create_task(generate_chart(ticker))

        # Collect charts (max 30s wait)
        charts: Dict[str, bytes] = {}
        if chart_tasks:
            results = await asyncio.gather(*chart_tasks.values(), return_exceptions=True)
            for ticker, result in zip(chart_tasks.keys(), results):
                if isinstance(result, bytes):
                    charts[ticker] = result

        await processing.delete()

        tickers = final_state.get("tickers", [])

        for ticker in tickers:
            fin = final_state.get("financial_data", {}).get(ticker, {})

            # Send chart photo first
            if ticker in charts:
                try:
                    name = fin.get("name", ticker)
                    price = fin.get("current_price")
                    change = fin.get("price_1y_change_pct")
                    rsi = fin.get("technical_indicators", {}).get("rsi_14")
                    caption = f"📈 {name} ({ticker})"
                    if price:
                        caption += f"\n💵 {fin.get('currency','')} {price:,.2f}"
                    if change is not None:
                        arrow = "▲" if float(change) >= 0 else "▼"
                        caption += f"  {arrow} {abs(float(change)):.1f}% (1Y)"
                    if rsi:
                        caption += f"  |  RSI: {rsi:.1f}"
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=charts[ticker],
                        caption=caption,
                    )
                except Exception:
                    pass

            # Send analysis text
            single = {**final_state, "tickers": [ticker]}
            for msg in format_all(single):
                await context.bot.send_message(
                    chat_id=chat_id, text=msg, parse_mode="HTML"
                )

        # Comparison table for multiple stocks
        if len(tickers) > 1:
            table = format_comparison(final_state)
            if table:
                await context.bot.send_message(
                    chat_id=chat_id, text=table, parse_mode="HTML"
                )

    except Exception as exc:
        try:
            await processing.edit_text(f"❌ <b>Error:</b> {exc}", parse_mode="HTML")
        except Exception:
            pass
