"""
RSS 源抓取器
用 httpx 异步获取内容，feedparser 解析 Atom/RSS
"""
import asyncio
import logging

import feedparser
import httpx

from src.models.news_item import Category, NewsItem

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0

_POLITICS_KEYWORDS = {
    "government", "president", "election", "war", "military",
    "nato", "policy", "regulation", "sanctions", "tariff",
    "china", "russia", "ukraine", "geopolit",
}

DEFAULT_RSS_FEEDS: list[str] = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
]


def _classify(title: str) -> Category:
    lower = title.lower()
    for kw in _POLITICS_KEYWORDS:
        if kw in lower:
            return Category.POLITICS
    return Category.TECH


async def _fetch_feed(url: str, limit: int) -> list[NewsItem]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=_TIMEOUT, follow_redirects=True)
            resp.raise_for_status()
            content = resp.text
    except Exception as e:
        logger.warning("RSS: 获取 %s 失败: %s", url, e)
        return []

    try:
        feed = feedparser.parse(content)
    except Exception as e:
        logger.warning("RSS: 解析 %s 失败: %s", url, e)
        return []

    feed_title = feed.feed.get("title", url)
    items: list[NewsItem] = []
    for entry in feed.entries[:limit]:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if not title or not link:
            continue
        items.append(
            NewsItem(
                title=title,
                url=link,
                source=f"rss/{feed_title}",
                category=_classify(title),
                score=0,
            )
        )

    logger.debug("RSS [%s]: 解析 %d 条", feed_title, len(items))
    return items


async def fetch_rss_feeds(
    feeds: list[str] | None = None,
    limit_per_feed: int = 5,
) -> list[NewsItem]:
    """并发抓取所有 RSS 源，返回合并后的列表"""
    from src.config import settings

    urls = feeds or getattr(settings, "rss_feeds", DEFAULT_RSS_FEEDS)
    tasks = [_fetch_feed(url, limit_per_feed) for url in urls]
    results = await asyncio.gather(*tasks)

    all_items: list[NewsItem] = []
    for items in results:
        all_items.extend(items)

    logger.info("RSS: 共抓取 %d 条内容（%d 个源）", len(all_items), len(urls))
    return all_items
