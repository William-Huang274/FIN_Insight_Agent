# FIN Insight 当前上下文包

更新时间：2026-08-12
当前产品版本：FIN 0.1.3
当前权威分支：`main`
G12 代码复证提交：`cd9990ac7ea4586cc55af0bc77f41c3f797399cb`

## 一句话状态

FIN 0.1.3 的严格仓库重定基已合并远端 `main` 并通过 G01–G12。当前唯一产品主线收敛为“DELL、MU、NVDA 三个身份绑定、只读、人工复核 Evidence Pack 的研究工作台”，历史实现已非破坏性迁入版本归档。S0 仓库基线完成，但 FIN 0.1.3 产品迭代尚未完成，下一责任阶段是 S1 检索纵切。

## 当前唯一产品边界

- 产品入口：`/workspace`
- 运维入口：`/operations`
- 当前 API：`/api/v1/research-cases`、`/api/v1/research-cases/{case_id}`、`/api/v1/research-cases/{case_id}/evidence`
- 当前案例：DELL、MU、NVDA
- 当前能力：展示经复核且与公司身份、研究截至日、case version、artifact digest 和 payload digest 绑定的 Evidence Pack；展示被拒证据、剩余缺口和可审计边界。三份当前 Pack 的结构化数值项为 0，因此不声称数值事实能力已经完成。
- 当前不声称：动态 Agentic Research、开放式联网检索、完整投资报告、实时行情、自动事实晋升、交易建议或 release-ready 产品。
- 数据边界：reviewed Evidence 对象、普通数据构建根和可写 Operations state 已分离；容器可把 Evidence 只读挂载。无对象时 `/api/readiness=503`，挂载正确对象时为 200。

## 当前活动代码

- 后端组合根：`apps/workbench/backend/app.py`
- 领域应用层：`apps/workbench/backend/application/`
- 当前前端：`apps/workbench/frontend/vite/src/`
- 稳定运行时：`src/sec_agent/`、`src/connectors/`、`src/ingestion/`、`src/evidence/`、`src/indexing/`、`src/retrieval/`
- 受控数据构建：`scripts/data_sec/`、`scripts/data_retrieval/`、`scripts/market/`、`scripts/industry/`
- 活动图检查：`scripts/engineering/verify_active_baseline.py`
- 精确历史重定向：`archive/versions/FIN_0_1_3_REBASELINE_REDIRECT_INDEX.jsonl`

活动 import graph 当前为 58 个 Python 文件、7 个前端源文件、3 个 runtime resource、2 个 runtime detector，未发现历史产品链引用或未解析 import。历史文件没有删除；完整旧 Project OS 账本也保存在 `archive/versions/fin_0_1_3_prebaseline/docs/project_os/`。

## 已完成的重定基事实

1. `main` 的有效语义已先合入候选分支，避免最后一次盲 merge。
2. Case 公司身份合同和 Case→Evidence Pack digest 绑定已经实现。
3. `/workspace` 已成为唯一研究产品入口；旧产品页面重定向，旧产品 API 返回 typed HTTP 410。
4. `/operations` 独立保留运行配置、来源包、受控数据构建、运行记录与基线检查，不承诺旧 Agent 产品能力。
5. 当前 Runtime Registry 只含三个活动资源。
6. 6,052 个旧实现/证明/尝试文件、被替换的规范快照、旧 HTML 原型、脱敏 fixture 以及已完成使命的一次性迁移程序，均已按推断版本非破坏性迁移到 `archive/versions/`；逐文件保留 source、archive、SHA256、原因和替代物。156 个过长路径已用可逆 path map 改为可移植短路径，两份冲突的旧 S0–S5 流水账也已归档。
7. 当前 44 个 Python tests、TypeScript、Vite production build、桌面/移动两种数据模式共 12 个 Playwright tests 均通过。
8. 三案业务验收通过其有界范围；secret scan 扫描 6,230 个文件为 0 finding。
9. Dockerfile、Compose、无数据容器 503、只读 Evidence 挂载容器 200 与 DELL `15 Evidence / 16 gaps` 均已真实 smoke。
10. G12 从两份独立 clean-main 工作树执行。第一份自然暴露归档换行摘要漂移、旧前端 fallback 和 Windows/Docker 保留端口问题；修复进入 `main` 后，第二份 clean-main 在无历史 `dist`、无 `node_modules` 的条件下完整通过。

## G12 关闭的可复现性缺陷

1. archive digest 改为读取 Git index 中的 canonical blob；Windows checkout 的 CRLF 不再改变历史内容身份。
2. 后端只消费 `apps/workbench/frontend/dist/index.html`；未构建时返回 typed 503 `frontend_not_built`，不再退回旧源码 HTML。
3. Playwright 前端端口默认使用 4173，并允许通过经校验的 `FINSIGHT_E2E_FRONTEND_PORT` 覆盖；不再固定占用 Docker Desktop 常见排除区间内的 5173。
4. 前端冷启动以 `package-lock.json + npm ci` 为权威；本地 pnpm 只可作为 npm 启动载体，不得生成或提交第二份 lock/workspace。

## 尚未完成，不能提前宣称通过

1. DELL、MU、NVDA 只覆盖 SEC 且结构化数值项为 0，必须按当前计划留在后续 S1/S2/S3，不能伪装为本次已完成能力。
2. Workbench 镜像仍安装数据构建依赖，冷缓存构建成本偏高；依赖拆分是非阻断基础设施优化，不能回滚已验证的数据/状态隔离。
3. Python 基础镜像与依赖目前可从 clean-main 构建并通过；更强的镜像/依赖字节级锁定属于后续基础设施加固，不得被误写为当前研究能力，也不阻断已通过的仓库基线。

## 决策与停止规则

- 不用增加新版本逃避当前失败；失败留在所属 gate 修复。
- 不再为单个历史 attempt 增加活动 runner、配置或测试。
- 不把 archive 中的 proof、fixture 或报告称为当前能力。
- 私有数据继续外置或挂载，不复制进 Git。
- 若业务验收发现当前三案例数据本身不可信，停止发布并在当前 FIN 0.1.3 修复；若只是未来动态研究能力缺失，记录为后续产品范围，不把它偷偷塞回本次重定基。
- 任何 materially changed scope 都要先向 Owner 说明。

## 当前下一步

`FIN_0_1_3_S1_RETRIEVAL_VERTICAL_SLICE`

仓库基线通过后回到 [FIN 0.1.3 当前 S0–S5 计划](../product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md)，不能把 baseline merge 写成 FIN 0.1.3 产品 release。
