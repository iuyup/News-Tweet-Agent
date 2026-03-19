"""
Analyst 节点
LLM 分析原始新闻，选出值得发推的条目，输出 should_tweet + analysis_reasoning
"""
import json
import logging

from src.agent._llm_call import call_default_llm
from src.models.news_item import Category, NewsItem
from src.prompts import build_analyst_prompt

logger = logging.getLogger(__name__)

# 提交给 LLM 的最大候选条数
_MAX_CANDIDATES = 20


def _pre_filter(items: list[NewsItem]) -> list[NewsItem]:
    """规则式预过滤：去 UNKNOWN、去过短标题，按 score 降序"""
    filtered = [
        item for item in items
        if item.category != Category.UNKNOWN and len(item.title) >= 10
    ]
    filtered.sort(key=lambda x: x.score, reverse=True)
    return filtered[:_MAX_CANDIDATES]


async def _call_llm(prompt: str) -> str:
    return await call_default_llm(prompt, max_tokens=512)


def _parse_analyst_response(raw: str, candidates: list[NewsItem]) -> dict:
    """解析 LLM 响应，返回 {should_tweet, reasoning, filtered_items}"""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])

    data = json.loads(text)
    should_tweet: bool = bool(data.get("should_tweet", True))
    reasoning: str = data.get("reasoning", "")
    indices: list[int] = data.get("selected_indices", [])

    selected: list[NewsItem] = []
    for idx in indices:
        zero_based = idx - 1
        if 0 <= zero_based < len(candidates):
            selected.append(candidates[zero_based])

    # 保底：LLM 未选则取前 6 条
    if not selected and should_tweet and candidates:
        selected = candidates[:6]

    return {
        "should_tweet": should_tweet,
        "reasoning": reasoning,
        "filtered_items": selected,
    }


async def analyst_node(state: dict) -> dict:
    """分析 raw_items，选出值得发推的新闻，输出 filtered_items + 判断"""
    raw_items: list[NewsItem] = state.get("raw_items", [])

    if not raw_items:
        logger.warning("Analyst: raw_items 为空，跳过")
        return {
            "should_tweet": False,
            "analysis_reasoning": "无抓取数据",
            "filtered_items": [],
            "error_log": ["Analyst: raw_items 为空"],
        }

    candidates = _pre_filter(raw_items)
    if not candidates:
        logger.warning("Analyst: 预过滤后无有效新闻")
        return {
            "should_tweet": False,
            "analysis_reasoning": "预过滤后无有效新闻",
            "filtered_items": [],
            "error_log": ["Analyst: 预过滤后无有效条目"],
        }

    # 从 SQLite 读取最近 7 天推文，作为去重上下文
    recent_tweets: list[dict] = []
    try:
        from src.storage.db import get_recent_tweets
        recent_tweets = get_recent_tweets(days=7)
        if recent_tweets:
            logger.info("Analyst: 载入 %d 条近期推文作去重参考", len(recent_tweets))
    except Exception as e:
        logger.warning("Analyst: 无法读取近期推文历史: %s", e)

    prompt = build_analyst_prompt(candidates, recent_tweets=recent_tweets)

    try:
        raw = await _call_llm(prompt)
        result = _parse_analyst_response(raw, candidates)
    except Exception as e:
        msg = f"Analyst LLM 调用失败: {e}，降级为规则过滤"
        logger.warning(msg)
        # 降级：直接使用规则预过滤结果
        result = {
            "should_tweet": True,
            "reasoning": "LLM 分析失败，使用规则过滤结果",
            "filtered_items": candidates[:6],
        }

    logger.info(
        "Analyst: should_tweet=%s，选出 %d 条 | %s",
        result["should_tweet"],
        len(result["filtered_items"]),
        result["reasoning"][:80],
    )

    return {
        "should_tweet": result["should_tweet"],
        "analysis_reasoning": result["reasoning"],
        "filtered_items": result["filtered_items"],
    }
