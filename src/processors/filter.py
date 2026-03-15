"""
内容过滤、去重、排序
"""
import hashlib
import logging
from pathlib import Path

from src.config import settings
from src.models.news_item import Category, NewsItem

logger = logging.getLogger(__name__)

# 已发布内容的指纹缓存文件
_CACHE_FILE = settings.cache_path / "published_hashes.txt"


def _fingerprint(item: NewsItem) -> str:
    """用标题生成稳定指纹，避免相同新闻重复发布"""
    normalized = item.title.lower().strip()
    return hashlib.sha1(normalized.encode()).hexdigest()


def _load_published() -> set[str]:
    if not _CACHE_FILE.exists():
        return set()
    return set(_CACHE_FILE.read_text(encoding="utf-8").splitlines())


def mark_published(item: NewsItem) -> None:
    """将条目指纹写入缓存，下次运行时跳过"""
    settings.cache_path.mkdir(parents=True, exist_ok=True)
    with _CACHE_FILE.open("a", encoding="utf-8") as f:
        f.write(_fingerprint(item) + "\n")


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
