"""
工作流测试
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from src.models.news_item import Category, NewsItem


class TestWorkflow:
    """工作流测试"""

    def test_async_retry_decorator(self):
        """测试重试装饰器"""
        from src.scheduler.workflow import async_retry

        call_count = 0

        @async_retry(max_attempts=3, delay=0.01)
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"

        import asyncio
        result = asyncio.run(failing_func())
        assert result == "success"
        assert call_count == 2

    def test_async_retry_exhausted(self):
        """测试重试耗尽"""
        from src.scheduler.workflow import async_retry

        call_count = 0

        @async_retry(max_attempts=3, delay=0.01)
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent error")

        import asyncio
        with pytest.raises(ValueError):
            asyncio.run(always_failing())

        assert call_count == 3

    def test_workflow_stages_present(self):
        """测试工作流各阶段"""
        # 验证 workflow.py 包含必要的导入
        from src.scheduler import workflow
        assert hasattr(workflow, "run_workflow")
        assert hasattr(workflow, "fetch_with_retry")
        assert hasattr(workflow, "async_retry")


class TestDataModels:
    """数据模型测试"""

    def test_news_item_creation(self):
        """测试 NewsItem 创建"""
        item = NewsItem(
            title="Test Title",
            url="https://example.com",
            source="test",
            category=Category.TECH,
            score=100,
        )
        assert item.title == "Test Title"
        assert item.category == Category.TECH

    def test_news_item_default_score(self):
        """测试默认分数"""
        item = NewsItem(
            title="Test",
            url="https://example.com",
            source="test",
            category=Category.TECH,
        )
        assert item.score == 0

    def test_news_item_default_fetched_at(self):
        """测试默认抓取时间"""
        before = datetime.utcnow()
        item = NewsItem(
            title="Test",
            url="https://example.com",
            source="test",
            category=Category.TECH,
        )
        after = datetime.utcnow()
        assert before <= item.fetched_at <= after

    def test_category_enum(self):
        """测试分类枚举"""
        assert Category.POLITICS.value == "politics"
        assert Category.TECH.value == "tech"
        assert Category.UNKNOWN.value == "unknown"
