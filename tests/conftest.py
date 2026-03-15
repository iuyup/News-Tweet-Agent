"""
pytest 配置和共享 fixtures
"""
import pytest
from datetime import datetime
from src.models.news_item import Category, NewsItem


@pytest.fixture
def sample_news_items():
    """样例新闻条目"""
    return [
        NewsItem(
            title="OpenAI announces GPT-5 with breakthrough capabilities",
            url="https://example.com/1",
            source="reddit/r/technology",
            category=Category.TECH,
            score=1000,
            fetched_at=datetime.utcnow(),
        ),
        NewsItem(
            title="US and China reach new trade agreement",
            url="https://example.com/2",
            source="reddit/r/worldnews",
            category=Category.POLITICS,
            score=800,
            fetched_at=datetime.utcnow(),
        ),
        NewsItem(
            title="AI startup raises $1 billion",
            url="https://example.com/3",
            source="nitter",
            category=Category.TECH,
            score=500,
            fetched_at=datetime.utcnow(),
        ),
        NewsItem(
            title="Short",  # 会被过滤 - 太短
            url="https://example.com/4",
            source="reddit/r/test",
            category=Category.TECH,
            score=100,
            fetched_at=datetime.utcnow(),
        ),
        NewsItem(
            title="Unknown topic without keywords",
            url="https://example.com/5",
            source="reddit/r/test",
            category=Category.UNKNOWN,
            score=50,
            fetched_at=datetime.utcnow(),
        ),
    ]
