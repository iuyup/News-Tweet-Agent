"""
LLM 每日总结生成模块
"""
import logging

from src.agent._llm_call import call_default_llm_with_usage

logger = logging.getLogger(__name__)


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
        summary, usage = await call_default_llm_with_usage(prompt, max_tokens=1024)
        logger.info(
            "每日总结生成完成 | tokens in=%d out=%d",
            usage["input_tokens"],
            usage["output_tokens"],
        )
        return summary.strip()
    except Exception as e:
        logger.error("生成每日总结失败: %s", e)
        return "每日总结生成失败"
