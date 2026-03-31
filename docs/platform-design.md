# 数据采集平台设计

## 1. 目标

构建一个本地可运行、后续可迁移到 Linux 服务器的采集平台，满足以下约束：

- 采集平台：微信公众号、小红书
- 运行方式：手动触发 + 每天低频定时触发 2-3 次
- 存储方式：本地文件 + 本地数据库
- 部署环境：优先 Linux / WSL，后续可上云
- 开发策略：复用现成开源项目，不重写底层采集逻辑

本项目不追求“大而全的统一爬虫”，而是做一个“采集编排平台”：

- 底层采集能力由成熟开源项目提供
- 平台自身负责任务配置、执行、定时、日志、结果统一入库

## 2. 开源项目选型

### 2.1 小红书采集

首选：`NanmiCoder/MediaCrawler`

- 仓库：https://github.com/NanmiCoder/MediaCrawler
- 适用场景：小红书关键词搜索、指定帖子详情、评论采集
- 优势：
  - 社区体量大，当前约 46.9k stars
  - 自带 WebUI 和命令行入口
  - 支持 `CSV / JSON / JSONL / Excel / SQLite / MySQL`
  - 适合先本地跑，后续迁移服务器
- 风险：
  - 依赖登录态与平台页面行为
  - 项目 README 明确有“仅供学习、禁止商业用途”的免责声明，需要你再次核查 LICENSE 与使用边界
  - 平台变动后可能需要跟进调整

备选：`ReaJason/xhs`

- 仓库：https://github.com/ReaJason/xhs
- 适用场景：你想自己封装更轻量的小红书适配层
- 优势：
  - MIT License
  - Python 包形式，适合二次封装
  - 仓库结构中包含 `xhs-api`
- 风险：
  - 更偏 SDK，不是完整平台
  - 需要你自己处理更多运行链路、签名、调度与结果整理

结论：

- 如果目标是尽快落地，选 `MediaCrawler`
- 如果目标是长期自己维护适配层，选 `ReaJason/xhs`

当前建议：`第一版使用 MediaCrawler`

### 2.2 公众号采集

首选：`wechat-article/wechat-article-exporter`

- 仓库：https://github.com/wechat-article/wechat-article-exporter
- 适用场景：公众号文章批量导出、本地归档
- 优势：
  - 当前约 8.2k stars
  - MIT License
  - 支持 docker 私有化部署
  - 支持多种导出格式，HTML 可较好保留排版
  - 适合“账号文章归档”这一明确场景
- 风险：
  - 更偏“导出工具”而非统一采集平台
  - 依赖公众号后台能力与登录态

备选：`NanmiCoder/NewsCrawler`

- 仓库：https://github.com/NanmiCoder/NewsCrawler
- 适用场景：你想把公众号采集纳入统一 API / WebUI / Docker 的技术结构
- 优势：
  - 支持微信公众号
  - 当前 README 展示了 FastAPI + Vue 3 + Docker Compose 结构
  - 输出标准化 JSON，默认保存在 `data/`
  - 更适合作为“内容抽取服务”
- 风险：
  - 社区体量远小于前两者
  - 对公众号的覆盖面与稳定性仍需你自己验证

结论：

- 如果目标是“文章导出归档”，选 `wechat-article-exporter`
- 如果目标是“平台内统一抽取接口”，选 `NewsCrawler`

当前建议：`第一版使用 wechat-article-exporter`

### 2.3 调度与编排

不建议直接把 `n8n` 作为主平台骨架。

- `n8n` 适合做工作流编排
- 但你的核心产品是“采集平台”，不是通用自动化平台
- 直接以 n8n 为核心，会导致任务模型、权限、结果展示、平台适配层都受限于其节点体系

建议：

- 你自己的平台负责任务与执行
- 底层定时先用 `APScheduler`
- 后续如果你要串联通知、审批、Webhook，再接入 `n8n`

## 3. 最终推荐组合

第一版最务实的组合如下：

- 小红书：`MediaCrawler`
- 公众号：`wechat-article-exporter`
- 平台后端：`FastAPI`
- 平台前端：`Vue 3 + Element Plus`
- 调度：`APScheduler`
- 数据库：`SQLite`
- 部署：`Docker Compose`

原因：

- 两个底层采集项目都已经相对接近“可直接跑”
- FastAPI 适合封装任务执行与日志接口
- Vue 3 做后台控制台足够快
- SQLite 适合单机低频任务，后续可以平滑切 PostgreSQL
- Docker Compose 方便 WSL、本地 Linux、云服务器三端统一

