"""
状态监控 CLI

用法：
    python -m src.cli.status          # 显示统计面板
    python -m src.cli.status --days 3  # 显示最近 3 天推文
"""
import argparse
import sys
from datetime import datetime


def _fmt_num(n: int) -> str:
    return f"{n:,}"


def show_status(days: int = 7) -> None:
    from src.storage.db import get_recent_tweets, get_stats, init_db

    init_db()
    stats = get_stats()
    recent = get_recent_tweets(days=days)

    # ── 统计面板 ──────────────────────────────────────────────────────────────
    print()
    print("Auto-Tweet Agent — 状态面板")
    print("=" * 42)
    print(f"  今日发布:     {_fmt_num(stats['today'])} 条")
    print(f"  累计发布:     {_fmt_num(stats['total'])} 条")
    print(f"  累计 Tokens:  {_fmt_num(stats['total_input_tokens'])} 输入 / "
          f"{_fmt_num(stats['total_output_tokens'])} 输出")
    print()

    # ── 最近推文 ──────────────────────────────────────────────────────────────
    if not recent:
        print(f"  （最近 {days} 天无发布记录）")
    else:
        print(f"最近 {days} 天推文（共 {len(recent)} 条）:")
        print("-" * 42)
        for row in recent[:20]:
            ts = row["published_at"][:16].replace("T", " ")
            cat = row["category"][:3].upper()
            tweet_preview = row["tweet"][:60].replace("\n", " ")
            line = f"  [{ts}] [{cat}] {tweet_preview}..."
            # 兼容 Windows GBK 终端
            print(line.encode("utf-8", errors="replace").decode("utf-8", errors="replace"),
                  end="\n", flush=True)

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-Tweet Agent 状态监控")
    parser.add_argument(
        "--days", type=int, default=7,
        help="显示最近 N 天的推文（默认 7）",
    )
    args = parser.parse_args()
    show_status(days=args.days)


if __name__ == "__main__":
    main()
