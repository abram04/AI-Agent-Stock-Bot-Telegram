import asyncio
from typing import Dict, List

from ddgs import DDGS

from tools.cache import cache_get, cache_set


def _search_news_sync(query: str, max_results: int = 6) -> List[str]:
    try:
        results = DDGS().news(query, max_results=max_results)
        return [
            f"{r.get('title', '')}: {r.get('body', '')[:250]}"
            for r in results if r.get("title")
        ]
    except Exception:
        return []


def _search_text_sync(query: str, max_results: int = 4) -> List[str]:
    try:
        results = DDGS().text(query, max_results=max_results)
        return [
            f"{r.get('title', '')}: {r.get('body', '')[:200]}"
            for r in results if r.get("title")
        ]
    except Exception:
        return []


async def fetch_news(ticker: str, company_name: str = "") -> List[str]:
    key = f"news:{ticker}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    loop = asyncio.get_event_loop()
    name_part = company_name if company_name and company_name != ticker else ""
    q_news = f"{ticker} {name_part} stock analysis 2025".strip()
    q_text = f"{ticker} {name_part} earnings forecast".strip()

    news, text = await asyncio.gather(
        loop.run_in_executor(None, _search_news_sync, q_news, 6),
        loop.run_in_executor(None, _search_text_sync, q_text, 4),
    )
    combined = news + [t for t in text if t not in news]
    result = combined[:8]
    cache_set(key, result)
    return result


async def fetch_all_news(tickers: List[str], financial_data: Dict) -> Dict[str, List[str]]:
    async def _one(ticker: str):
        name = financial_data.get(ticker, {}).get("name", "")
        return ticker, await fetch_news(ticker, name)

    results = await asyncio.gather(*[_one(t) for t in tickers])
    return {ticker: news for ticker, news in results}