## 4. 架构原则

### 4.1 不直接侵入第三方源码

平台不要直接修改第三方项目内部逻辑。

推荐通过以下方式集成：

- 优先：CLI 调用
- 其次：容器服务调用
- 最后才考虑：直接 import 第三方内部模块

这样做的好处：

- 第三方升级更容易跟进
- 你的平台与底层采集器解耦
- 更容易替换采集器

### 4.2 平台内部统一抽象

平台内部统一抽象为：

- `Task`：任务定义
- `Job`：一次执行实例
- `Adapter`：平台适配器
- `Artifact`：原始导出文件
- `Item`：标准化后的结果数据

## 5. 系统模块设计

建议拆成以下模块：

### 5.1 Web 管理台

负责：

- 新建/编辑采集任务
- 手动启动任务
- 启用/停用定时任务
- 查看执行日志
- 查看采集结果
- 管理平台登录态

### 5.2 API 服务

负责：

- 任务管理接口
- 运行控制接口
- 日志查询接口
- 结果查询接口
- 调度注册接口

### 5.3 Scheduler

负责：

- 读取启用中的任务
- 注册 cron 表达式
- 到点创建执行 Job

第一版直接使用 `APScheduler` 即可。

### 5.4 Runner

负责：

- 根据任务配置选择对应 adapter
- 启动 CLI / 容器调用
- 收集 stdout / stderr
- 解析输出文件
- 标准化入库
- 更新 job 状态

### 5.5 Adapter

每个平台一个 adapter：

- `XhsAdapter`
- `WechatAdapter`

adapter 只做三件事：

- 校验任务参数
- 生成底层执行命令
- 解析底层输出结果

### 5.6 Storage

负责两部分：

- 结构化数据：SQLite
- 原始文件：本地目录

## 6. 推荐仓库结构

```text
DataGatherAgent/
  backend/
    app/
      api/
      core/
      models/
      schemas/
      services/
      scheduler/
      runners/
      adapters/
      repositories/
      utils/
    data/
    logs/
    tests/
  frontend/
    src/
      api/
      views/
      components/
      stores/
  workers/
    mediacrawler/
    wechat-exporter/
  docker/
  docs/
    platform-design.md
  docker-compose.yml
```

说明：

- `workers/` 不一定存放第三方源码，也可以只放适配脚本与配置
- 如果第三方项目采用独立容器运行，`workers/` 可仅保留调用封装

## 7. 数据库设计

### 7.1 platform_account

保存平台登录态配置。

字段：

- `id`
- `platform`
- `name`
- `cookie_text`
- `cookie_path`
- `browser_profile_path`
- `status`
- `created_at`
- `updated_at`

### 7.2 crawl_task

保存任务配置。

字段：

- `id`
- `name`
- `platform`
- `task_type`
- `enabled`
- `schedule_type`
- `cron_expr`
- `params_json`
- `account_id`
- `output_dir`
- `save_raw`
- `dedupe_enabled`
- `status`
- `created_at`
- `updated_at`

### 7.3 crawl_job

保存每次执行记录。

字段：

- `id`
- `task_id`
- `trigger_type`
- `status`
- `started_at`
- `finished_at`
- `duration_ms`
- `log_path`
- `error_message`
- `result_summary_json`

### 7.4 crawl_item

保存标准化后的内容数据。

字段：

- `id`
- `platform`
- `item_type`
- `source_id`
- `source_url`
- `title`
- `author_name`
- `author_id`
- `publish_time`
- `content_text`
- `raw_json`
- `content_hash`
- `created_at`
- `updated_at`

### 7.5 crawl_media

保存图片、封面、视频等媒体记录。

字段：

- `id`
- `item_id`
- `media_type`
- `url`
- `local_path`
- `sort_order`
- `created_at`

### 7.6 crawl_artifact

保存原始导出文件。

字段：

- `id`
- `job_id`
- `artifact_type`
- `file_path`
- `file_size`
- `created_at`

## 8. 任务模型设计

统一任务结构建议如下：

```json
{
  "name": "xhs-keyword-cafe",
  "platform": "xhs",
  "task_type": "search",
  "schedule_type": "cron",
  "cron_expr": "0 8,14,20 * * *",
  "params": {
    "keyword": "咖啡店装修",
    "limit": 50,
    "include_comments": true
  }
}
```

公众号任务示例：

