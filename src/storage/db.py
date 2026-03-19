"""
SQLite 持久化层
存储推文发布历史，替代 published_hashes.txt 文本缓存

表结构: tweet_history
  - fingerprint: SHA1(normalized_title)，唯一键，用于去重
  - tweet_id:    Twitter 推文 ID（dry-run 时为 NULL）
  - tweet:       推文正文
  - news_title:  原始新闻标题
  - source:      来源（reddit/hackernews/arxiv/rss）
  - category:    POLITICS / TECH
  - published_at: ISO 时间戳
  - input_tokens / output_tokens: LLM token 用量
  - is_published: 1=已发布, 0=dry-run/失败
"""
import logging
import sqlite3
from datetime import datetime, timedelta

from src.config import settings

logger = logging.getLogger(__name__)

_DB_PATH = settings.cache_path / "tweet_history.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_table() -> None:
    """建表（幂等）。所有 DB 操作前调用，无需显式 init_db()。"""
    settings.cache_path.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tweet_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint   TEXT    NOT NULL UNIQUE,
                tweet_id      TEXT,
                tweet         TEXT    NOT NULL DEFAULT '',
                news_title    TEXT    NOT NULL DEFAULT '',
                source        TEXT    NOT NULL DEFAULT '',
                category      TEXT    NOT NULL DEFAULT '',
                published_at  TEXT    NOT NULL,
                input_tokens  INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                is_published  INTEGER DEFAULT 0
            )
        """)
        conn.commit()


def init_db() -> None:
    """启动时调用：建表 + 迁移旧 txt 缓存（幂等）"""
    _ensure_table()
    _migrate_txt_to_db()


def _migrate_txt_to_db() -> None:
    """一次性将 published_hashes.txt 中的指纹迁移到 SQLite，成功后备份原文件"""
    old_path = settings.cache_path / "published_hashes.txt"
    if not old_path.exists():
        return

    lines = [l.strip() for l in old_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return

    now_iso = datetime.now().isoformat()
    with _connect() as conn:
        existing = {row[0] for row in conn.execute("SELECT fingerprint FROM tweet_history")}
        new_rows = [(fp, now_iso) for fp in lines if fp not in existing]
        if new_rows:
            conn.executemany(
                """INSERT OR IGNORE INTO tweet_history
                   (fingerprint, tweet, news_title, source, category, published_at, is_published)
                   VALUES (?, '[migrated]', '[migrated]', 'unknown', 'unknown', ?, 1)""",
                new_rows,
            )
            conn.commit()
            logger.info("DB迁移: %d 条旧记录已导入 SQLite", len(new_rows))

    bak_path = old_path.with_suffix(".txt.bak")
    if bak_path.exists():
        old_path.unlink()
        logger.info("DB迁移: .bak 已存在，直接删除旧缓存文件")
    else:
        old_path.rename(bak_path)
        logger.info("DB迁移: 旧缓存已备份为 published_hashes.txt.bak")


def load_published_fingerprints() -> set[str]:
    """返回所有已发布内容的指纹集合（用于 filter.py 去重）"""
    _ensure_table()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT fingerprint FROM tweet_history WHERE is_published = 1"
        ).fetchall()
    return {row[0] for row in rows}


def save_tweet(
    *,
    fingerprint: str,
    tweet_id: str | None,
    tweet: str,
    news_title: str,
    source: str,
    category: str,
    published_at: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    is_published: bool = True,
) -> None:
    """插入或更新推文记录（以 fingerprint 为唯一键，重复时更新完整字段）"""
    _ensure_table()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO tweet_history
               (fingerprint, tweet_id, tweet, news_title, source, category,
                published_at, input_tokens, output_tokens, is_published)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(fingerprint) DO UPDATE SET
                   tweet_id      = excluded.tweet_id,
                   tweet         = excluded.tweet,
                   news_title    = excluded.news_title,
                   source        = excluded.source,
                   category      = excluded.category,
                   published_at  = excluded.published_at,
                   input_tokens  = excluded.input_tokens,
                   output_tokens = excluded.output_tokens,
                   is_published  = excluded.is_published""",
            (fingerprint, tweet_id, tweet, news_title, source, category,
             published_at, input_tokens, output_tokens, int(is_published)),
        )
        conn.commit()


def get_recent_tweets(days: int = 7) -> list[dict]:
    """获取最近 N 天已发布推文列表（供 Analyst 节点作去重上下文）"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT tweet, news_title, category, published_at
               FROM tweet_history
               WHERE is_published = 1 AND published_at >= ?
               ORDER BY published_at DESC
               LIMIT 50""",
            (cutoff,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_stats() -> dict:
    """返回发布统计汇总"""
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM tweet_history WHERE is_published = 1"
        ).fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM tweet_history WHERE is_published = 1 AND published_at LIKE ?",
            (f"{today_prefix}%",),
        ).fetchone()[0]
        row = conn.execute(
            """SELECT COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0)
               FROM tweet_history WHERE is_published = 1"""
        ).fetchone()
    return {
        "total": total,
        "today": today,
        "total_input_tokens": row[0],
        "total_output_tokens": row[1],
    }
