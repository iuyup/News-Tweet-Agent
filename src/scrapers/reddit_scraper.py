"""
Reddit 热帖抓取器
使用 reddit.com/r/{subreddit}/hot.json 无需认证
"""
import logging
from typing import Any, Optional

import httpx
from httpx import HTTPError, HTTPStatusError, TimeoutException

from src.models.news_item import Category, NewsItem

logger = logging.getLogger(__name__)

# 目标 subreddit 及其分类
SUBREDDITS: dict[str, Category] = {
    "worldnews": Category.POLITICS,
    "geopolitics": Category.POLITICS,
    "politics": Category.POLITICS,
    "technology": Category.TECH,
    "artificial": Category.TECH,
    "MachineLearning": Category.TECH,
    "singularity": Category.TECH,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def fetch_subreddit(
    client: httpx.AsyncClient,
    subreddit: str,
    category: Category,
    limit: int = 10,
) -> tuple[list[NewsItem], Optional[str]]:
    """抓取单个 subreddit 的热帖，返回 (items, error_msg)"""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    error_msg: Optional[str] = None

    try:
        resp = await client.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        posts: list[dict[str, Any]] = data.get("data", {}).get("children", [])
    except TimeoutException as e:
        error_msg = f"请求超时: {e}"
        logger.warning("抓取 r/%s 失败: %s", subreddit, error_msg)
        return [], error_msg
    except HTTPStatusError as e:
        if e.response.status_code == 429:
            error_msg = f"API 限流 (429)"
        elif e.response.status_code == 403:
            error_msg = f"禁止访问 (403)"
        elif e.response.status_code == 404:
            error_msg = f"子版不存在 (404)"
        else:
            error_msg = f"HTTP {e.response.status_code}"
        logger.warning("抓取 r/%s 失败: %s", subreddit, error_msg)
        return [], error_msg
    except HTTPError as e:
        error_msg = f"网络错误: {e}"
        logger.warning("抓取 r/%s 失败: %s", subreddit, error_msg)
        return [], error_msg
    except Exception as e:
        error_msg = f"未知错误: {type(e).__name__}: {e}"
        logger.warning("抓取 r/%s 失败: %s", subreddit, error_msg)
        return [], error_msg

    items: list[NewsItem] = []
    for post in posts:
        data = post.get("data", {})
        # 跳过置顶帖和媒体帖（无外链价值）
        if data.get("stickied") or data.get("is_video"):
            continue
        items.append(
            NewsItem(
                title=data.get("title", ""),
                url=data.get("url", f"https://reddit.com{data.get('permalink', '')}"),
                source=f"reddit/r/{subreddit}",
                category=category,
                score=data.get("score", 0),
            )
        )

    return items, None


async def fetch_reddit_hot(limit_per_sub: int = 10) -> list[NewsItem]:
    """并发抓取所有目标 subreddit，返回合并后的热帖列表（按热度降序）"""
    import asyncio

    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_subreddit(client, sub, cat, limit_per_sub)
            for sub, cat in SUBREDDITS.items()
        ]
        results = await asyncio.gather(*tasks)

    all_items: list[NewsItem] = []
    failed_subs: list[tuple[str, str]] = []

    for (sub, cat), (items, error) in zip(SUBREDDITS.items(), results):
        if items:
            all_items.extend(items)
        if error:
            failed_subs.append((sub, error))

    all_items.sort(key=lambda x: x.score, reverse=True)

    # 记录失败情况
    if failed_subs:
        error_summary = "; ".join(f"r/{sub}: {err}" for sub, err in failed_subs)
        logger.warning("Reddit 部分子版抓取失败: %s", error_summary)

    logger.info("Reddit 共抓取 %d 条热帖（%d/%d 子版成功）",
                len(all_items), len(SUBREDDITS) - len(failed_subs), len(SUBREDDITS))
    return all_items
