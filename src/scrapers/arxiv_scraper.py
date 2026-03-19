"""
arXiv 论文抓取器
使用 arXiv Atom API（无需认证）
https://export.arxiv.org/api/query
"""
import logging
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

_ARXIV_API = "https://export.arxiv.org/api/query"
_TIMEOUT = 30.0
_NS = {"atom": "http://www.w3.org/2005/Atom"}


async def fetch_arxiv_papers(
    query: str | None = None,
    limit: int = 10,
) -> list:
    """
    获取 arXiv 最新论文，返回 list[NewsItem]。
    默认查询 CS.AI / CS.LG / CS.CL 方向。
    """
    from src.config import settings
    from src.models.news_item import Category, NewsItem

    q = query or settings.arxiv_query
    params = {
        "search_query": q,
        "max_results": limit,
        "sortBy": "lastUpdatedDate",
        "sortOrder": "descending",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(_ARXIV_API, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
    except Exception as e:
        logger.error("arXiv: 请求失败: %s", e)
        return []

    try:
        root = ElementTree.fromstring(resp.text)
        entries = root.findall("atom:entry", _NS)
    except Exception as e:
        logger.error("arXiv: XML 解析失败: %s", e)
        return []

    items: list[NewsItem] = []
    for entry in entries:
        title_el = entry.find("atom:title", _NS)
        id_el = entry.find("atom:id", _NS)
        if title_el is None or id_el is None:
            continue
        title = " ".join(title_el.text.split())  # 去除多余空白换行
        url = id_el.text.strip()
        if not title:
            continue
        items.append(
            NewsItem(
                title=title,
                url=url,
                source="arxiv",
                category=Category.TECH,
                score=0,  # arXiv 无热度分，由 Analyst 判断价值
            )
        )

    logger.info("arXiv: 抓取 %d 篇论文", len(items))
    return items
