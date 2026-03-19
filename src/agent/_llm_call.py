"""
Agent 节点共享的 LLM 调用工具
支持 DeepSeek / MiniMax / Claude，使用 settings.default_llm_provider

内部 _call_* 函数统一返回 (text, {"input_tokens": int, "output_tokens": int})
外部接口：
  call_default_llm(prompt, max_tokens) -> str
  call_default_llm_with_usage(prompt, max_tokens) -> (str, dict)
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
    text, _ = await call_default_llm_with_usage(prompt, max_tokens)
    return text


async def call_default_llm_with_usage(
    prompt: str, max_tokens: int = 512
) -> tuple[str, dict]:
    """调用当前配置的默认 LLM，返回 (text, {"input_tokens": int, "output_tokens": int})"""
    provider = settings.default_llm_provider
    if provider == "deepseek":
        return await _call_deepseek(prompt, max_tokens)
    elif provider == "minimax":
        return await _call_minimax(prompt, max_tokens)
    else:
        return await _call_claude(prompt, max_tokens)


async def _call_deepseek(prompt: str, max_tokens: int) -> tuple[str, dict]:
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
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return text, {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                }
        except Exception:
            if attempt == _MAX_RETRIES - 1:
                raise
            await asyncio.sleep(_BASE_DELAY * (2 ** attempt))
    raise RuntimeError("超过最大重试次数")


async def _call_minimax(prompt: str, max_tokens: int) -> tuple[str, dict]:
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
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return text, {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                }
        except Exception:
            if attempt == _MAX_RETRIES - 1:
                raise
            await asyncio.sleep(_BASE_DELAY * (2 ** attempt))
    raise RuntimeError("超过最大重试次数")


async def _call_claude(prompt: str, max_tokens: int) -> tuple[str, dict]:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in response.content if hasattr(b, "text"))
            return text, {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        except anthropic.RateLimitError:
            await asyncio.sleep(_BASE_DELAY * (2 ** attempt))
        except anthropic.APIError:
            if attempt == _MAX_RETRIES - 1:
                raise
            await asyncio.sleep(_BASE_DELAY)
    raise RuntimeError("超过最大重试次数")
