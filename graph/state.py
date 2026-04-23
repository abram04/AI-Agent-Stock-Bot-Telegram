from typing import TypedDict, List, Dict, Any, Optional


class StockAnalysisState(TypedDict):
    user_message: str
    language: str
    tickers: List[str]
    financial_data: Dict[str, Any]
    news_data: Dict[str, List[str]]
    agent_results: Dict[str, Dict[str, str]]
    synthesis: Dict[str, str]
    error: Optional[str]
