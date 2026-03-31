# 关键词驱动的热点文章工作流

## 流程

```text
关键词输入
  -> 搜索入口发现文章
  -> 文章回采
  -> AI 相关性排序
  -> 最终热点榜
```

## 模块说明

### 搜索入口发现文章

作用：

- 根据关键词拿到候选文章链接
- 同时记录标题、摘要、公众号名、来源搜索引擎

第一版接口抽象：

- `BaseDiscoveryAdapter.search(keyword, limit)`

当前实现：

- `mock_wechat_search`

后续可替换为：

- 搜狗微信搜索适配器
- 通用搜索引擎 `site:mp.weixin.qq.com` 适配器
- 微信桌面 GUI 自动化搜索适配器

### 文章回采

作用：

- 对候选链接抓详情
- 补齐正文、发布时间、阅读量、评论数、原文链接

第一版接口抽象：

- `BaseFetchAdapter.fetch(candidate)`

当前实现：

- `MockWechatFetchAdapter`

后续可替换为：

- `wechat-article-exporter` 适配器
- 其他公众号详情抓取器

### AI 相关性排序

作用：

- 过滤“只是带关键词但主题不相关”的文章
- 给文章打相关度分数

第一版实现：

- 本地规则打分，模拟 AI 相关性排序

后续升级：

- 接 LLM 对标题和正文摘要做主题相关性判断
- 输出关键词匹配解释、主题标签、摘要

### 最终热点榜

作用：

- 根据相关度、热度、时效性综合排序
- 输出当前任务下最值得关注的文章列表

当前公式：

`总分 = 相关度 * 0.5 + 热度 * 0.3 + 时效 * 0.2`

后续可调：

- 阅读量权重
- 评论权重
- 来源公众号权重
- 时间衰减曲线

## 当前已实现接口

- `GET /health`
- `GET /api/discovery/sources`
- `POST /api/workflows/preview`
- `GET /api/workflows/jobs`
- `GET /api/workflows/jobs/{job_id}`

## 示例请求

```json
{
  "keywords": ["AI 出海", "跨境电商"],
  "platform": "wechat",
  "discovery_source": "mock_wechat_search",
  "limit": 5,
  "top_k": 5,
  "time_window_days": 7,
  "ranking": {
    "relevance": 0.5,
    "popularity": 0.3,
    "freshness": 0.2
  }
}
```

## 下一步接真实能力

1. 新增 `SogouWechatSearchAdapter`
2. 新增 `WechatArticleExporterFetchAdapter`
3. 把当前内存工作流接入数据库表 `crawl_task / crawl_job / crawl_item`
4. 再接 APScheduler 做定时执行

## 当前持久化

工作流执行结果会写入 SQLite：

- `workflow_job`
- `discovered_candidate`
- `fetched_article`
- `ranked_article`

数据库文件位置：

- Linux 默认：`backend/data/workflow.sqlite3`
- Windows 当前开发环境默认：`%USERPROFILE%\\.codex\\memories\\data-gather-agent.sqlite3`
- 可通过环境变量 `DATA_GATHER_DB_PATH` 覆盖
