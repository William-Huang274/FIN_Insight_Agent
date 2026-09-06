# FinSight Agent — FIN 0.1.3

**一个用真实工具、可追踪来源和多 Agent 协作完成金融研究的本地工作台。** 研究目标不是罗列“能证明/不能证明”，而是把业务增长连接到利润、现金和执行要求，形成有条件、可追问的判断。

本分支已把一个全新 Dell 增长质量问题从真实前端运行到多 Agent 研究、报告和人工审阅点。2026-09-07：完整链已实际发生，并经历保留失败的原生接续及人审定向修订；不是一次无人辅助、零错误的盲测，也不是已发布的通用投资平台。最终交付版本、真实费用及剩余意见见执行记录，Owner 验收与公开发布仍分开处理。

当前交付候选为报告 v3（7,281字符、42引用、3图），四格式已真实下载/渲染。终审仍有1条重大意见：需求专家底稿的过强判断未与已修正文稿同步。会话265请求、264已知用量、约28.09元；停止追加付费，保留“待修订”，**尚不标为最终质量通过**。这是带开发修复与修订的完整案例费用，不是一次普通问答报价。

## 产品与工程能力

| 能力 | 当前实现与证据边界 |
| --- | --- |
| 自主研究 | Lead 动态任务 DAG；专家各自多轮规划和调用工具，九研究面、并发2而非固定2专家 |
| 多角色质量闭环 | Counter/Verifier → 责任作者 → Lead 综合判断 → 独立研究复核 → Writer → 终审 → 人工；已真实执行，模型审查仍可能漏错 |
| 数据工具 | SEC 结构化财务SQL、本地文档结构/搜索/原文窗口、外源搜索/网页读取、来源绑定计算；通过 MCP 接入 |
| 运行底座 | LangChain create_agent / LangGraph、Agent Server、PostgreSQL、Redis、LangSmith；不自建模型循环、checkpoint或任务队列 |
| 交互 | 新研究、实际事件与任务状态、来源展开、追问/修订、停止；运行中意见在后续阶段交接读取 |
| 上传与视觉 | 任务隔离文件副本、成熟解析/分块、按需 Flash vision 工具；真实MCP视觉探针1调用423tokens，非OCR全面准确率 |
| 报告交付 | 来源绑定图表，MD/PDF/Word/PowerPoint导出；本地真实文件与视觉检查，财务图表仍需语义审阅 |

当前入口：`http://127.0.0.1:8766/workspace/session`；原生 Agent Server：`http://127.0.0.1:18165`。服务只绑定本机，密钥在服务端。研究原始资料可复用；新研究不加载旧专家答案。当前固定案例资料时点为2026-09-02，SQL实际覆盖DELL/MU/NVDA，非任意公司数据库。

- [架构与自研/成熟栈分工](docs/public/architecture.zh-CN.md)
- [运行、测试和部署说明](docs/public/quickstart.zh-CN.md)
- [对外展示范围与证据声明](docs/public/sharing-scope.md)
- [执行记录与本次真实成本](docs/worklog/fin_0_1_3_s3/190_dell_cost_external_and_interactive_delivery.md)
- English: [README.en.md](README.en.md)

公开准备仅整理代码和文档，不改变仓库可见性。源码/测试可展示；原始网页、用户上传、数据库、模型原文与私有trace不默认再分发。报告不是自动投资建议，模型审查不是事实裁决或人工批准。

## 历史只读工作台（兼容入口，不代表上面新研究链）

下列8765入口属于早期固定Evidence Pack展示，保留用于兼容/回归。不要用它演示新研究，也不要把它的旧三公司Pack当成新多Agent全链已通过的证明。

### 历史入口

- 研究产品：`http://127.0.0.1:8765/workspace`
- 运维控制台：`http://127.0.0.1:8765/operations`
- 健康检查：`http://127.0.0.1:8765/api/health`
- 当前案例 API：`/api/v1/research-cases`

旧 `/current`、`/next`、`/tasks` 和 `/cases` 只保留永久重定向；旧产品 API 返回带替代路径的 HTTP 410。历史代码和证明位于 `archive/versions/`，不会被当前应用加载。

### 历史入口启动

```powershell
uv sync --locked

cd apps/workbench/frontend
npm ci
npm run build
cd ../../..

uv run --locked python scripts/dev/run_workbench_backend.py --host 127.0.0.1 --port 8765
```

Python 依赖只在 `pyproject.toml` 人工维护，并由 tracked `uv.lock` 固定；不要另建手工 requirements 文件。

仓库不分发三份 reviewed Evidence Pack 的私有对象。只启动代码时，案例目录仍可读，但三个详情入口会明确显示“证据对象未挂载”，`/api/readiness` 返回 typed HTTP 503。要验收完整案例，请把包含 `workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/zero-call-r1/objects` 的数据根挂载为 `data/`，或在启动前设置 `FINSIGHT_DATA_ROOT`。凭据只放环境变量，禁止写入 Git。

### 历史基线验证

```powershell
uv run --locked python scripts/engineering/verify_active_baseline.py --pretty
uv run --locked python scripts/engineering/build_archive_redirect_index.py --check
uv run --locked python -m pytest -q
```

前端验证：

```powershell
cd apps/workbench/frontend
npm run typecheck
npm run build
```

## 代码结构

```text
apps/workbench/        唯一浏览器产品与运维组合根
src/                   当前稳定领域、数据与运行时模块
scripts/               受控数据构建、启动和基线治理入口
tests/                 当前基线测试；不递归执行 archive
configs/runtime/       三个当前运行时资源和注册表
configs/repository/    当前活动图、生命周期和验收合同
docs/                  PRD、当前技术图、质量标准和 Project OS
archive/versions/      不可执行的版本历史与逐文件重定向索引
data/                  本地/挂载数据根；私有内容不进入 Git
```

详细边界见 [当前代码图](docs/architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md) 和 [当前上下文包](docs/project_os/current_context_pack.zh-CN.md)。

### 历史数据与研究边界

- 当前公开基线不包含私有数据、API key、模型 capture、生成索引或报告运行产物。
- SEC、8-K、市场和行业脚本只负责受控数据准备；运行脚本不等于对应数据已完整可用。
- Evidence 只有通过身份、日期、来源和 digest 绑定后才能被当前 workspace 展示；当前三份 Pack 尚无结构化数值项，不能据此声称数值事实能力已完成。
- 历史失败保持不可变，但不能作为当前能力或发布通过的证据。

English: [README.en.md](README.en.md)
