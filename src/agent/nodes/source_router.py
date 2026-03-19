"""
SourceRouter 节点
LLM 决策：根据当前时间，选择今天采集哪些信息源
LLM 失败时 fallback 到默认列表
"""
import json
import logging

from src.agent._llm_call import call_default_llm
from src.prompts.templates import build_source_router_prompt

logger = logging.getLogger(__name__)

AVAILABLE_SOURCES = ["reddit", "hackernews", "arxiv", "rss"]
DEFAULT_SOURCES = ["reddit", "hackernews"]


async def source_router_node(state: dict) -> dict:
    """LLM 决定今天使用哪些信息源"""
    from datetime import datetime

    from src.config import settings

    now = state.get("run_at", datetime.utcnow())
    prompt = build_source_router_prompt(AVAILABLE_SOURCES, now)

    try:
        raw = await call_default_llm(prompt, max_tokens=256)
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1])
        data = json.loads(text)
        sources: list[str] = [s for s in data.get("selected_sources", []) if s in AVAILABLE_SOURCES]
        reasoning: str = data.get("reasoning", "")
        if not sources:
            sources = DEFAULT_SOURCES[:]
    except Exception as e:
        logger.warning("SourceRouter LLM 失败: %s，使用默认源", e)
        sources = DEFAULT_SOURCES[:]
        reasoning = "LLM 失败，使用默认信息源"

    # 仅保留配置允许的源
    enabled: list[str] = getattr(settings, "enabled_sources", AVAILABLE_SOURCES)
    sources = [s for s in sources if s in enabled]
    if not sources:
        sources = [s for s in DEFAULT_SOURCES if s in enabled] or DEFAULT_SOURCES[:]

    logger.info("SourceRouter: 选择信息源 %s | %s", sources, reasoning[:80])
    return {"selected_sources": sources}
