"""
Writer 节点
- 正常模式：调用 generate_tweets()，使用 ContentPlanner 制定的数量
- 修改模式：基于 Reviewer 反馈重写现有推文（revision_count > 0）
"""
import json
import logging

from src.agent._llm_call import call_default_llm
from src.config import settings
from src.generator import generate_tweets
from src.models.news_item import Category
from src.prompts.templates import build_revision_prompt

logger = logging.getLogger(__name__)


def _parse_revision(raw: str, originals: list[dict]) -> list[dict]:
    """解析修改后的推文，保留原始 news_item 引用"""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])

    data = json.loads(text)
    revised_list = data.get("revised", [])

    result = []
    for r in revised_list:
        idx = r.get("index", 1) - 1  # 转 0-based
        if 0 <= idx < len(originals):
            original = originals[idx]
            tweet_text = r["tweet"]
            if len(tweet_text) > settings.tweet_max_length:
                tweet_text = tweet_text[:settings.tweet_max_length]
            result.append({
                "tweet": tweet_text,
                "news_item": original["news_item"],
                "input_tokens": original.get("input_tokens", 0),
                "output_tokens": original.get("output_tokens", 0),
            })

    # 保底：解析失败时返回原推文
    return result if result else originals


async def writer_node(state: dict) -> dict:
    """生成或修改推文"""
    filtered = state.get("filtered_items", [])
    revision_count = state.get("revision_count", 0)
    review_feedback = state.get("review_feedback", "")
    current_tweets = state.get("generated_tweets", [])

    if not filtered:
        logger.warning("Writer: 无可用新闻，跳过")
        return {
            "generated_tweets": [],
            "error_log": ["Writer: filtered_items 为空，跳过"],
        }

    # ── 修改模式 ──────────────────────────────────────────────────────────
    if revision_count > 0 and review_feedback and current_tweets:
        logger.info("Writer: 修改模式（第 %d 次）", revision_count)
        try:
            prompt = build_revision_prompt(current_tweets, review_feedback)
            raw = await call_default_llm(prompt, max_tokens=1024)
            tweets = _parse_revision(raw, current_tweets)
            logger.info("Writer: 修改完成，%d 条推文", len(tweets))
            return {"generated_tweets": tweets}
        except Exception as e:
            logger.error("Writer: 修改失败 %s，保留原推文", e)
            return {"generated_tweets": current_tweets}

    # ── 正常生成模式 ──────────────────────────────────────────────────────
    content_plan = state.get("content_plan", {})
    politics_count = content_plan.get("politics_count", 0)
    tech_count = content_plan.get("tech_count", 0)
    total = content_plan.get("total", settings.tweets_per_run) or settings.tweets_per_run

    politics_items = [i for i in filtered if i.category == Category.POLITICS]
    tech_items = [i for i in filtered if i.category == Category.TECH]

    tweets: list[dict] = []
    try:
        # 按 ContentPlanner 配比分别生成，逐条调用以避免同类重复
        for _ in range(politics_count):
            if not politics_items:
                break
            result = await generate_tweets(politics_items, count=1)
            tweets.extend(result)
            # 排除已选条目，避免下次重复选同一条
            if result:
                selected = result[0].get("news_item")
                politics_items = [i for i in politics_items if i != selected]

        for _ in range(tech_count):
            if not tech_items:
                break
            result = await generate_tweets(tech_items, count=1)
            tweets.extend(result)
            if result:
                selected = result[0].get("news_item")
                tech_items = [i for i in tech_items if i != selected]

        # 兜底：content_plan 缺失时按总数生成
        if not tweets:
            tweets = await generate_tweets(filtered, count=total)

    except Exception as e:
        msg = f"Writer: 推文生成异常: {e}"
        logger.error(msg)
        return {"generated_tweets": [], "error_log": [msg]}

    logger.info("Writer: 生成 %d 条推文（计划 %d 条）", len(tweets), total)
    return {"generated_tweets": tweets}
