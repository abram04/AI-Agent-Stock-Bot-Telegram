import asyncio
import json
import os
import re
from typing import Dict, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

def _extract_text(content) -> str:
    if isinstance(content, list):
        return "".join(
            part.get("text", str(part)) if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


from agents.prompts import (
    BUFFETT_PROMPT,
    GRAHAM_PROMPT,
    GREENBLATT_PROMPT,
    QUANT_NEWS_PROMPT,
    VETERAN_PROMPT,
)
from graph.state import StockAnalysisState
from tools.financial import fetch_all_stocks
from tools.search import fetch_all_news

_llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-3-pro-preview"),
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.7,
)

AGENTS = [
    ("buffett", BUFFETT_PROMPT),
    ("greenblatt", GREENBLATT_PROMPT),
    ("graham", GRAHAM_PROMPT),
    ("veteran", VETERAN_PROMPT),
    ("quant_news", QUANT_NEWS_PROMPT),
]


async def parse_stocks_node(state: StockAnalysisState) -> dict:
    prompt = (
        "Extract stock ticker symbols from this user message and detect the language.\n\n"
        f"Message: \"{state['user_message']}\"\n\n"
        "Rules:\n"
        "- Indonesian stocks (IDX): ALWAYS add .JK suffix\n"
        "  Common IDX: BBCA, BBRI, BMRI, TLKM, ASII, GOTO, BREN, ADRO, UNVR, HMSP, ICBP, KLBF, MAPI, SMGR\n"
        "- US stocks (NYSE/NASDAQ): keep as-is (AAPL, MSFT, NVDA, GOOG, AMZN, TSLA)\n"
        "- Convert company names to tickers (Apple -> AAPL, Bank BCA -> BBCA.JK)\n"
        "- Language: id=Bahasa Indonesia, en=English (default)\n"
        "- Maximum 10 tickers\n\n"
        'Return ONLY raw JSON: {"tickers": ["BBCA.JK", "AAPL"], "language": "id"}'
    )

    try:
        response = await _llm.ainvoke([HumanMessage(content=prompt)])
        raw = _extract_text(response.content).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            tickers = [t.upper() for t in data.get("tickers", [])]
            language = data.get("language", "en")
            if not tickers:
                return {"error": "Tidak ada ticker ditemukan. Sebutkan nama/kode saham spesifik."}
            return {"tickers": tickers[:10], "language": language}
    except Exception as exc:
        return {"error": f"Gagal parsing saham: {exc}"}
    return {"error": "Tidak dapat mengidentifikasi saham dari pesan Anda."}


async def fetch_data_node(state: StockAnalysisState) -> dict:
    if state.get("error"):
        return {}
    financial_data = await fetch_all_stocks(state["tickers"])
    news_data = await fetch_all_news(state["tickers"], financial_data)
    return {"financial_data": financial_data, "news_data": news_data}


