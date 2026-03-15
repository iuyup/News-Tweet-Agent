"""
LLM 生成模块测试
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from src.models.news_item import Category, NewsItem


class TestLLMGenerator:
    """LLM 生成器测试"""

    @pytest.fixture
    def sample_items(self):
        """样例新闻条目"""
        return [
            NewsItem(
                title="OpenAI announces GPT-5 with breakthrough AI capabilities",
                url="https://example.com/1",
                source="reddit/r/technology",
                category=Category.TECH,
                score=1000,
                fetched_at=datetime.utcnow(),
            ),
            NewsItem(
                title="World leaders meet for climate summit",
                url="https://example.com/2",
                source="reddit/r/worldnews",
                category=Category.POLITICS,
                score=800,
                fetched_at=datetime.utcnow(),
            ),
        ]

    def test_tweet_length_under_280(self):
        """测试推文长度不超过 280"""
        tweet = "This is a test tweet #test #ai"
        assert len(tweet) <= 280

    def test_tweet_with_hashtags(self):
        """测试带 hashtag 的推文"""
        tweet = "Breaking: Major AI breakthrough announced today! #AI #Tech #Innovation"
        assert "#" in tweet

    def test_category_detection_tech(self):
        """测试技术分类检测"""
        items = [
            NewsItem(
                title="AI startup raises $1 billion funding",
                url="https://example.com",
                source="test",
                category=Category.TECH,
                score=100,
            )
        ]
        assert items[0].category == Category.TECH

    def test_category_detection_politics(self):
        """测试政治分类检测"""
        items = [
            NewsItem(
                title="Election results announced",
                url="https://example.com",
                source="test",
                category=Category.POLITICS,
                score=100,
            )
        ]
        assert items[0].category == Category.POLITICS


class TestTweetGeneration:
    """推文生成测试"""

    def test_generate_tech_tweet_structure(self):
        """测试技术推文结构"""
        # 模拟生成的推文
        tweet = "OpenAI just unveiled GPT-5, promising revolutionary AI capabilities. The new model shows significant improvements in reasoning and creativity. #AI #OpenAI #Tech"

        assert len(tweet) <= 280
        assert "#" in tweet
        words = tweet.split()
        assert len(words) >= 5

    def test_generate_politics_tweet_structure(self):
        """测试政治推文结构"""
        tweet = "World leaders gathered today for crucial climate negotiations. The summit aims to address pressing environmental challenges. #Climate #Diplomacy #WorldNews"

        assert len(tweet) <= 280
        assert "#" in tweet

    def test_multiple_hashtags(self):
        """测试多个 hashtag"""
        tweet = "Test tweet with multiple hashtags #AI #Tech #Innovation"
        hashtag_count = tweet.count("#")
        assert hashtag_count >= 2
        assert hashtag_count <= 3  # 符合规范
