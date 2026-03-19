"""
Hacker News 热帖抓取器
使用 HN Firebase API（无需认证）
https://hacker-news.firebaseio.com/v0/
"""
import asyncio
import logging

import httpx

from src.models.news_item import Category, NewsItem

logger = logging.getLogger(__name__)

_HN_BASE = "https://hacker-news.firebaseio.com/v0"
_TIMEOUT = 15.0

_POLITICS_KEYWORDS = {
    "government", "president", "election", "congress", "senate",
    "war", "military", "nato", "policy", "regulation", "court",
    "sanctions", "tariff", "diplomat", "china", "russia", "ukraine",
    "geopolit", "biden", "trump", "xi jinping", "putin",
}


def _classify(title: str) -> Category:
    lower = title.lower()
    for kw in _POLITICS_KEYWORDS:
        if kw in lower:
            return Category.POLITICS
    return Category.TECH


async def _fetch_story(client: httpx.AsyncClient, story_id: int) -> NewsItem | None:
    try:
        resp = await client.get(f"{_HN_BASE}/item/{story_id}.json", timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if not data or data.get("type") != "story" or not data.get("url"):
            return None
        title = data.get("title", "").strip()
        if not title:
            return None
        return NewsItem(
            title=title,
            url=data["url"],
            source="hackernews",
            category=_classify(title),
            score=data.get("score", 0),
        )
    except Exception:
        return None


async def fetch_hackernews_top(limit: int = 20) -> list[NewsItem]:
    """获取 HN top stories，返回前 limit 条（过滤无 URL 的帖子）"""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{_HN_BASE}/topstories.json", timeout=_TIMEOUT)
            resp.raise_for_status()
            story_ids: list[int] = resp.json()[: limit * 3]  # 多取，过滤后保证数量
        except Exception as e:
            logger.error("HackerNews: 获取 top stories 失败: %s", e)
            return []

        tasks = [_fetch_story(client, sid) for sid in story_ids]
        results = await asyncio.gather(*tasks)

    items = [item for item in results if item is not None]
    items.sort(key=lambda x: x.score, reverse=True)
    result = items[:limit]
    logger.info("HackerNews: 抓取 %d 条热帖", len(result))
    return result
