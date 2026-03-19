"""
StateGraph 组装 (Phase 4)

START → SourceRouter → Collector → Analyst → ContentPlanner → Writer → Reviewer →(通过/超限)→ Publisher → END
                                                                ↑←────(未通过)──────────────┘

MAX_REVISIONS = 2：最多 2 次修改（共 3 次 Reviewer 评审）
"""
import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agent.nodes import (
    analyst_node,
    collector_node,
    content_planner_node,
    publisher_node,
    reviewer_node,
    source_router_node,
    writer_node,
)
from src.agent.state import TweetAgentState

logger = logging.getLogger(__name__)

MAX_REVISIONS = 2  # 超过此次数强制发布


def _after_collect(state: TweetAgentState) -> str:
    if state.get("raw_items"):
        return "analyst"
    logger.info("Graph: 无抓取数据，结束")
    return END


def _after_analyst(state: TweetAgentState) -> str:
    if state.get("should_tweet", True) and state.get("filtered_items"):
        return "content_planner"
    logger.info(
        "Graph: Analyst 不发推 (should_tweet=%s, items=%d)，结束",
        state.get("should_tweet"),
        len(state.get("filtered_items", [])),
    )
    return END


def _after_write(state: TweetAgentState) -> str:
    if state.get("generated_tweets"):
        return "reviewer"
    logger.info("Graph: 无推文，结束")
    return END


def _after_review(state: TweetAgentState) -> str:
    if state.get("review_passed"):
        return "publisher"
    revision_count = state.get("revision_count", 0)
    if revision_count >= MAX_REVISIONS:
        logger.info("Graph: 达到最大修改次数 %d，强制发布", revision_count)
        return "publisher"
    logger.info("Graph: 评审未通过，第 %d 次修改", revision_count)
    return "writer"


def build_graph() -> StateGraph:
    """构建并返回 StateGraph（未 compile）"""
    graph = StateGraph(TweetAgentState)

    graph.add_node("source_router", source_router_node)
    graph.add_node("collector", collector_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("content_planner", content_planner_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("publisher", publisher_node)

    graph.set_entry_point("source_router")

    graph.add_edge("source_router", "collector")
    graph.add_conditional_edges("collector", _after_collect, {"analyst": "analyst", END: END})
    graph.add_conditional_edges("analyst", _after_analyst, {"content_planner": "content_planner", END: END})
    graph.add_edge("content_planner", "writer")
    graph.add_conditional_edges("writer", _after_write, {"reviewer": "reviewer", END: END})
    graph.add_conditional_edges("reviewer", _after_review, {"writer": "writer", "publisher": "publisher"})
    graph.add_edge("publisher", END)

    return graph


def build_checkpointed_graph():
    """返回带 MemorySaver checkpointing 的编译图"""
    return build_graph().compile(checkpointer=MemorySaver())
