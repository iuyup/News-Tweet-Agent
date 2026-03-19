"""
SQLite 持久化层单元测试
使用 tmp_path 隔离，不污染生产数据库
"""
import pytest
from datetime import datetime
from unittest.mock import patch


def _patch_db_path(tmp_path):
    """将 _DB_PATH 指向临时目录"""
    db_file = tmp_path / "tweet_history.db"
    return patch("src.storage.db._DB_PATH", db_file)


# ── init_db ───────────────────────────────────────────────────────────────────

class TestInitDb:
    def test_creates_table(self, tmp_path):
        import sqlite3
        with _patch_db_path(tmp_path), patch("src.storage.db.settings") as mock_settings:
            mock_settings.cache_path = tmp_path
            from src.storage import db
            db.init_db()

        conn = sqlite3.connect(str(tmp_path / "tweet_history.db"))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "tweet_history" in tables

    def test_idempotent(self, tmp_path):
        with _patch_db_path(tmp_path), patch("src.storage.db.settings") as mock_settings:
            mock_settings.cache_path = tmp_path
            from src.storage import db
            db.init_db()
            db.init_db()  # 第二次不应报错

    def test_migrates_txt(self, tmp_path):
        # 写入旧 txt 文件
        txt = tmp_path / "published_hashes.txt"
        txt.write_text("aaa\nbbb\nccc\n", encoding="utf-8")

        with _patch_db_path(tmp_path), patch("src.storage.db.settings") as mock_settings:
            mock_settings.cache_path = tmp_path
            from src.storage import db
            db.init_db()
            fps = db.load_published_fingerprints()

        assert "aaa" in fps
        assert "bbb" in fps
        assert not txt.exists()
        assert (tmp_path / "published_hashes.txt.bak").exists()


# ── save_tweet / load_published_fingerprints ──────────────────────────────────

class TestSaveAndLoad:
    def _init(self, tmp_path):
        with _patch_db_path(tmp_path), patch("src.storage.db.settings") as mock_settings:
            mock_settings.cache_path = tmp_path
            from src.storage import db
            db.init_db()
        return tmp_path / "tweet_history.db"

    def test_save_and_load(self, tmp_path):
        db_file = self._init(tmp_path)
        with _patch_db_path(tmp_path):
            from src.storage import db
            db.save_tweet(
                fingerprint="fp1",
                tweet_id="tid1",
                tweet="Hello world #Test",
                news_title="Test Headline",
                source="hackernews",
                category="TECH",
                published_at=datetime.now().isoformat(),
                input_tokens=100,
                output_tokens=50,
                is_published=True,
            )
            fps = db.load_published_fingerprints()

        assert "fp1" in fps

    def test_dry_run_not_in_published(self, tmp_path):
        self._init(tmp_path)
        with _patch_db_path(tmp_path):
            from src.storage import db
            db.save_tweet(
                fingerprint="fp_dry",
                tweet_id=None,
                tweet="Dry run tweet",
                news_title="Dry Run Headline",
                source="reddit",
                category="POLITICS",
                published_at=datetime.now().isoformat(),
                is_published=False,
            )
            fps = db.load_published_fingerprints()

        assert "fp_dry" not in fps

    def test_on_conflict_update(self, tmp_path):
        """同一 fingerprint 再次 save 时应更新（不报错）"""
        self._init(tmp_path)
        with _patch_db_path(tmp_path):
            from src.storage import db
            db.save_tweet(
                fingerprint="fp_dup",
                tweet_id=None,
                tweet="",
                news_title="Title",
                source="reddit",
                category="TECH",
                published_at=datetime.now().isoformat(),
                is_published=True,
            )
            db.save_tweet(
                fingerprint="fp_dup",
                tweet_id="real_id",
                tweet="Real tweet text",
                news_title="Title",
                source="reddit",
                category="TECH",
                published_at=datetime.now().isoformat(),
                input_tokens=200,
                output_tokens=80,
                is_published=True,
            )
            fps = db.load_published_fingerprints()

        assert "fp_dup" in fps


# ── get_recent_tweets ─────────────────────────────────────────────────────────

class TestGetRecentTweets:
    def test_returns_recent(self, tmp_path):
        with _patch_db_path(tmp_path), patch("src.storage.db.settings") as mock_settings:
            mock_settings.cache_path = tmp_path
            from src.storage import db
            db.init_db()
            db.save_tweet(
                fingerprint="fp_r1",
                tweet_id="t1",
                tweet="Tweet one",
                news_title="Headline one",
                source="reddit",
                category="TECH",
                published_at=datetime.now().isoformat(),
                is_published=True,
            )
            recent = db.get_recent_tweets(days=7)

        assert len(recent) == 1
        assert recent[0]["tweet"] == "Tweet one"


# ── get_stats ─────────────────────────────────────────────────────────────────

class TestGetStats:
    def test_stats_empty(self, tmp_path):
        with _patch_db_path(tmp_path), patch("src.storage.db.settings") as mock_settings:
            mock_settings.cache_path = tmp_path
            from src.storage import db
            db.init_db()
            stats = db.get_stats()

        assert stats["total"] == 0
        assert stats["today"] == 0
        assert stats["total_input_tokens"] == 0

    def test_stats_with_data(self, tmp_path):
        with _patch_db_path(tmp_path), patch("src.storage.db.settings") as mock_settings:
            mock_settings.cache_path = tmp_path
            from src.storage import db
            db.init_db()
            db.save_tweet(
                fingerprint="stat1",
                tweet_id="t1",
                tweet="Tweet",
                news_title="Headline",
                source="hackernews",
                category="TECH",
                published_at=datetime.now().isoformat(),
                input_tokens=300,
                output_tokens=100,
                is_published=True,
            )
            stats = db.get_stats()

        assert stats["total"] == 1
        assert stats["today"] == 1
        assert stats["total_input_tokens"] == 300
        assert stats["total_output_tokens"] == 100