async def analyze_stocks_node(state: StockAnalysisState) -> dict:
    if state.get("error"):
        return {}

    language = state.get("language", "en")
    lang_instr = (
        "Language instruction: Respond entirely in Bahasa Indonesia."
        if language == "id"
        else "Language instruction: Respond entirely in English."
    )

    def fmt(v, mult=1, dec=2):
        if v is None:
            return "N/A"
        try:
            return f"{float(v) * mult:.{dec}f}"
        except Exception:
            return str(v)

    async def run_agent(ticker: str, agent_name: str, system_prompt: str) -> Tuple[str, str, str]:
        fin = state["financial_data"].get(ticker, {})
        ddg_news = state["news_data"].get(ticker, [])
        yf_news = fin.get("recent_news", [])
        all_news = yf_news + [n for n in ddg_news if n not in yf_news]

        news_block = "\n".join(f"- {n}" for n in all_news[:8]) or "No recent news available."

        income_trends = json.dumps(fin.get("income_statement_trends", {}), indent=2, default=str)
        bs_trends = json.dumps(fin.get("balance_sheet_trends", {}), indent=2, default=str)
        cf_trends = json.dumps(fin.get("cashflow_trends", {}), indent=2, default=str)

        context = "\n".join([
            f"Stock: {ticker}",
            f"Company: {fin.get('name', ticker)}",
            f"Sector: {fin.get('sector', 'N/A')} | Industry: {fin.get('industry', 'N/A')}",
            f"Currency: {fin.get('currency', 'USD')} | Exchange: {fin.get('exchange', 'N/A')}",
            "",
            "=== PRICE & VALUATION ===",
            f"Current Price:    {fmt(fin.get('current_price'))}",
            f"52W High/Low:     {fmt(fin.get('52_week_high'))} / {fmt(fin.get('52_week_low'))}",
            f"1Y Price Change:  {fmt(fin.get('price_1y_change_pct'))}%",
            f"Market Cap:       {fin.get('market_cap')}",
            f"P/E (TTM):        {fmt(fin.get('pe_ratio_trailing'))}",
            f"P/E (Fwd):        {fmt(fin.get('pe_ratio_forward'))}",
            f"P/B:              {fmt(fin.get('pb_ratio'))}",
            f"P/S:              {fmt(fin.get('ps_ratio'))}",
            f"EV/EBITDA:        {fmt(fin.get('ev_ebitda'))}",
            f"PEG Ratio:        {fmt(fin.get('peg_ratio'))}",
            "",
            "=== PROFITABILITY ===",
            f"ROE:              {fmt(fin.get('roe'), 100, 1)}%",
            f"ROA:              {fmt(fin.get('roa'), 100, 1)}%",
            f"Gross Margin:     {fmt(fin.get('gross_margin'), 100, 1)}%",
            f"Operating Margin: {fmt(fin.get('operating_margin'), 100, 1)}%",
            f"Net Margin:       {fmt(fin.get('profit_margin'), 100, 1)}%",
            "",
            "=== FINANCIAL HEALTH ===",
            f"Debt/Equity:      {fmt(fin.get('debt_equity'))}",
            f"Current Ratio:    {fmt(fin.get('current_ratio'))}",
            f"Quick Ratio:      {fmt(fin.get('quick_ratio'))}",
            f"Total Debt:       {fin.get('total_debt')}",
            f"Total Cash:       {fin.get('total_cash')}",
            f"Free Cash Flow:   {fin.get('free_cashflow')}",
            f"Operating CF:     {fin.get('operating_cashflow')}",
            "",
            "=== GROWTH ===",
            f"Revenue Growth (YoY): {fmt(fin.get('revenue_growth'), 100, 1)}%",
            f"Earnings Growth:      {fmt(fin.get('earnings_growth'), 100, 1)}%",
            f"EPS (TTM):            {fmt(fin.get('eps_trailing'))}",
            f"EPS (Fwd):            {fmt(fin.get('eps_forward'))}",
            f"Book Value/Share:     {fmt(fin.get('book_value'))}",
            "",
            "=== DIVIDEND ===",
            f"Dividend Yield: {fmt(fin.get('dividend_yield'), 100, 2)}%",
            f"Payout Ratio:   {fmt(fin.get('payout_ratio'), 100, 1)}%",
            "",
            "=== MARKET DATA ===",
            f"Beta:                   {fmt(fin.get('beta'))}",
            f"Analyst Target Price:   {fin.get('target_price')}",
            f"Analyst Recommendation: {fin.get('recommendation')}",
            f"# of Analyst Opinions:  {fin.get('number_of_analyst_opinions')}",
            "",
            "=== MULTI-YEAR INCOME TRENDS ===",
            income_trends,
            "",
            "=== BALANCE SHEET TRENDS ===",
            bs_trends,
            "",
            "=== CASH FLOW TRENDS ===",
            cf_trends,
            "",
            "=== TECHNICAL INDICATORS ===",
            f"RSI (14):     {fmt(fin.get('technical_indicators', {}).get('rsi_14'))} → {fin.get('technical_indicators', {}).get('rsi_signal', 'N/A')}",
            f"MACD Line:    {fmt(fin.get('technical_indicators', {}).get('macd_line'), dec=4)} | Signal: {fmt(fin.get('technical_indicators', {}).get('macd_signal'), dec=4)} → {fin.get('technical_indicators', {}).get('macd_trend', 'N/A')}",
            f"MA20:  {fmt(fin.get('technical_indicators', {}).get('ma_20'))} ({fmt(fin.get('technical_indicators', {}).get('price_vs_ma20_pct'))}% vs price)",
            f"MA50:  {fmt(fin.get('technical_indicators', {}).get('ma_50'))} ({fmt(fin.get('technical_indicators', {}).get('price_vs_ma50_pct'))}% vs price)",
            f"MA200: {fmt(fin.get('technical_indicators', {}).get('ma_200'))} ({fmt(fin.get('technical_indicators', {}).get('price_vs_ma200_pct'))}% vs price)",
            "",
            "=== DCF VALUATION ===",
            f"Intrinsic Value (DCF): {fmt(fin.get('dcf', {}).get('dcf_intrinsic_value'))} {fin.get('currency', '')}",
            f"Margin of Safety:      {fmt(fin.get('dcf', {}).get('dcf_margin_of_safety_pct'))}%  (positive = undervalued)",
            f"Assumptions:           {fin.get('dcf', {}).get('dcf_assumptions', 'N/A')}",
            "",
            "=== RECENT NEWS ===",
            news_block,
            "",
            lang_instr,
        ])

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Analyze this stock:\n\n{context}"),
        ]
        try:
            resp = await _llm.ainvoke(messages)
            return (ticker, agent_name, _extract_text(resp.content))
        except Exception as exc:
            return (ticker, agent_name, f"[Analysis error: {exc}]")

    tasks = [
        run_agent(ticker, agent_name, prompt)
        for ticker in state["tickers"]
        for agent_name, prompt in AGENTS
    ]

    raw = await asyncio.gather(*tasks, return_exceptions=True)

    agent_results: Dict[str, Dict[str, str]] = {}
    for item in raw:
        if isinstance(item, Exception):
            continue
        ticker, agent_name, analysis = item
        agent_results.setdefault(ticker, {})[agent_name] = analysis

    return {"agent_results": agent_results}


