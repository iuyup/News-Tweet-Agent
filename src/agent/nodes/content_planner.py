"""
ContentPlanner 节点（规则式，无 LLM 调用）
根据 filtered_items + analysis_reasoning 制定发推计划
"""
import logging

from src.config import settings
from src.models.news_item import Category, NewsItem

logger = logging.getLogger(__name__)


def content_planner_node(state: dict) -> dict:
    """
    制定内容计划：统计各分类条目数，按比例分配发推数量。
    输出 content_plan: {politics_count, tech_count, total, reasoning}
    """
    filtered: list[NewsItem] = state.get("filtered_items", [])
    analysis_reasoning: str = state.get("analysis_reasoning", "")
    total_budget = settings.tweets_per_run

    politics = [i for i in filtered if i.category == Category.POLITICS]
    tech = [i for i in filtered if i.category == Category.TECH]

    has_politics = bool(politics)
    has_tech = bool(tech)

    if has_politics and has_tech:
        # 双类均有：均分，剩余给 politics
        tech_count = total_budget // 2
        politics_count = total_budget - tech_count
    elif has_politics:
        politics_count = total_budget
        tech_count = 0
    elif has_tech:
        tech_count = total_budget
        politics_count = 0
    else:
        politics_count = 0
        tech_count = 0

    content_plan = {
        "politics_count": politics_count,
        "tech_count": tech_count,
        "total": politics_count + tech_count,
        "analysis_reasoning": analysis_reasoning,
    }

    logger.info(
        "ContentPlanner: politics=%d tech=%d total=%d",
        politics_count,
        tech_count,
        content_plan["total"],
    )
    return {"content_plan": content_plan}
