"""
Publisher 节点
发布推文 → 增量更新 Markdown → 每日总结 → JSONL 日志
"""
import json
import logging
import re
from datetime import datetime

from src.config import settings
from src.processors.filter import _fingerprint, mark_published
from src.publisher import publish_tweet
from src.storage.db import save_tweet
from src.storage.daily_md import (
    get_daily_md_path,
    sync_to_target,
    update_daily_md_incremental,
    write_daily_md,
)
from src.storage.summarizer import generate_daily_summary

logger = logging.getLogger(__name__)


def _get_existing_tweet_count(run_at: datetime) -> int:
    """获取当天已发布的推文数量"""
    md_file = get_daily_md_path(run_at)
    if not md_file.exists():
        return 0
    try:
        content = md_file.read_text(encoding="utf-8")
        matches = re.findall(r"^### 推文 \d+$", content, re.MULTILINE)
        return len(matches)
    except Exception as e:
        logger.warning("读取现有推文数量失败: %s", e)
        return 0


def _write_log(run_at: datetime, entries: list[dict]) -> None:
    """写入 JSONL 日志"""
    settings.log_path.mkdir(parents=True, exist_ok=True)
    log_file = settings.log_path / f"{run_at.strftime('%Y-%m-%d')}.jsonl"
    with log_file.open("a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info("日志写入: %s", log_file)


async def publisher_node(state: dict) -> dict:
    """发布推文 + Markdown 增量更新 + 每日总结 + 日志"""
    tweets = state.get("generated_tweets", [])
    run_at = state["run_at"]
    filtered_items = state.get("filtered_items", [])

    if not tweets:
        logger.warning("Publisher: 无推文可发布")
        return {
            "publish_results": [],
            "error_log": ["Publisher: generated_tweets 为空，跳过"],
        }

    # 获取当天已发布推文数
    existing_count = _get_existing_tweet_count(run_at)
    logger.info("Publisher: 当天已发布 %d 条推文", existing_count)

    log_entries: list[dict] = []
    publish_results: list[dict] = []

    for i, entry in enumerate(tweets):
        tweet_id = await publish_tweet(entry["tweet"])

        log_entry = {
            "run_at": run_at.isoformat(),
            "tweet_id": tweet_id,
            "tweet": entry["tweet"],
            "char_count": len(entry["tweet"]),
            "source": entry["news_item"].source,
            "source_sub": entry["news_item"].subreddit
            or entry["news_item"].username
            or "unknown",
            "headline": entry["news_item"].title,
            "category": entry["news_item"].category.value,
            "input_tokens": entry["input_tokens"],
            "output_tokens": entry["output_tokens"],
            "published": tweet_id is not None and tweet_id != "dry-run-id",
        }
        log_entries.append(log_entry)

        if log_entry["published"]:
            # 写入完整推文记录到 SQLite（ON CONFLICT UPDATE 覆盖 mark_published 的最小记录）
            save_tweet(
                fingerprint=_fingerprint(entry["news_item"]),
                tweet_id=tweet_id,
                tweet=entry["tweet"],
                news_title=entry["news_item"].title,
                source=entry["news_item"].source,
                category=entry["news_item"].category.value,
                published_at=run_at.isoformat(),
                input_tokens=entry["input_tokens"],
                output_tokens=entry["output_tokens"],
                is_published=True,
            )
            mark_published(entry["news_item"])

            # 增量更新 Markdown
            if existing_count == 0 and i == 0:
                write_daily_md(run_at, log_entries, filtered_items)
            else:
                update_daily_md_incremental(run_at, log_entry, filtered_items)

        publish_results.append({
            "tweet_id": tweet_id,
            "published": log_entry["published"],
            "tweet": entry["tweet"][:80],
        })

    # 每日总结
    md_file = get_daily_md_path(run_at)
    has_summary = False
    if md_file.exists():
        content = md_file.read_text(encoding="utf-8")
        has_summary = "## 每日总结" in content

    if not has_summary:
        summary = await generate_daily_summary(filtered_items, log_entries)
        if summary and md_file.exists():
            content = md_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            insert_idx = 0
            found = False
            for idx, line in enumerate(lines):
                if line.strip() == "## 每日总结":
                    insert_idx = idx
                    found = True
                    break

            if not found:
                for idx, line in enumerate(lines):
                    if line.strip() == "## 发布的推文":
                        insert_idx = idx
                        break

            new_lines = ["## 每日总结", "", summary, ""]
            lines[insert_idx:insert_idx] = new_lines
            md_file.write_text("\n".join(lines), encoding="utf-8")
            sync_to_target(md_file)
            logger.info("已添加每日总结到 Markdown")

    # JSONL 日志
    _write_log(run_at, log_entries)

    published_count = sum(1 for e in log_entries if e["published"])
    logger.info("Publisher: 发布 %d 条推文", published_count)

    return {"publish_results": publish_results}
