# 工程记录

## 当前架构（Phase 4，2026-03-19）

### 图结构
```
START → SourceRouter → Collector → Analyst → ContentPlanner → Writer → Reviewer →(通过/超限)→ Publisher → END
                                                               ↑←────(未通过，≤2次)──────────┘
```

### 节点职责
| 节点 | 职责 | LLM |
|------|------|-----|
| SourceRouter | LLM决定今天使用哪些信息源（失败时fallback） | ✅ |
| Collector | 并发抓取多个信息源 + 合并去重 | 无 |
| Analyst | 从原始新闻选出4-6条值得发推的条目，决定 should_tweet | ✅ |
| ContentPlanner | 规则式制定发推计划（politics/tech各几条） | 无 |
| Writer | 生成推文（正常）或根据Reviewer反馈修改（修改模式） | ✅ |
| Reviewer | 评审推文质量（满分10，阈值7.0），给出actionable反馈 | ✅ |
| Publisher | 发布 + 增量更新Markdown + 每日总结 + JSONL日志 | ✅（总结用） |

### 关键参数
- `MAX_REVISIONS = 2`：最多修改2次（共3次Reviewer评审），超限强制发布
- Reviewer LLM失败默认通过，防止死循环
- Analyst LLM失败降级为规则过滤，不中断流程
- SourceRouter LLM失败fallback到 `["reddit", "hackernews"]`
- Checkpointing：每次运行独立 thread_id（MemorySaver）

### 支持的信息源
| 源 | 类型 | API | 分类 |
|----|------|-----|------|
| reddit | 热帖 | JSON（无需认证） | POLITICS/TECH（按subreddit） |
| hackernews | 热帖 | Firebase API（无需认证） | POLITICS/TECH（关键词分类） |
| arxiv | 论文 | Atom API（无需认证） | TECH |
| rss | 博客 | feedparser（TechCrunch/TheVerge） | POLITICS/TECH（关键词分类） |

---

## 变更历史

### 2026-03-19: Phase 4 — SourceRouter + 多信息源

**新增文件**
- `src/scrapers/hackernews_scraper.py` — HN Firebase API抓取（并发获取story详情）
- `src/scrapers/arxiv_scraper.py` — arXiv Atom API抓取（XML解析）
- `src/scrapers/rss_scraper.py` — RSS源抓取（httpx异步获取 + feedparser解析）
- `src/agent/nodes/source_router.py` — SourceRouter节点（LLM决策选源，失败fallback）

**修改文件**
- `src/agent/nodes/collector.py` — 改为多源并发抓取，根据selected_sources分发
- `src/agent/state.py` — 新增 `selected_sources: NotRequired[list[str]]`
- `src/agent/graph.py` — 新增source_router节点，入口点改为source_router
- `src/agent/nodes/__init__.py` — 导出source_router_node
- `src/config.py` — 新增 hackernews_limit/arxiv_query/arxiv_limit/rss_feeds/rss_limit_per_feed/enabled_sources
- `src/prompts/templates.py` — 新增 `build_source_router_prompt()`
- `requirements.txt` — 新增 `feedparser>=6.0.0`

**验证结果（单测）**
- 27/27 测试全部通过（新增5个：SourceRouter×3 + Collector多源×1 + 图集成多源×1）

---

### 2026-03-19: Phase 3 — Reviewer 反思循环 + Checkpointing

**新增文件**
- `src/agent/_llm_call.py` — 节点共享LLM调用工具（DeepSeek/MiniMax/Claude）
- `src/agent/nodes/reviewer.py` — Reviewer节点

**修改文件**
- `src/agent/nodes/analyst.py` — 改用共享 `_llm_call`
- `src/agent/nodes/writer.py` — 新增修改模式（revision_count>0时走revision prompt）
- `src/agent/graph.py` — 新增reviewer节点 + 循环边 + MemorySaver checkpointing
- `src/agent/__init__.py` — run_agent()带thread_id config，日志记录修改次数和评分
- `src/prompts/templates.py` — 新增 `build_reviewer_prompt()` 和 `build_revision_prompt()`

**验证结果（dry-run）**
- 7/7 subreddit抓取成功，60条→去重46条
- Analyst选出4条精华（DeepSeek）
- ContentPlanner: politics=1, tech=1
- Writer生成2条推文
- Reviewer评分7.5，**首次通过**，revision_count=0
- 全程无异常，JSONL日志正常写入

---

### 2026-03-19: Phase 2 — Analyst + ContentPlanner 节点

**新增文件**
- `src/agent/nodes/analyst.py` — LLM选题节点
- `src/agent/nodes/content_planner.py` — 规则式内容计划节点

**修改文件**
- `src/agent/nodes/collector.py` — 去掉filter_and_rank，只做抓取+去重
- `src/agent/nodes/writer.py` — 使用content_plan.total作为生成数量
- `src/agent/graph.py` — 新增两个节点及条件边
- `src/prompts/templates.py` — 新增 `build_analyst_prompt()`

**验证结果（dry-run）**
- Analyst从48条中选出6条（DeepSeek，约500 tokens），比规则过滤更精准
- should_tweet=True，ContentPlanner正确分配politics/tech数量

---

### 2026-03-19: Phase 1 MVP — Collector → Writer → Publisher

**新增文件**
- `src/agent/__init__.py`, `src/agent/__main__.py`
- `src/agent/state.py` — TweetAgentState TypedDict（含Phase2-3预留字段）
- `src/agent/graph.py` — StateGraph组装
- `src/agent/nodes/` — collector, writer, publisher

**修改文件**
- `requirements.txt` — 新增 `langgraph>=0.2.0`
- `src/config.py` — 新增 `use_agent: bool = False`
- `src/scheduler/cron.py` — 条件调度agent或旧pipeline

---

