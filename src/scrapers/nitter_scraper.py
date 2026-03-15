"""
Nitter 热搜抓取器
通过抓取 Nitter 公开镜像获取 Twitter/X 热搜话题
无需 API Key

注意：Nitter 实例常使用自签名证书，因此禁用 SSL 验证是必要的。
这些实例是公开的 Twitter 前端镜像，无需认证即可访问公开内容。
"""
import logging
import ssl
from urllib.parse import urljoin
from typing import Optional

import httpx
from httpx import HTTPError, TimeoutException
from bs4 import BeautifulSoup

from src.config import settings
from src.models.news_item import Category, NewsItem

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; news-bot/1.0)"
}

# 关键词分类规则（简单匹配，可按需扩展）
TECH_KEYWORDS = {
    "ai", "gpt", "llm", "openai", "anthropic", "claude", "gemini",
    "tech", "robot", "chip", "nvidia", "apple", "google", "meta",
    "cybersecurity", "quantum", "blockchain", "software", "startup",
}
POLITICS_KEYWORDS = {
    "war", "election", "president", "congress", "senate", "nato",
    "ukraine", "russia", "china", "taiwan", "sanction", "treaty",
    "minister", "parliament", "government", "policy", "vote",
}


def classify(text: str) -> Category:
    """根据关键词分类文本为技术或政治新闻"""
    lower = text.lower()
    # 按关键词长度降序排序，优先匹配较长关键词（避免 "ai" 匹配 "ukraine"）
    sorted_tech = sorted(TECH_KEYWORDS, key=len, reverse=True)
    sorted_politics = sorted(POLITICS_KEYWORDS, key=len, reverse=True)

    # 先检查 politics（因为政治新闻通常更重要）
    if any(kw in lower for kw in sorted_politics):
        return Category.POLITICS
    if any(kw in lower for kw in sorted_tech):
        return Category.TECH

    return Category.UNKNOWN


async def fetch_trending_from(
    client: httpx.AsyncClient, base_url: str
) -> tuple[list[NewsItem], Optional[str]]:
    """从单个 Nitter 实例抓取热搜话题，返回 (items, error_msg)"""
    url = f"{base_url}/search?f=tweets&q=%23trending&src=trend_click"
    # 部分实例直接提供 /trending 页面
    trending_url = f"{base_url}/trending"
    items: list[NewsItem] = []
    last_error: Optional[str] = None

    for target in (trending_url, url):
        try:
            resp = await client.get(target, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            # 尝试解析趋势话题标签
            trend_tags = soup.select(".trend-item, .trending-tag, .timeline-item .fullname")
            if not trend_tags:
                # 回退：抓取推文标题
                trend_tags = soup.select(".tweet-content, .tweet-text")

            for tag in trend_tags[:20]:
                text = tag.get_text(strip=True)
                if not text or len(text) < 5:
                    continue
                # 提取链接
                link = tag.find("a")
                href = urljoin(base_url, link["href"]) if link and link.get("href") else target

                items.append(
                    NewsItem(
                        title=text,
                        url=href,
                        source="nitter",
                        category=classify(text),
                        score=0,
                    )
                )

            if items:
                logger.info("Nitter [%s] 抓取 %d 条热搜", base_url, len(items))
                return items, None
        except TimeoutException as e:
            last_error = f"超时: {e}"
            logger.debug("Nitter [%s] 请求超时: %s", base_url, e)
        except HTTPError as e:
            last_error = f"网络错误: {e}"
            logger.debug("Nitter [%s] 网络错误: %s", base_url, e)
        except ssl.SSLError as e:
            last_error = f"SSL 错误: {e}"
            logger.debug("Nitter [%s] SSL 错误: %s", base_url, e)
        except Exception as e:
            last_error = f"未知错误: {type(e).__name__}: {e}"
            logger.warning("Nitter [%s] 意外错误: %s", base_url, e)

    return items, last_error


async def fetch_nitter_trending() -> list[NewsItem]:
    """依次尝试所有 Nitter 镜像，收集所有成功的结果"""
    # Nitter 镜像常有用自签名证书，禁用 SSL 验证是必要的
    # 这些是公开的 Twitter 前端镜像，无需认证即可访问公开内容
    logger.debug("Nitter SSL 验证已禁用（自签名证书）")

    all_items: list[NewsItem] = []
    failed_instances: list[tuple[str, str]] = []

    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        for instance in settings.nitter_instances:
            base_url = f"https://{instance}"
            items, error = await fetch_trending_from(client, base_url)
            if items:
                all_items.extend(items)
                logger.info("Nitter [%s] 成功抓取 %d 条", instance, len(items))
            else:
                failed_instances.append((instance, error or "未知错误"))
                logger.warning("Nitter [%s] 失败: %s", instance, error)

    # 按热度排序（score 降序）
    all_items.sort(key=lambda x: x.score, reverse=True)

    if all_items:
        # 去重（基于标题）
        seen = set()
        unique_items = []
        for item in all_items:
            if item.title not in seen:
                seen.add(item.title)
                unique_items.append(item)
        logger.info("Nitter 共抓取 %d 条热搜（去重后）", len(unique_items))
        return unique_items

    # 所有实例都失败时记录详细错误
    error_summary = "; ".join(f"{inst}: {err}" for inst, err in failed_instances)
    logger.warning("所有 Nitter 镜像均不可用，错误详情: %s", error_summary)
    return []
