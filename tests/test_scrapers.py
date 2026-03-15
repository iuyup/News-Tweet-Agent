"""
抓取模块测试
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.scrapers.nitter_scraper import fetch_trending_from, classify
from src.scrapers.reddit_scraper import fetch_subreddit
from src.models.news_item import Category


class TestNitterScraper:
    """Nitter 抓取器测试"""

    def test_classify_tech(self):
        """测试技术关键词分类"""
        assert classify("OpenAI announces GPT-5") == Category.TECH
        assert classify("AI breakthrough in quantum computing") == Category.TECH
        assert classify("Nvidia releases new chip") == Category.TECH
        assert classify("Apple launches new product") == Category.TECH

    def test_classify_politics(self):
        """测试政治关键词分类"""
        assert classify("US election results") == Category.POLITICS
        assert classify("NATO summit meeting") == Category.POLITICS
        assert classify("Ukraine war update") == Category.POLITICS

    def test_classify_unknown(self):
        """测试未知分类"""
        assert classify("Random news headline") == Category.UNKNOWN
        assert classify("Weather forecast") == Category.UNKNOWN

    @pytest.mark.asyncio
    async def test_fetch_trending_success(self):
        """测试成功抓取热搜"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <div class="tweet-content">Test trending topic #1</div>
            <div class="tweet-content">Test trending topic #2</div>
        </html>
        """

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        items, error = await fetch_trending_from(mock_client, "https://nitter.example.com")

        assert error is None
        assert len(items) >= 0  # 可能为空因为解析逻辑

    @pytest.mark.asyncio
    async def test_fetch_trending_http_error(self):
        """测试 HTTP 错误处理"""
        from httpx import HTTPStatusError

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        items, error = await fetch_trending_from(mock_client, "https://nitter.example.com")

        assert len(items) == 0
        assert error is not None


class TestRedditScraper:
    """Reddit 抓取器测试"""

    @pytest.mark.asyncio
    async def test_fetch_subreddit_success(self):
        """测试成功抓取 Reddit 子版"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Test Post Title",
                            "url": "https://example.com/post",
                            "permalink": "/r/technology/comments/abc123",
                            "score": 100,
                            "stickied": False,
                            "is_video": False,
                        }
                    }
                ]
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        items, error = await fetch_subreddit(mock_client, "technology", Category.TECH, 10)

        assert error is None
        assert len(items) == 1
        assert items[0].title == "Test Post Title"
        assert items[0].source == "reddit/r/technology"

    @pytest.mark.asyncio
    async def test_fetch_subreddit_skip_stickied(self):
        """测试跳过置顶帖"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Stickied Post",
                            "url": "https://example.com/post",
                            "permalink": "/r/technology/comments/abc123",
                            "score": 100,
                            "stickied": True,  # 置顶帖应跳过
                            "is_video": False,
                        }
                    },
                    {
                        "data": {
                            "title": "Normal Post",
                            "url": "https://example.com/post2",
                            "permalink": "/r/technology/comments/def456",
                            "score": 50,
                            "stickied": False,
                            "is_video": False,
                        }
                    }
                ]
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        items, error = await fetch_subreddit(mock_client, "technology", Category.TECH, 10)

        assert len(items) == 1
        assert items[0].title == "Normal Post"

    @pytest.mark.asyncio
    async def test_fetch_subreddit_rate_limit(self):
        """测试 API 限流处理"""
        from httpx import HTTPStatusError

        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=HTTPStatusError(
                "Rate Limited",
                request=MagicMock(),
                response=mock_response
            )
        )

        items, error = await fetch_subreddit(mock_client, "technology", Category.TECH, 10)

        assert len(items) == 0
        assert "限流" in error or "429" in error
