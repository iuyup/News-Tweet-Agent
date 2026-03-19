"""
Agent 架构入口
基于 LangGraph StateGraph 的推文自动化 Agent（Phase 3）
"""
import logging
from datetime import datetime, timezone

from src.agent.graph import build_checkpointed_graph
from src.storage.db import init_db

logger = logging.getLogger(__name__)

# 全局编译图（带 MemorySaver checkpointing，支持 Writer↔Reviewer 循环）
app = build_checkpointed_graph()


async def run_agent() -> dict:
    """单次运行 Agent 图，返回最终 State"""
    init_db()  # 幂等，确保 SQLite 表存在并完成旧缓存迁移
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    config = {"configurable": {"thread_id": run_id}}

    initial_state = {
        "raw_items": [],
        "scrape_errors": [],
        "filtered_items": [],
        "generated_tweets": [],
        "publish_results": [],
        "run_at": datetime.now(timezone.utc),
        "error_log": [],
    }

    logger.info("=== Agent 开始运行 (thread=%s) ===", run_id)
    result = await app.ainvoke(initial_state, config=config)

    published = len(result.get("publish_results", []))
    revisions = result.get("revision_count", 0)
    score = result.get("review_score")
    logger.info(
        "=== Agent 运行完成 | 发布 %d 条 | 修改 %d 次 | 评分 %s ===",
        published,
        revisions,
        f"{score:.1f}" if score is not None else "N/A",
    )
    return result


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_agent())
