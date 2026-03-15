"""
每日自动化工作流
抓取 → 过滤 → 生成 → 发布 → 日志
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, TypeVar

from src.config import settings
from src.generator import generate_tweets
from src.processors import deduplicate, filter_and_rank
from src.publisher import publish_tweet
from src.scrapers.nitter_scraper import fetch_nitter_trending
from src.scrapers.reddit_scraper import fetch_reddit_hot
from src.processors.filter import mark_published
from src.storage.daily_md import write_daily_md, update_daily_md_incremental
from src.storage.summarizer import generate_daily_summary

logger = logging.getLogger(__name__)

T = TypeVar("T")


def async_retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """异步重试装饰器，支持指数退避"""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        wait_time = delay * (backoff ** (attempt - 1))
                        logger.warning(
                            "%s 失败 (尝试 %d/%d): %s，%.1f 秒后重试...",
                            func.__name__, attempt, max_attempts, e, wait_time
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error("%s 失败 (已重试 %d 次): %s", func.__name__, max_attempts, e)
            raise last_exception
        return wrapper
    return decorator


@async_retry(max_attempts=2, delay=2.0, backoff=2.0)
async def fetch_with_retry() -> tuple[list, list]:
    """带重试的抓取任务"""
    reddit_items, nitter_items = await asyncio.gather(
        fetch_reddit_hot(limit_per_sub=settings.reddit_limit_per_sub),
        fetch_nitter_trending(),
    )
    return reddit_items, nitter_items


async def run_workflow() -> None:
    """执行完整的每日工作流"""
    run_at = datetime.now(timezone.utc)
    logger.info("=== 工作流开始 %s ===", run_at.isoformat())

    # 1. 抓取（带重试）
    try:
        reddit_items, nitter_items = await fetch_with_retry()
    except Exception as e:
        logger.error("抓取阶段全部失败: %s", e)
        return

    all_items = reddit_items + nitter_items
    logger.info("共抓取 %d 条（Reddit=%d, Nitter=%d）", len(all_items), len(reddit_items), len(nitter_items))

    # 2. 去重 + 过滤
    deduped = deduplicate(all_items)
    ranked = filter_and_rank(deduped, top_n=settings.tweets_per_run * 10)

    if not ranked:
        logger.warning("过滤后无可用条目，工作流结束")
        return

    # 3. LLM 生成推文
    tweets = await generate_tweets(ranked, count=settings.tweets_per_run)

    if not tweets:
        logger.warning("推文生成失败，工作流结束")
        return

    # 4. 发布 + 记录（增量更新 Markdown）
    log_entries = []
    for i, entry in enumerate(tweets):
        tweet_id = await publish_tweet(entry["tweet"])

        log_entry = {
            "run_at": run_at.isoformat(),
            "tweet_id": tweet_id,
            "tweet": entry["tweet"],
            "char_count": len(entry["tweet"]),
            "source": entry["news_item"].source,
            "source_sub": getattr(entry["news_item"], "subreddit", None) or getattr(entry["news_item"], "username", "unknown"),
            "headline": entry["news_item"].title,
            "category": entry["news_item"].category.value,
            "input_tokens": entry["input_tokens"],
            "output_tokens": entry["output_tokens"],
            "published": tweet_id is not None and tweet_id != "dry-run-id",
        }
        log_entries.append(log_entry)

        if log_entry["published"]:
            mark_published(entry["news_item"])

            # 增量更新 Markdown 文件
            if i == 0:
                # 第一条推文：创建初始文件
                write_daily_md(run_at, log_entries, ranked)
            else:
                # 后续推文：增量追加
                update_daily_md_incremental(run_at, log_entry, ranked)

    # 5. LLM 每日总结（追加到 Markdown 文件）
    summary = await generate_daily_summary(ranked, log_entries)
    if summary:
        # 读取现有文件，追加每日总结
        from src.storage.daily_md import get_daily_md_path
        md_file = get_daily_md_path(run_at)
        if md_file.exists():
            content = md_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            # 找到 "## 发布的推文" 位置，在其前插入每日总结
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.strip() == "## 发布的推文":
                    insert_idx = i
                    break
            new_lines = [
                "## 每日总结",
                "",
                summary,
                "",
            ]
            lines[insert_idx:insert_idx] = new_lines
            md_file.write_text("\n".join(lines), encoding="utf-8")
            from src.storage.daily_md import sync_to_target
            sync_to_target(md_file)

    # 6. 写 JSONL 日志
    _write_log(run_at, log_entries)
    logger.info("=== 工作流完成，发布 %d 条推文 ===", sum(1 for e in log_entries if e["published"]))


def _write_log(run_at: datetime, entries: list[dict]) -> None:
    settings.log_path.mkdir(parents=True, exist_ok=True)
    log_file = settings.log_path / f"{run_at.strftime('%Y-%m-%d')}.jsonl"
    with log_file.open("a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info("日志写入: %s", log_file)
