# 本地运行与验证

[English](quickstart.en.md) · [首页](../../README.md) · FIN 0.1.3

## 选择验证方式

| 方式 | 需要什么 | 可以验证什么 |
| --- | --- | --- |
| 公开源码检查 | Python 3.11、uv | 上传、导出、配置消费、目标修订；合成四格式报告 |
| 前端交互检查 | Node.js 22、npm、Chromium | 三种宽度下的导航、来源、修订对比、配置编辑和回放；API 为合成响应 |
| 完整研究工作台 | 上述依赖、Docker、模型/工具凭据、原始资料和服务设置 | 实际线程、模型、工具、报告、修订和运行费用 |

前两项不需要私有数据库，不调用模型。它们不证明真实财务研究正确，也不是完整后端的替代品。当前仓库没有可供下载的一键完整研究数据包。

## 1. 检查源码与生成合成报告

在仓库根目录执行；命令适用于 PowerShell 和常用 POSIX shell：

```bash
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery
uv run --no-sync python -m scripts.dev.verify_public_checkout --output-directory .local/public-check-01
```

本轮结果为 **34 项通过**，并生成 MD、PDF、DOCX、PPTX、图表 PNG 和合成报告 JSON。目录必须尚不存在；再次运行请改成 `.local/public-check-02`，脚本不会覆盖旧结果。导出文件明确标注为合成测试，不是公司研究结果。PDF 可直接打开；Word/PPT 还应在 Office 或 LibreOffice 中检查实际布局。

脚本使用现有 pytest 与导出器，不加载本地 `.env`、不部署服务、不提交模型任务。

## 2. 验证前端交互

```bash
cd apps/workbench/frontend
npm ci
npm run typecheck
npm run build
npx playwright install chromium
npm run test:public
```

Linux 如果缺少浏览器系统依赖，使用 `npx playwright install --with-deps chromium`。公开测试只启动本机 Vite，默认端口 **4183**，不启动旧 8765 后端；本轮 **13 项通过**，涵盖 1440、1024、390 像素界面。测试使用明确的合成 API 响应，不会调用实际研究接口。

需要观察操作时运行 `npm run test:public -- --headed --workers=1`。失败截图和 trace 写入 `apps/workbench/frontend/test-results/public/`；使用 `npx playwright show-trace <trace.zip>` 查看。该结果目录由 Playwright 管理，需要保存失败证据时先复制到独立目录。

端口占用时设置环境变量 `FINSIGHT_E2E_FRONTEND_PORT` 为另一个空闲端口，再执行测试。不要停止别人的服务来腾端口。

## 3. 启动完整本地研究

运行服务使用 LangGraph Agent Server、PostgreSQL、Redis 和 LangSmith。需要准备：

- Docker Engine 可用；
- 本地模型、LangSmith 及所用外部工具凭据，参考根目录 `.env.example`；
- 符合当前数据合同的原始财务 SQL、文档树和来源资料；
- 独立设置目录中的 `host-settings.json`、`container-settings.json` 及数据挂载，结构参考[部署目录](../../deploy/dell_agent_server/README.md)和[当前研究启动实现](../../src/sec_agent/agent_runtime/research_session_runtime.py)。

`--fresh-only` 不读取旧报告或专家答案，但仍需要原始资料，设置中应省略旧 bundle/report 路径。以下目录仅为占位示例，须替换为实际准备好的设置目录：

```bash
uv run --no-sync python -m scripts.deployment.research_workbench check --settings-directory /path/to/prepared-settings --enable-research --fresh-only
uv run --no-sync python -m scripts.deployment.research_workbench up --settings-directory /path/to/prepared-settings --enable-research --fresh-only
uv run --no-sync python -m scripts.deployment.research_workbench serve --settings-directory /path/to/prepared-settings --enable-research --fresh-only --ui-port 8793
```

Windows 可使用 `D:/private/finsight-session`。先完成上节前端构建，再启动；浏览器打开 **http://127.0.0.1:8793/workspace**，原生 API 默认为 **18165**。`serve` 占用当前终端，Ctrl+C 结束该 BFF。上述命令本身不提交模型任务；`up` 会创建或更新本地服务，运行中不要重建服务。

`research_workbench` 是统一对外入口，沿用原 `dell_report_workbench` 实现和部署身份，避免改变已有数据库卷。旧入口保持兼容。新问题创建原生线程，不创建新的 Compose 项目或端口。

## 4. 给测试者的走查清单

1. **开始研究：** 选择快捷问题、填写范围、添加资料；准备与实际启动是分开的。真实启动会产生模型费用。
2. **研究地图：** 总览进入专题，再进入判断和来源；检查面包屑返回、完整原文和计算口径。
3. **修订对比：** 展开后再次点击收起，或用底部“收起并返回研究图”；确认报告版本和基线。
4. **研究配置：** 编辑 Skill 并保存新版本，刷新后回读，再应用到指定空闲任务；浏览器项目分组与后端配置版本是不同存储范围。
5. **运行记录：** 选择历史运行、筛选阶段、播放/暂停/定位；历史回放不调用模型。运行中补充意见在后续阶段交接时读取。
6. **真实小修改（可选）：** 在已配置环境提交一条明确、局部的修改，核对目标、运行结果、差异和费用；测试不应默认重跑完整研究。

反馈时提供复现步骤、预期/实际结果、浏览器及宽度、代码提交、公开错误文字；运行问题补充 run ID。不要上传凭据、原始模型上下文、私有 trace 或个人资料。可用仓库的 Bug report 模板。

## 常见问题

| 现象 | 检查方向 |
| --- | --- |
| 配置页提示运行服务不可用 | 完整功能要连接研究 BFF 和原生 API；单独 Vite 不是研究后端。 |
| 无资料时 readiness 503 | 历史源码模式健康与目录可用，真实数据未就绪；不是自动填充测试财务数据。 |
| 浏览器测试找不到 Chromium | 执行 Playwright 安装命令；检查下载代理和系统依赖。 |
| 输出目录已存在 | 使用新的目录名，保留旧测试结果。 |
| 模型请求结果未确定 | 先查看原运行和审计，不自动重复提交付费请求。 |

## 更多工程检查

完整公开 Python 套件需要附加依赖：

```bash
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery --extra control-plane --extra qualification
uv run --no-sync python -m pytest -q
```

私有资料测试默认跳过，挂载原资料后才使用 `--run-private-data`；历史 Git 证明需要完整历史，Windows 专属资格只在对应环境执行。完整套件、公开交互测试与真实模型研究分别记录，不能混成一个成功率。

当前产品为 FIN 0.1.3，当前 Dell 报告为 v5 待审阅；已有 v4 导出页数属于历史版本，不冒充 v5 的新渲染结果。
