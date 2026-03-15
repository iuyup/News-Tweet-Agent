"""
命令行工具：手动保存每日推文到 Markdown
用法: python -m src.cli.save_daily 2026-03-14
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import settings
from src.storage.daily_md import write_daily_md
from src.storage.summarizer import generate_daily_summary
from src.models.news_item import Category, NewsItem


def parse_args():
    parser = argparse.ArgumentParser(description="保存每日推文到 Markdown")
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="日期 (YYYY-MM-DD)，默认为今天",
    )
    return parser.parse_args()


def load_jsonl(date: str) -> list[dict]:
    """从 JSONL 文件加载推文日志"""
    log_file = settings.log_path / f"{date}.jsonl"
    if not log_file.exists():
        raise FileNotFoundError(f"日志文件不存在: {log_file}")

    entries = []
    with log_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    return entries


def parse_news_items(entries: list[dict]) -> list[NewsItem]:
    """从日志条目中重建 NewsItem 列表"""
    seen_titles = set()
    items = []

    for entry in entries:
        if entry.get("headline") in seen_titles:
            continue
        seen_titles.add(entry.get("headline"))

        item = NewsItem(
            title=entry.get("headline", ""),
            url="",  # 日志中不保存 URL
            source=entry.get("source", "unknown"),
            category=Category(entry.get("category", "unknown")),
            score=0,
        )
        items.append(item)

    return items


async def main():
    args = parse_args()

    # 确定日期
    if args.date:
        try:
            date = datetime.strptime(args.date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            print(f"错误: 日期格式无效，应为 YYYY-MM-DD")
            sys.exit(1)
    else:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"正在保存 {date} 的每日推文...")

    # 加载日志
    try:
        log_entries = load_jsonl(date)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        print(f"请确保工作流已经运行并生成了日志文件")
        sys.exit(1)

    if not log_entries:
        print(f"警告: {date} 没有推文日志")
        sys.exit(0)

    print(f"已加载 {len(log_entries)} 条推文记录")

    # 重建新闻列表（用于总结）
    news_items = parse_news_items(log_entries)

    # 生成 LLM 总结
    print("正在生成每日总结...")
    summary = await generate_daily_summary(news_items, log_entries)

    # 写入 Markdown
    run_at = datetime.fromisoformat(log_entries[0]["run_at"])
    md_path = write_daily_md(run_at, log_entries, news_items, summary)

    print(f"✅ 每日 Markdown 已保存: {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
