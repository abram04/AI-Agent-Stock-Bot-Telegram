import asyncio
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import yfinance as yf

from tools.cache import cache_get, cache_set


# ── Technical indicators ────────────────────────────────────────────────────

def _calc_technicals(close: pd.Series) -> Dict[str, Any]:
    if close is None or len(close) < 14:
        return {}

    result: Dict[str, Any] = {}
    current = float(close.iloc[-1])

    # RSI 14
    try:
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        rs = gain / loss
        rsi_val = float((100 - 100 / (1 + rs)).iloc[-1])
        result["rsi_14"] = round(rsi_val, 1)
        if rsi_val >= 70:
            result["rsi_signal"] = "OVERBOUGHT"
        elif rsi_val <= 30:
            result["rsi_signal"] = "OVERSOLD"
        else:
            result["rsi_signal"] = "NEUTRAL"
    except Exception:
        pass

    # MACD (12/26/9)
    try:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        result["macd_line"] = round(float(macd.iloc[-1]), 4)
        result["macd_signal"] = round(float(signal.iloc[-1]), 4)
        result["macd_histogram"] = round(float(hist.iloc[-1]), 4)
        result["macd_trend"] = "BULLISH" if float(hist.iloc[-1]) > 0 else "BEARISH"
    except Exception:
        pass

    # Moving averages
    for period in [20, 50, 200]:
        if len(close) >= period:
            try:
                ma = float(close.rolling(period).mean().iloc[-1])
                result[f"ma_{period}"] = round(ma, 2)
                result[f"price_vs_ma{period}_pct"] = round((current - ma) / ma * 100, 1)
            except Exception:
                pass

    return result


# ── DCF ─────────────────────────────────────────────────────────────────────

def _calc_dcf(info: Dict) -> Dict[str, Any]:
    fcf = info.get("freeCashflow")
    shares = info.get("sharesOutstanding")
    if not fcf or not shares or float(fcf) <= 0 or float(shares) <= 0:
        return {}

    growth = float(info.get("earningsGrowth") or info.get("revenueGrowth") or 0.10)
    growth = min(max(growth, 0.0), 0.30)
    terminal_rate = 0.03
    wacc = 0.10

    dcf_value = 0.0
    cf = float(fcf)
    for year in range(1, 11):
        rate = growth if year <= 5 else terminal_rate
        cf *= (1 + rate)
        dcf_value += cf / (1 + wacc) ** year

    terminal = cf * (1 + terminal_rate) / (wacc - terminal_rate)
    dcf_value += terminal / (1 + wacc) ** 10

    intrinsic = dcf_value / float(shares)
    current_price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
    margin = round((intrinsic - current_price) / intrinsic * 100, 1) if intrinsic > 0 and current_price else None

    return {
        "dcf_intrinsic_value": round(intrinsic, 2),
        "dcf_margin_of_safety_pct": margin,
        "dcf_assumptions": f"FCF growth {growth*100:.0f}%/5yr then 3%, WACC 10%",
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_serializable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        val = float(obj)
        return None if (np.isnan(val) or np.isinf(val)) else val
    elif isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    elif isinstance(obj, pd.Timestamp):
        return str(obj)
    return obj


# ── Main fetch ───────────────────────────────────────────────────────────────

def _fetch_sync(ticker: str) -> Dict[str, Any]:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        result: Dict[str, Any] = {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", ""),
            "market_cap": info.get("marketCap"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "target_price": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationKey", ""),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "pe_ratio_trailing": info.get("trailingPE"),
            "pe_ratio_forward": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "peg_ratio": info.get("pegRatio"),
            "enterprise_value": info.get("enterpriseValue"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "ev_revenue": info.get("enterpriseToRevenue"),
            "ebitda": info.get("ebitda"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "profit_margin": info.get("profitMargins"),
            "debt_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "total_debt": info.get("totalDebt"),
            "total_cash": info.get("totalCash"),
            "free_cashflow": info.get("freeCashflow"),
            "operating_cashflow": info.get("operatingCashflow"),
            "revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "eps_trailing": info.get("trailingEps"),
            "eps_forward": info.get("forwardEps"),
            "book_value": info.get("bookValue"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "beta": info.get("beta"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
        }

        # Historical prices + technicals
        try:
            hist = stock.history(period="1y")
            if not hist.empty and len(hist) > 1:
                close = hist["Close"]
                result["price_1y_change_pct"] = round(
                    float((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100), 2
                )
                result["avg_daily_volume"] = int(hist["Volume"].mean())
                result["technical_indicators"] = _calc_technicals(close)
        except Exception:
            pass

        # DCF
        try:
            dcf = _calc_dcf(info)
            if dcf:
                result["dcf"] = dcf
        except Exception:
            pass

        # Multi-year income statement
        try:
            fin = stock.financials
            if not fin.empty:
                trends: Dict[str, Any] = {}
                for row in ["Total Revenue", "Net Income", "EBIT", "Gross Profit", "Operating Income"]:
                    if row in fin.index:
                        series = fin.loc[row].dropna()
                        if not series.empty:
                            trends[row] = {str(k): v for k, v in series.items()}
                if trends:
                    result["income_statement_trends"] = trends
        except Exception:
            pass

        # Balance sheet
        try:
            bs = stock.balance_sheet
            if not bs.empty:
                bs_data: Dict[str, Any] = {}
                for row in ["Total Assets", "Total Liabilities Net Minority Interest",
                            "Stockholders Equity", "Current Assets", "Current Liabilities",
                            "Long Term Debt", "Cash And Cash Equivalents"]:
                    if row in bs.index:
                        series = bs.loc[row].dropna()
                        if not series.empty:
                            bs_data[row] = {str(k): v for k, v in series.head(3).items()}
                if bs_data:
                    result["balance_sheet_trends"] = bs_data
        except Exception:
            pass

        # Cash flow
        try:
            cf = stock.cashflow
            if not cf.empty:
                cf_data: Dict[str, Any] = {}
                for row in ["Free Cash Flow", "Operating Cash Flow", "Capital Expenditure"]:
                    if row in cf.index:
                        series = cf.loc[row].dropna()
                        if not series.empty:
                            cf_data[row] = {str(k): v for k, v in series.head(3).items()}
                if cf_data:
                    result["cashflow_trends"] = cf_data
        except Exception:
            pass

        # Recent news
        try:
            raw_news = stock.news
            result["recent_news"] = [
                f"{item.get('title', '')} ({item.get('publisher', '')})"
                for item in (raw_news or [])[:6]
            ]
        except Exception:
            result["recent_news"] = []

        return _make_serializable(result)

    except Exception as exc:
        return {"ticker": ticker, "error": str(exc), "name": ticker, "recent_news": []}


async def fetch_stock_data(ticker: str) -> Dict[str, Any]:
    key = f"fin:{ticker}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _fetch_sync, ticker)
    if not result.get("error"):
        cache_set(key, result)
    return result


async def fetch_all_stocks(tickers: List[str]) -> Dict[str, Any]:
    results = await asyncio.gather(*[fetch_stock_data(t) for t in tickers])
    return {ticker: data for ticker, data in zip(tickers, results)}
