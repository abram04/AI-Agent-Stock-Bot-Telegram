from langgraph.graph import StateGraph, END

from graph.nodes import (
    analyze_stocks_node,
    fetch_data_node,
    parse_stocks_node,
    synthesize_node,
)
from graph.state import StockAnalysisState


def create_workflow():
    graph = StateGraph(StockAnalysisState)

    graph.add_node("parse_stocks", parse_stocks_node)
    graph.add_node("fetch_data", fetch_data_node)
    graph.add_node("analyze_stocks", analyze_stocks_node)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("parse_stocks")
    graph.add_edge("parse_stocks", "fetch_data")
    graph.add_edge("fetch_data", "analyze_stocks")
    graph.add_edge("analyze_stocks", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


workflow = create_workflow()