```json
{
  "name": "wechat-account-articles",
  "platform": "wechat",
  "task_type": "account_articles",
  "schedule_type": "manual",
  "params": {
    "account_name": "目标公众号",
    "limit": 30,
    "export_format": "html"
  }
}
```

## 9. Adapter 接口设计

统一接口：

```python
class BaseAdapter:
    platform: str

    def validate(self, task_config: dict) -> None:
        ...

    def build_command(self, task_config: dict, job_id: int) -> list[str]:
        ...

    def parse_output(self, workdir: str) -> dict:
        ...
```

### 9.1 XhsAdapter

第一版对接 `MediaCrawler`。

职责：

- 把平台任务配置转换为 `uv run main.py ...`
- 指定输出目录
- 任务结束后读取 JSON / SQLite / 导出文件
- 标准化为平台内部 item 格式

### 9.2 WechatAdapter

第一版对接 `wechat-article-exporter`。

职责：

- 把平台任务配置转换为导出命令或 HTTP 调用
- 收集导出的 `html/json/xlsx/md`
- 解析必要字段入库
- 原始文件作为 artifact 保留

## 10. 执行链路

一次任务执行的标准流程：

1. 用户手动点击运行，或调度器到点触发
2. 系统创建 `crawl_job`
3. Runner 根据 `platform` 选择 adapter
4. adapter 生成底层执行命令
5. 系统启动子进程
6. stdout/stderr 写入日志文件
7. 第三方采集器输出结果到 job 专属目录
8. adapter 解析结果并标准化
9. 平台写入 `crawl_item / crawl_media / crawl_artifact`
10. 更新 `crawl_job` 状态为成功或失败

## 11. 文件存储设计

建议按 job 分目录：

```text
backend/data/jobs/
  20260331_080000_12/
    stdout.log
    stderr.log
    result.json
    export.xlsx
    export.html
```

优点：

- 便于排错
- 便于回溯执行结果
- 便于把某次 job 完整归档

## 12. API 设计

### 12.1 任务管理

- `GET /api/tasks`
- `POST /api/tasks`
- `GET /api/tasks/{id}`
- `PUT /api/tasks/{id}`
- `DELETE /api/tasks/{id}`
- `POST /api/tasks/{id}/enable`
- `POST /api/tasks/{id}/disable`

### 12.2 执行控制

- `POST /api/tasks/{id}/run`
- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `GET /api/jobs/{id}/logs`

### 12.3 结果查询

- `GET /api/items`
- `GET /api/items/{id}`
- `GET /api/jobs/{id}/artifacts`

### 12.4 账号配置

- `GET /api/accounts`
- `POST /api/accounts`
- `PUT /api/accounts/{id}`

## 13. 前端页面设计

第一版只做以下页面：

- 任务列表
- 新建/编辑任务
- 执行记录
- 任务日志详情
- 采集结果列表
- 平台账号设置

任务列表页建议支持：

- 手动运行
- 启用/停用
- 查看最近一次结果
- 查看最近一次日志

## 14. 部署设计

### 14.1 第一阶段

本地 / WSL / 单机 Linux：

- `backend`
- `frontend`
- `sqlite`
- 第三方 crawler 使用本机依赖或独立容器

### 14.2 第二阶段

迁移云服务器后：

- `backend`
- `frontend`
- `scheduler`
- `worker`
- `postgres`
- 第三方 crawler 容器化

## 15. 开发顺序

推荐按以下顺序开发：

1. 初始化 FastAPI 后端骨架
2. 初始化 Vue 3 后台页面骨架
3. 建表并接通 SQLite
4. 实现任务 CRUD
5. 实现 `XhsAdapter -> MediaCrawler`
6. 实现手动触发与日志收集
7. 实现结果入库与结果页
8. 接入 APScheduler
9. 实现 `WechatAdapter -> wechat-article-exporter`
10. 最后补 Docker Compose

## 16. 第一版边界

第一版建议明确不做：

- 多租户
- 权限系统
- 分布式 worker
- 复杂消息队列
- 大规模代理池
- 高并发抓取
- 自动绕过反爬

## 17. 当前结论

建议你把以下项目作为“底层手脚架”：

- 小红书：`NanmiCoder/MediaCrawler`
- 公众号：`wechat-article/wechat-article-exporter`

建议你自己实现的平台部分：

- FastAPI 后端
- Vue 3 管理台
- APScheduler 定时
- SQLite / PostgreSQL 存储
- adapter / runner / job / 日志 / 结果标准化

这条路线的核心价值是：

- 开发成本低
- 上手快
- 本地可跑
- 后续可上云
- 采集器可以替换
