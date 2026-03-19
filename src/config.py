"""
统一配置管理
使用 pydantic-settings 从 .env 文件加载环境变量
"""
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Anthropic / Claude ────────────────────────────────────────────────
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    claude_model: Literal["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"] = "claude-sonnet-4-6"

    # ── MiniMax ────────────────────────────────────────────────────────────
    minimax_api_key: str = Field("", alias="MINIMAX_API_KEY")
    minimax_model: str = "MiniMax-M2.5"

    # ── DeepSeek ───────────────────────────────────────────────────────────
    deepseek_api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    deepseek_model: str = "deepseek-chat"

    # ── LLM Provider ───────────────────────────────────────────────────────
    default_llm_provider: Literal["claude", "minimax", "deepseek"] = "minimax"

    # ── Twitter/X API v2 ─────────────────────────────────────────────────
    twitter_api_key: str = Field(..., alias="TWITTER_API_KEY")
    twitter_api_secret: str = Field(..., alias="TWITTER_API_SECRET")
    twitter_access_token: str = Field(..., alias="TWITTER_ACCESS_TOKEN")
    twitter_access_secret: str = Field(..., alias="TWITTER_ACCESS_SECRET")

    # ── 抓取参数 ─────────────────────────────────────────────────────────
    reddit_limit_per_sub: int = 10
    http_timeout: float = 15.0
    http_user_agent: str = "Mozilla/5.0 (compatible; news-bot/1.0)"

    # HackerNews
    hackernews_limit: int = 20

    # arXiv
    arxiv_query: str = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL"
    arxiv_limit: int = 10

    # RSS
    rss_feeds: list[str] = [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
    ]
    rss_limit_per_feed: int = 5

    # 允许使用的信息源（可通过 .env 覆盖）
    enabled_sources: list[str] = ["reddit", "hackernews", "arxiv", "rss"]

    # ── 推文生成规范 ──────────────────────────────────────────────────────
    tweet_max_length: int = 280
    tweets_per_run: int = 2

    # ── 调度 ──────────────────────────────────────────────────────────────
    schedule_interval_hours: int = 2
    # pydantic-settings 从 .env 读取为 str，model_validator 负责转换为 list[int]
    # 支持逗号分隔格式，如 SCHEDULE_HOURS=9,11,13,15
    schedule_hours: str | list = Field(default="9")
    schedule_hour: int = 9  # 保留，向后兼容
    schedule_minute: int = 0

    @model_validator(mode="after")
    def _parse_schedule_hours(self) -> "Settings":
        if isinstance(self.schedule_hours, str):
            self.schedule_hours = [
                int(h.strip()) for h in self.schedule_hours.split(",") if h.strip()
            ]
        elif isinstance(self.schedule_hours, list):
            self.schedule_hours = [int(h) for h in self.schedule_hours]
        return self

    # ── 路径 ──────────────────────────────────────────────────────────────
    cache_dir: str = "data/cache"
    log_dir: str = "data/logs"
    daily_dir: str = "data/daily"

    # 同步目标目录（可选，用于同步每日总结到其他位置）
    sync_target_dir: Path | None = None

    @property
    def cache_path(self) -> Path:
        return ROOT_DIR / self.cache_dir

    @property
    def log_path(self) -> Path:
        return ROOT_DIR / self.log_dir

    @property
    def daily_path(self) -> Path:
        return ROOT_DIR / self.daily_dir

    @property
    def sync_target(self) -> Path | None:
        """同步目标目录（如果有配置）"""
        if self.sync_target_dir is None:
            return None
        path = Path(self.sync_target_dir)
        return path if path.exists() else None

    # ── Agent 模式 ─────────────────────────────────────────────────────────
    use_agent: bool = False

    # ── 审核模式 ──────────────────────────────────────────────────────────
    dry_run: bool = False


# 全局单例，其他模块直接 import
settings = Settings()