## 架构决策记录（ADR）

| ADR | 决策 | 理由 |
|-----|------|------|
| ADR-001 | State用TypedDict+NotRequired预留Phase2-3字段 | 后续不需改State结构 |
| ADR-002 | Phase1 Collector合并scrape+filter | Phase2拆分给Analyst |
| ADR-003 | 保留旧workflow.py，USE_AGENT开关切换 | 零风险迁移 |
| ADR-004 | Phase1-2不用checkpointing | Phase3引入（循环需要） |
| ADR-005 | Publisher内联_write_log | 不依赖workflow.py内部函数 |
| ADR-006 | 每日总结放Publisher节点末尾 | 与旧workflow行为一致 |
| ADR-007 | Reviewer LLM失败默认通过 | 防止Writer↔Reviewer死循环 |
| ADR-008 | 共享_llm_call.py抽取LLM调用 | analyst/reviewer/writer(revision)三处复用 |

---

---

### 2026-03-19: Phase 5 — SQLite持久化 + 监控CLI

**新增文件**
- `src/storage/db.py` — SQLite持久化层，替代 `published_hashes.txt` 文本缓存
  - `init_db()`: 建表 + 一次性迁移旧 txt → SQLite（启动时调用）
  - `_ensure_table()`: 懒加载建表，所有DB操作前自动调用，无需显式init
  - `load_published_fingerprints()`: 返回已发布指纹集合（供 filter.py 去重）
  - `save_tweet()`: INSERT OR REPLACE，以fingerprint为唯一键
  - `get_recent_tweets(days)`: 返回最近N天推文列表（可供Analyst参考）
  - `get_stats()`: 发布统计（今日/累计数量 + token用量）
- `src/cli/status.py` — 监控CLI，`python -m src.cli.status [--days N]`
- `tests/test_db.py` — 9个DB单测（建表/迁移/存取/冲突更新/统计）

**修改文件**
- `src/processors/filter.py` — 移除 `_CACHE_FILE` 文本文件，改用SQLite
  - `_load_published()` → `db.load_published_fingerprints()`
  - `mark_published()` → `db.save_tweet()` 写最小记录（兼容旧workflow.py）
- `src/agent/nodes/publisher.py` — 发布成功后调用 `save_tweet()` 写完整记录（ON CONFLICT UPDATE覆盖最小记录）
- `src/agent/__init__.py` — `run_agent()` 入口处调用 `init_db()`
- `tests/test_filters.py` — 更新 `TestMarkPublished` 测试改为验证SQLite写入
- `tests/test_agent_graph.py` — 图集成测试新增 `save_tweet` mock

**验证结果（单测）**
- 63/63 测试全部通过（新增9个DB单测）

**架构决策**
- ADR-009: `_ensure_table()` 懒加载建表，解耦 init 与 migrate，避免测试时需要显式初始化
- ADR-010: `save_tweet()` 使用 ON CONFLICT(fingerprint) DO UPDATE，允许 mark_published（最小记录）被 publisher（完整记录）覆盖
- ADR-011: JSONL日志保留（追加-only，适合日志聚合），SQLite为主要持久化（可查询、去重）

---

### 2026-03-19: Phase 5 补完 — JSONL回填 + Analyst近期推文去重

**新增文件**
- `src/cli/backfill.py` — JSONL历史数据回填CLI，`python -m src.cli.backfill [--dry]`
  - 解析所有 `data/logs/*.jsonl`，用 `save_tweet()` 回填完整记录（tweet文本、token、分类）
  - `--dry` 模式只统计不写入

**修改文件**
- `src/storage/db.py` — `save_tweet()` ON CONFLICT 补全所有字段更新（原缺少 category/source/news_title/published_at）
- `src/prompts/templates.py` — `build_analyst_prompt()` 新增 `recent_tweets` 参数，将最近7天推文列表注入 prompt 供去重参考
- `src/agent/nodes/analyst.py` — 调用 `db.get_recent_tweets(days=7)` 并传给 prompt（失败时静默降级）
- `src/cli/status.py` — 修复 Windows GBK 终端编码问题

**验证**
- 147 条 JSONL 历史记录回填成功，token 统计恢复正常（70,299 输入 / 57,224 输出）
- 63/63 测试全部通过（无回归）

---

### 2026-03-19: 生产验证 — 首次完整 Agent 实时发布

**运行参数**：`USE_AGENT=true`，`DRY_RUN=false`，LLM=DeepSeek

| 指标 | 数值 |
|------|------|
| 信息源（SourceRouter 选定） | reddit + hackernews + rss |
| 抓取原始 → 去重后 | 90 → 75 条 |
| Analyst 近期上下文 | 50 条（近 7 天 DB 查询）|
| 生成推文 | 2 条（politics 238c / tech 225c）|
| Reviewer 评分 | 8.0，首次通过（revision=0）|
| 实际发布 | ✅ 2 条 |
| Tweet ID | 2034567228096680349 / 2034567231984849035 |
| Obsidian 同步 | ✅ |

---

## 测试覆盖（63个测试，全部通过）

```
tests/test_agent_graph.py  — 27个（各节点单测 + 图集成含循环场景 + 多源场景）
tests/test_db.py           — 9个（SQLite建表/迁移/存取/统计）
tests/test_filters.py      — 8个
tests/test_llm.py          — 7个
tests/test_scrapers.py     — 3个
tests/test_workflow.py     — 9个
```

## 环境配置

```bash
# .env 关键开关
USE_AGENT=true      # 启用Agent模式（默认false，走旧workflow）
DRY_RUN=true        # 干跑模式，不实际发推
DEFAULT_LLM_PROVIDER=deepseek  # 当前默认LLM

# 手动单次运行
python -m src.agent

# 运行所有测试
pytest tests/ -v
```
