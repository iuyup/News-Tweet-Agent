"""
内容过滤、去重、排序
"""
import hashlib
import logging
from datetime import datetime

from src.models.news_item import Category, NewsItem

logger = logging.getLogger(__name__)


def _fingerprint(item: NewsItem) -> str:
    """用标题生成稳定指纹，避免相同新闻重复发布"""
    normalized = item.title.lower().strip()
    return hashlib.sha1(normalized.encode()).hexdigest()


def _load_published() -> set[str]:
    from src.storage.db import load_published_fingerprints
    return load_published_fingerprints()


def mark_published(item: NewsItem) -> None:
    """将条目指纹存入 SQLite，下次运行时跳过。
    publisher.py 会用 save_tweet() 补全完整字段；此处写入最小记录保证去重生效。
    """
    from src.storage.db import save_tweet
    save_tweet(
        fingerprint=_fingerprint(item),
        tweet_id=None,
        tweet="",
        news_title=item.title,
        source=item.source,
        category=item.category.value,
        published_at=datetime.now().isoformat(),
        is_published=True,
    )


def deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    """去除已发布内容和本批次内重复标题"""
    published = _load_published()
    seen: set[str] = set()
    result: list[NewsItem] = []

    for item in items:
        fp = _fingerprint(item)
        if fp in published:
            logger.debug("跳过已发布: %s", item.title[:50])
            continue
        if fp in seen:
            logger.debug("跳过批次内重复: %s", item.title[:50])
            continue
        seen.add(fp)
        result.append(item)

    logger.info("去重后剩余 %d / %d 条", len(result), len(items))
    return result


def filter_and_rank(
    items: list[NewsItem],
    category: Category | None = None,
    top_n: int | None = None,
) -> list[NewsItem]:
    """
    过滤 + 排序：
    - 可按分类筛选（None 表示不过滤）
    - 去除 UNKNOWN 分类（质量太低）
    - 按 score 降序，返回前 top_n 条
    """
    filtered = [
        item for item in items
        if item.category != Category.UNKNOWN
        and (category is None or item.category == category)
        and len(item.title) >= 10   # 过滤过短标题
    ]

    filtered.sort(key=lambda x: x.score, reverse=True)

    if top_n:
        filtered = filtered[:top_n]

    logger.info(
        "过滤后剩余 %d 条（category=%s）",
        len(filtered),
        category.value if category else "all",
    )
    return filtered
