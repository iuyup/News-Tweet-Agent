"""
Agent 节点共享的 LLM 调用工具
支持 DeepSeek / MiniMax / Claude，使用 settings.default_llm_provider
"""
import asyncio
import logging

import anthropic
import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 2.0


async def call_default_llm(prompt: str, max_tokens: int = 512) -> str:
    """调用当前配置的默认 LLM，返回原始文本"""
    provider = settings.default_llm_provider
    if provider == "deepseek":
        return await _call_deepseek(prompt, max_tokens)
    elif provider == "minimax":
        return await _call_minimax(prompt, max_tokens)
    else:
        return await _call_claude(prompt, max_tokens)


async def _call_deepseek(prompt: str, max_tokens: int) -> str:
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            if attempt == _MAX_RETRIES - 1:
                raise
            await asyncio.sleep(_BASE_DELAY * (2 ** attempt))
    raise RuntimeError("超过最大重试次数")


async def _call_minimax(prompt: str, max_tokens: int) -> str:
    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {settings.minimax_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.minimax_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            if attempt == _MAX_RETRIES - 1:
                raise
            await asyncio.sleep(_BASE_DELAY * (2 ** attempt))
    raise RuntimeError("超过最大重试次数")


async def _call_claude(prompt: str, max_tokens: int) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(b.text for b in response.content if hasattr(b, "text"))
        except anthropic.RateLimitError:
            await asyncio.sleep(_BASE_DELAY * (2 ** attempt))
        except anthropic.APIError:
            if attempt == _MAX_RETRIES - 1:
                raise
            await asyncio.sleep(_BASE_DELAY)
    raise RuntimeError("超过最大重试次数")
