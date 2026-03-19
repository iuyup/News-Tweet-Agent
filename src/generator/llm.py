"""
LLM 推文生成
复用 _llm_call.call_default_llm_with_usage，返回结构化推文列表
"""
import json
import logging

from src.agent._llm_call import call_default_llm_with_usage
from src.config import settings
from src.models.news_item import Category, NewsItem
from src.prompts import build_tweet_prompt

logger = logging.getLogger(__name__)


class TweetGenerationError(Exception):
    pass


def _parse_response(raw: str) -> dict:
    """从 LLM 响应中提取 JSON"""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
    return json.loads(text)


async def generate_tweets(
    items: list[NewsItem],
    count: int | None = None,
) -> list[dict]:
    """
    从新闻条目中生成推文。
    返回推文字典列表：
    [{"tweet": str, "news_item": NewsItem, "input_tokens": int, "output_tokens": int}]
    """
    count = count or settings.tweets_per_run
    results: list[dict] = []

    by_category: dict[Category, list[NewsItem]] = {
        Category.POLITICS: [],
        Category.TECH: [],
    }
    for item in items:
        if item.category in by_category:
            by_category[item.category].append(item)

    for category, cat_items in by_category.items():
        if len(results) >= count:
            break
        if not cat_items:
            continue

        top_items = cat_items[:10]
        prompt = build_tweet_prompt(top_items, category)

        try:
            raw, usage = await call_default_llm_with_usage(prompt, max_tokens=1024)
            data = _parse_response(raw)
            tweet_text: str = data["tweet"]
            source_idx: int = data["source_index"] - 1  # 转 0-based

            if len(tweet_text) > settings.tweet_max_length:
                logger.warning("推文超长 %d 字符，截断", len(tweet_text))
                tweet_text = tweet_text[: settings.tweet_max_length]

            chosen_item = (
                top_items[source_idx] if 0 <= source_idx < len(top_items) else top_items[0]
            )
            results.append({
                "tweet": tweet_text,
                "news_item": chosen_item,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
            })
            logger.info(
                "[%s] 生成推文 (%d chars) | tokens in=%d out=%d",
                category.value,
                len(tweet_text),
                usage["input_tokens"],
                usage["output_tokens"],
            )
        except (TweetGenerationError, json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error("生成推文失败 [%s]: %s", category.value, e)

    return results
