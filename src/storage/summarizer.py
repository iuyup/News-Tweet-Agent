"""
LLM 每日总结生成模块
"""
import asyncio
import json
import logging

import anthropic

from src.config import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 2.0


async def _call_claude_summary(prompt: str) -> tuple[str, anthropic.types.Usage]:
    """向 Claude 发送请求生成每日总结"""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
                elif hasattr(block, "thinking"):
                    logger.debug("Claude 扩展思考: %s", block.thinking[:100])
            raw_text = "".join(text_parts)
            return raw_text, response.usage
        except anthropic.RateLimitError as e:
            delay = _BASE_DELAY ** (attempt + 1)
            logger.warning("Rate limit，%.1f 秒后重试（%d/%d）", delay, attempt + 1, _MAX_RETRIES)
            await asyncio.sleep(delay)
        except anthropic.APIError as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            await asyncio.sleep(_BASE_DELAY)

    raise Exception("超过最大重试次数")


async def generate_daily_summary(news_items: list, tweets: list[dict]) -> str:
    """
    调用 LLM 生成每日新闻摘要

    Args:
        news_items: 抓取的新闻列表
        tweets: 生成的推文列表

    Returns:
        200-300 字的新闻摘要
    """
    if not news_items:
        return "今日无抓取数据"

    # 构建新闻列表摘要
    politics = [n for n in news_items if n.category.value == "politics"]
    tech = [n for n in news_items if n.category.value == "tech"]

    news_summary = []
    if politics:
        news_summary.append("时政热点：")
        for n in politics[:5]:
            news_summary.append(f"- {n.title} (评分: {n.score})")
    if tech:
        news_summary.append("科技热点：")
        for n in tech[:5]:
            news_summary.append(f"- {n.title} (评分: {n.score})")

    # 推文摘要
    tweet_summary = []
    for i, t in enumerate(tweets, 1):
        tweet_summary.append(f"- 推文{i}: {t['tweet'][:100]}...")

    prompt = f"""你是一个新闻分析师。请根据以下今日抓取的新闻和发布的推文，写一段 200-300 字的新闻摘要。

要求：
1. 概述当日最主要的热点话题
2. 分析这些话题的趋势或影响
3. 简洁客观，适合英文受众

## 今日抓取的新闻
{chr(10).join(news_summary)}

## 发布的推文
{chr(10).join(tweet_summary)}

请直接输出摘要内容，不要使用 JSON 格式，不要添加额外解释。"""

    try:
        summary, usage = await _call_claude_summary(prompt)
        logger.info(
            "每日总结生成完成 | tokens in=%d out=%d",
            usage.input_tokens,
            usage.output_tokens,
        )
        return summary.strip()
    except Exception as e:
        logger.error("生成每日总结失败: %s", e)
        return "每日总结生成失败"
