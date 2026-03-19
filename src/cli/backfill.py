"""
从 JSONL 日志回填历史推文数据到 SQLite

用法：
    python -m src.cli.backfill         # 回填全部日志
    python -m src.cli.backfill --dry   # 只统计，不写入
"""
import argparse
import hashlib
import json
import logging
from pathlib import Path

from src.config import settings
from src.storage.db import init_db, save_tweet

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _fingerprint(title: str) -> str:
    return hashlib.sha1(title.lower().strip().encode()).hexdigest()


def backfill(dry_run: bool = False) -> int:
    """回填所有 JSONL 日志到 SQLite，返回写入条数"""
    init_db()
    total = 0

    log_files = sorted(settings.log_path.glob("*.jsonl"))
    if not log_files:
        print("未找到 JSONL 日志文件")
        return 0

    for log_file in log_files:
        count = 0
        with log_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if not entry.get("published"):
                    continue

                headline = entry.get("headline", "")
                if not headline:
                    continue

                if not dry_run:
                    save_tweet(
                        fingerprint=_fingerprint(headline),
                        tweet_id=entry.get("tweet_id"),
                        tweet=entry.get("tweet", ""),
                        news_title=headline,
                        source=entry.get("source", "unknown"),
                        category=entry.get("category", "unknown").upper(),
                        published_at=entry.get("run_at", ""),
                        input_tokens=entry.get("input_tokens", 0),
                        output_tokens=entry.get("output_tokens", 0),
                        is_published=True,
                    )
                count += 1

        print(f"  {log_file.name}: {count} 条{'（dry-run，未写入）' if dry_run else ''}")
        total += count

    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="JSONL → SQLite 历史数据回填")
    parser.add_argument("--dry", action="store_true", help="只统计条数，不写入数据库")
    args = parser.parse_args()

    action = "统计（dry-run）" if args.dry else "回填"
    print(f"\n开始{action} JSONL 历史数据...")
    n = backfill(dry_run=args.dry)
    print(f"\n完成：共 {n} 条已发布推文{'可回填' if args.dry else '写入 SQLite'}\n")


if __name__ == "__main__":
    main()
