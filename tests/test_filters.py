"""
过滤模块测试
"""
import pytest
from src.processors.filter import deduplicate, filter_and_rank, mark_published
from src.models.news_item import Category, NewsItem
from datetime import datetime


class TestDeduplicate:
    """去重功能测试"""

    def test_deduplicate_unique(self, sample_news_items):
        """测试无重复时保留所有条目"""
        result = deduplicate(sample_news_items)
        assert len(result) == len(sample_news_items)

    def test_deduplicate_same_title(self, sample_news_items):
        """测试相同标题去重"""
        items = sample_news_items[:2]
        # 添加一个重复标题
        items.append(NewsItem(
            title=items[0].title,  # 与第一个相同
            url="https://example.com/dup",
            source="test",
            category=Category.TECH,
            score=100,
            fetched_at=datetime.utcnow(),
        ))

        result = deduplicate(items)
        assert len(result) == 2

    def test_deduplicate_case_insensitive(self, sample_news_items):
        """测试大小写不敏感去重"""
        items = [sample_news_items[0]]
        items.append(NewsItem(
            title=items[0].title.upper(),  # 大小写不同
            url="https://example.com/dup",
            source="test",
            category=Category.TECH,
            score=100,
            fetched_at=datetime.utcnow(),
        ))

        result = deduplicate(items)
        assert len(result) == 1


class TestFilterAndRank:
    """过滤和排序功能测试"""

    def test_filter_and_rank_all(self, sample_news_items):
        """测试返回所有分类"""
        result = filter_and_rank(sample_news_items)
        # 应该过滤掉 UNKNOWN 和太短的
        for item in result:
            assert item.category != Category.UNKNOWN
            assert len(item.title) >= 10

    def test_filter_by_category(self, sample_news_items):
        """测试按分类过滤"""
        result = filter_and_rank(sample_news_items, category=Category.TECH)
        assert all(item.category == Category.TECH for item in result)

    def test_filter_top_n(self, sample_news_items):
        """测试返回前 N 条"""
        result = filter_and_rank(sample_news_items, top_n=2)
        assert len(result) == 2

    def test_filter_sorted_by_score(self, sample_news_items):
        """测试按分数降序排序"""
        result = filter_and_rank(sample_news_items, top_n=10)
        scores = [item.score for item in result]
        assert scores == sorted(scores, reverse=True)

    def test_filter_removes_unknown(self, sample_news_items):
        """测试移除 UNKNOWN 分类"""
        result = filter_and_rank(sample_news_items)
        titles = [item.title for item in result]
        assert "Unknown topic without keywords" not in titles

    def test_filter_removes_short(self, sample_news_items):
        """测试移除过短标题"""
        result = filter_and_rank(sample_news_items)
        titles = [item.title for item in result]
        assert "Short" not in titles


class TestMarkPublished:
    """标记已发布功能测试"""

    def test_mark_published_creates_file(self, tmp_path, monkeypatch):
        """测试标记后创建缓存文件"""
        from src.config import settings
        from src.processors import filter as filter_module

        # 临时修改缓存路径
        monkeypatch.setattr(filter_module, "_CACHE_FILE", tmp_path / "test_hashes.txt")

        item = NewsItem(
            title="Test Title",
            url="https://example.com",
            source="test",
            category=Category.TECH,
            score=100,
        )

        mark_published(item)

        cache_file = tmp_path / "test_hashes.txt"
        assert cache_file.exists()
        content = cache_file.read_text()
        assert len(content) > 0
