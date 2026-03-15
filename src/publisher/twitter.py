"""
Twitter/X API v2 发布客户端
使用 tweepy 的 OAuth 1.0a 用户认证
"""
import asyncio
import logging

import tweepy

from src.config import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 5.0


def _extract_error_details(exception: Exception) -> str:
    """从 tweepy 异常中提取详细错误信息"""
    try:
        # 尝试获取 response 属性中的详细信息
        if hasattr(exception, 'response') and exception.response is not None:
            response = exception.response
            if hasattr(response, 'text'):
                return f"status={response.status_code}, body={response.text[:200]}"
            elif hasattr(response, 'status_code'):
                return f"status={response.status_code}"
    except Exception:
        pass
    return "无详细响应"


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=settings.twitter_api_key,
        consumer_secret=settings.twitter_api_secret,
        access_token=settings.twitter_access_token,
        access_token_secret=settings.twitter_access_secret,
    )


async def publish_tweet(tweet_text: str) -> str | None:
    """
    发布单条推文，返回推文 ID（失败返回 None）。
    dry_run 模式下只打印，不实际发布。
    """
    if len(tweet_text) > settings.tweet_max_length:
        logger.error("推文超过 280 字符，拒绝发布: %d chars", len(tweet_text))
        return None

    if settings.dry_run:
        logger.info("[DRY RUN] 推文内容:\n%s", tweet_text)
        return "dry-run-id"

    client = _get_client()

    for attempt in range(_MAX_RETRIES):
        try:
            # tweepy.Client.create_tweet 是同步调用，用 asyncio 包装
            response = await asyncio.to_thread(client.create_tweet, text=tweet_text)
            tweet_id: str = str(response.data["id"])
            logger.info("推文发布成功: id=%s", tweet_id)
            return tweet_id
        except tweepy.TooManyRequests:
            delay = _BASE_DELAY * (2 ** attempt)
            logger.warning("Twitter 限流 (429)，%.1f 秒后重试（%d/%d）", delay, attempt + 1, _MAX_RETRIES)
            await asyncio.sleep(delay)
        except tweepy.Forbidden as e:
            # 内容违规：详细记录错误信息和推文内容
            error_details = _extract_error_details(e)
            logger.error(
                "Twitter 内容违规 (403)。错误: %s | 推文内容: %s | 详情: %s",
                e, tweet_text[:100], error_details
            )
            return None
        except tweepy.TweepyException as e:
            # 其他 API 错误：记录详细信息
            error_details = _extract_error_details(e)
            logger.error(
                "Twitter API 错误: %s | 错误类型: %s | 推文: %s | 详情: %s",
                e, type(e).__name__, tweet_text[:100], error_details
            )
            if attempt == _MAX_RETRIES - 1:
                return None
            await asyncio.sleep(_BASE_DELAY)

    return None
