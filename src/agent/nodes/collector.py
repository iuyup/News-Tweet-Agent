"""
Collector 节点
根据 selected_sources 并发抓取多个信息源 → 合并去重
（过滤/选题交由 Analyst 节点处理）
"""
import asyncio
import logging

from src.models.news_item import NewsItem
from src.processors.filter import deduplicate
from src.scrapers.arxiv_scraper import fetch_arxiv_papers
from src.scrapers.hackernews_scraper import fetch_hackernews_top
from src.scrapers.reddit_scraper import fetch_reddit_hot
from src.scrapers.rss_scraper import fetch_rss_feeds

logger = logging.getLogger(__name__)


async def _fetch_reddit() -> tuple[list[NewsItem], list[str]]:
    from src.config import settings
    try:
        items = await fetch_reddit_hot(limit_per_sub=settings.reddit_limit_per_sub)
        return items, []
    except Exception as e:
        return [], [f"Reddit 抓取失败: {e}"]


async def _fetch_hackernews() -> tuple[list[NewsItem], list[str]]:
    from src.config import settings
    try:
        items = await fetch_hackernews_top(limit=settings.hackernews_limit)
        return items, []
    except Exception as e:
        return [], [f"HackerNews 抓取失败: {e}"]


async def _fetch_arxiv() -> tuple[list[NewsItem], list[str]]:
    from src.config import settings
    try:
        items = await fetch_arxiv_papers(limit=settings.arxiv_limit)
        return items, []
    except Exception as e:
        return [], [f"arXiv 抓取失败: {e}"]


async def _fetch_rss() -> tuple[list[NewsItem], list[str]]:
    from src.config import settings
    try:
        items = await fetch_rss_feeds(limit_per_feed=settings.rss_limit_per_feed)
        return items, []
    except Exception as e:
        return [], [f"RSS 抓取失败: {e}"]


_FETCHER_MAP = {
    "reddit": _fetch_reddit,
    "hackernews": _fetch_hackernews,
    "arxiv": _fetch_arxiv,
    "rss": _fetch_rss,
}


async def collector_node(state: dict) -> dict:
    """根据 selected_sources 并发抓取，合并去重写入 raw_items"""
    selected_sources: list[str] = state.get("selected_sources", ["reddit", "hackernews"])
    valid_sources = [s for s in selected_sources if s in _FETCHER_MAP]
    if not valid_sources:
        valid_sources = ["reddit"]

    tasks = [_FETCHER_MAP[s]() for s in valid_sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[NewsItem] = []
    all_errors: list[str] = []
    for source, result in zip(valid_sources, results):
        if isinstance(result, Exception):
            err = f"{source} 抓取异常: {result}"
            logger.error("Collector [%s]: %s", source, result)
            all_errors.append(err)
            continue
        items, errors = result
        all_items.extend(items)
        all_errors.extend(errors)
        if items:
            logger.info("Collector [%s]: %d 条", source, len(items))

    if all_items:
        all_items = deduplicate(all_items)

    logger.info("Collector: 去重后 %d 条原始新闻（来源: %s）", len(all_items), valid_sources)
    return {
        "raw_items": all_items,
        "scrape_errors": all_errors,
        "error_log": all_errors,
    }
