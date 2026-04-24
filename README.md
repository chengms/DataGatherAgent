# Archived

This repository has been integrated into the unified monorepo:

https://github.com/chengms/DataAgent-Maker

Please use the monorepo for future development.

Note: The unified monorepo is currently private. If you need access, request access to chengms/DataAgent-Maker.

---

# DataGatherAgent

统一内容采集与排序工作台，当前通过两类外部能力覆盖多平台采集：

- 微信公众号：`wechat-article-exporter`
- 小红书 / 微博 / 抖音 / B站：`MediaCrawler`

这些外部仓库都作为受管 checkout 放在 `external_tools/` 下，不直接改上游源码。登录、配置写回、启动编排都在当前仓库里完成。
控制台支持按平台勾选采集范围，后端会自动选择对应的平台采集链路。

## 最快开始

Windows:

```powershell
.\bootstrap.ps1
```

Linux/macOS/WSL:

```bash
./bootstrap.sh
```

这个统一入口会顺序完成：

1. 检查必要命令和端口
2. clone 或更新外部仓库
3. 安装 backend 和外部工具依赖
4. 在缺少登录态时显示终端二维码
5. 扫码成功后把登录结果写入 `services.local.json`
6. 启动完整服务栈

启动完成后访问：

- 控制台：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/health`

## 常用脚本

- `bootstrap.ps1` / `bootstrap.sh`
  - 新机器或首次使用的统一入口
- `up.ps1` / `up.sh`
  - 已经有登录态时，直接启动完整服务
- `start.ps1` / `start.sh`
  - 只启动 backend
- `login-wechat.ps1` / `login-wechat.sh`
  - 单独执行微信公众号终端扫码登录
- `login-xhs.ps1` / `login-xhs.sh`
  - 单独执行小红书终端扫码登录
- `test-watch.ps1` / `test-watch.sh`
  - 带心跳和无输出超时保护的测试入口

## 目录说明

- `backend/`
  - FastAPI 应用、adapter、workflow、测试
- `scripts/`
  - 启动编排、终端二维码登录、外部仓库包装器
- `external_tools/`
  - 受管第三方仓库 checkout
- `docs/`
  - 开发和维护说明

## 配置文件

- `services.manifest.json`
  - 声明受管服务、安装命令、启动命令、端口和健康检查
- `services.local.json`
  - 本机私有配置，不提交
- `services.local.example.json`
  - 本机配置模板

扫码登录成功后，脚本会自动把这些值写入 `services.local.json`：

- `WECHAT_EXPORTER_API_KEY`
- `XHS_MEDIACRAWLER_COOKIES`
- 必要时切换 `XHS_MEDIACRAWLER_LOGIN_TYPE=cookie`

工作流平台选择与策略：

- 已接入：`wechat`、`xiaohongshu`、`weibo`、`douyin`、`bilibili`
- 预留：`zhihu`
- 预览请求默认按 `platforms` 字段逐平台运行，不需要手动传 adapter 名称

## 外部仓库策略

- 外部仓库统一放在 `external_tools/`
- 主仓库不直接提交这些外部仓库内容
- 已存在仓库只有在 `git status --porcelain` 干净时才允许更新
- 更新使用 `git pull --ff-only`
- 当前仓库通过附加脚本调用它们，不修改上游源码

## 常见问题

`bootstrap` 卡在依赖检查：
- 先看终端提示缺的是 `python`、`node`、`corepack`、`git` 还是 `uv`

二维码登录后没保存：
- 检查 `services.local.json` 是否已生成
- 确认脚本有没有报错退出

外部仓库更新失败：
- 先进入对应目录看 `git status --short`
- 有本地脏改动时，启动器会拒绝自动更新

## 更多文档

- [backend/README.md](/D:/MyFile/Coder/DataGatherAgent/backend/README.md)
- [docs/DEVELOPMENT.md](/D:/MyFile/Coder/DataGatherAgent/docs/DEVELOPMENT.md)
