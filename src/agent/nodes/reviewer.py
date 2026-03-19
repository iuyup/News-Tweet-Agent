"""
Reviewer 节点
LLM 评审推文质量，输出 review_passed / score / feedback
未通过时由 graph 路由回 Writer 进行修改（最多 MAX_REVISIONS 次）
"""
import json
import logging

from src.agent._llm_call import call_default_llm
from src.prompts.templates import build_reviewer_prompt

logger = logging.getLogger(__name__)


def _parse_review(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
    return json.loads(text)


async def reviewer_node(state: dict) -> dict:
    """评审 generated_tweets，输出评审结果"""
    tweets = state.get("generated_tweets", [])
    revision_count = state.get("revision_count", 0)

    if not tweets:
        logger.warning("Reviewer: 无推文可评审，默认通过")
        return {
            "review_passed": True,
            "review_score": 0.0,
            "review_feedback": "",
            "revision_count": revision_count,
        }

    prompt = build_reviewer_prompt(tweets)

    try:
        raw = await call_default_llm(prompt, max_tokens=512)
        data = _parse_review(raw)
        passed = bool(data.get("review_passed", False))
        score = float(data.get("score", 0.0))
        feedback = str(data.get("feedback", "")).strip()
        engagement = float(data.get("engagement", 0.0))
        accuracy = float(data.get("accuracy", 0.0))
        fmt = float(data.get("format", 0.0))
    except Exception as e:
        # LLM 失败时默认通过，避免死循环
        logger.warning("Reviewer LLM 失败: %s，默认通过", e)
        return {
            "review_passed": True,
            "review_score": 7.0,
            "review_feedback": "",
            "revision_count": revision_count,
        }

    # 未通过时计数 +1
    new_count = revision_count + (0 if passed else 1)

    logger.info(
        "Reviewer: passed=%s score=%.1f (eng=%.1f acc=%.1f fmt=%.1f) revision=%d | %s",
        passed,
        score,
        engagement,
        accuracy,
        fmt,
        new_count,
        feedback[:80] if feedback else "OK",
    )

    return {
        "review_passed": passed,
        "review_score": score,
        "review_feedback": feedback,
        "revision_count": new_count,
    }
