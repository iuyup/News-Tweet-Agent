"""快速验证抓取模块是否正常工作"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from src.scrapers import fetch_reddit_hot, fetch_nitter_trending


async def main():
    print("\n=== Reddit 热帖 ===")
    reddit_items = await fetch_reddit_hot(limit_per_sub=5)
    for item in reddit_items[:10]:
        print(f"[{item.category.value:8s}] ({item.score:6d}) {item.title[:80]}")

    print("\n=== Nitter 热搜 ===")
    nitter_items = await fetch_nitter_trending()
    for item in nitter_items[:10]:
        print(f"[{item.category.value:8s}] {item.title[:80]}")


if __name__ == "__main__":
    asyncio.run(main())
