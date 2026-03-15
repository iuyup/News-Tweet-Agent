# save-daily - 保存每日推文到 Markdown

## 描述
手动保存指定日期的推文记录到 Markdown 文件。读取 JSONL 日志，调用 LLM 生成总结，然后输出 MD 文件。

## 参数
- `date` (可选): 日期字符串，格式为 YYYY-MM-DD，默认为今天

## 功能
1. 读取 `data/logs/{date}.jsonl` 中的推文日志
2. 调用 LLM 生成每日新闻总结
3. 将结果写入 `data/daily/{date}.md`
4. 输出文件路径给用户

## 示例
```
/save-daily 2026-03-14
```

## 注意事项
- 如果 JSONL 文件不存在，返回错误提示
- 如果日期为今天，会尝试读取当日工作流生成的日志