async def synthesize_node(state: StockAnalysisState) -> dict:
    if state.get("error"):
        return {}

    language = state.get("language", "en")
    lang_instr = (
        "Respond entirely in Bahasa Indonesia."
        if language == "id"
        else "Respond entirely in English."
    )

    agent_display = {
        "buffett": "Warren Buffett Agent",
        "greenblatt": "Joel Greenblatt Agent",
        "graham": "Benjamin Graham Agent",
        "veteran": "25-Year Veteran Analyst",
        "quant_news": "Quant + News Analyst",
    }

    async def synthesize_one(ticker: str) -> Tuple[str, str]:
        analyses = state["agent_results"].get(ticker, {})
        fin = state["financial_data"].get(ticker, {})

        combined = "\n\n".join(
            f"--- {agent_display.get(k, k)} ---\n{v}"
            for k, v in analyses.items()
        )

        prompt = "\n".join([
            f"You are the senior investment committee chair reviewing {ticker} ({fin.get('name', ticker)}).",
            "",
            f"Current Price: {fin.get('current_price')} {fin.get('currency', '')}",
            f"52W Range: {fin.get('52_week_low')} - {fin.get('52_week_high')}",
            f"Analyst Consensus: {fin.get('recommendation', 'N/A')} | Target: {fin.get('target_price', 'N/A')}",
            "",
            "FIVE EXPERT ANALYSES:",
            combined,
            "",
            "Write a synthesis covering:",
            "",
            "[CONSENSUS SUMMARY]",
            "Where the 5 analysts agree and disagree (max 80 words)",
            "",
            "[FINAL VERDICT]",
            "Recommendation: BUY / HOLD / SELL",
            "Confidence: HIGH / MEDIUM / LOW",
            "Time Horizon: [timeframe]",
            "Analyst Agreement: [X/5 aligned]",
            "",
            "[PRICE PREDICTION]",
            "Short-term (3-6 months): [price range with currency]",
            "Mid-term (1-2 years): [price range with currency]",
            "Key Price Driver: [single most important factor]",
            "",
            "[TOP 3 RISKS]",
            "1. [risk]",
            "2. [risk]",
            "3. [risk]",
            "",
            lang_instr,
        ])

        try:
            resp = await _llm.ainvoke([HumanMessage(content=prompt)])
            return (ticker, _extract_text(resp.content))
        except Exception as exc:
            return (ticker, f"[Synthesis error: {exc}]")

    tasks = [synthesize_one(ticker) for ticker in state["tickers"]]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    synthesis: Dict[str, str] = {}
    for item in raw:
        if isinstance(item, Exception):
            continue
        ticker, summary = item
        synthesis[ticker] = summary

    return {"synthesis": synthesis}
