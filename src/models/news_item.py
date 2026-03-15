from datetime import datetime
from enum import Enum
from pydantic import BaseModel, HttpUrl


class Category(str, Enum):
    POLITICS = "politics"
    TECH = "tech"
    UNKNOWN = "unknown"


class NewsItem(BaseModel):
    title: str
    url: str
    source: str          # "reddit" | "nitter"
    category: Category
    score: int = 0       # 热度分（reddit upvotes / nitter 转发数）
    fetched_at: datetime = None

    def model_post_init(self, __context):
        if self.fetched_at is None:
            self.fetched_at = datetime.utcnow()
