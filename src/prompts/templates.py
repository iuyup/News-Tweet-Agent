"""
推文撰写 Prompt 模板
"""
from src.models.news_item import Category, NewsItem


def build_tweet_prompt(items: list[NewsItem], category: Category) -> str:
    """
    根据新闻条目列表构建推文生成 Prompt。
    返回完整的 user message 字符串。
    """
    category_desc = {
        Category.POLITICS: "geopolitics and world affairs",
        Category.TECH: "technology and AI",
    }.get(category, "current events")

    headlines = "\n".join(
        f"{i+1}. [{item.source}] {item.title} (score: {item.score})"
        for i, item in enumerate(items)
    )

    return f"""You are a sharp, concise social media writer covering {category_desc}.

Below are today's top trending headlines:

{headlines}

Select the SINGLE most newsworthy headline and write one engaging English tweet about it.

Rules:
- Strict maximum 280 characters (including hashtags)
- Include 2-3 relevant hashtags at the end
- Tone: informative, neutral, attention-grabbing
- For politics: stay objective, no extreme positions
- For tech: highlight the key innovation or industry impact
- Do NOT include a URL

Respond with ONLY a JSON object in this exact format:
{{
  "tweet": "<tweet text with hashtags>",
  "source_index": <1-based index of the headline you chose>,
  "char_count": <character count of tweet>
}}"""
