# FIN 0.1.3 严格主线重定基验收与迁移程序

更新：2026-08-12
状态：`mainline G01–G12 pass; repository baseline complete; product iteration open`

## 目标

建立一个可由人和 Agent 在一次恢复中读懂的 FIN 0.1.3 主线：一个研究产品入口、一个运维入口、一个活动 Runtime 注册表、一份当前计划和一个不可执行历史归档。迁移不删除历史，也不把历史 proof 改写为当前能力。

## 当前结构

```text
apps/workbench/        当前浏览器产品与后端组合根
src/                   当前稳定领域、数据和运行时模块
scripts/               准入数据构建、启动和基线治理入口
tests/                 当前 pytest 门
configs/runtime/       当前 Runtime 资源
configs/repository/    当前机器合同和验收报告
docs/                  PRD、当前计划、代码图、质量标准、Project OS
archive/versions/      不可执行历史与逐文件 SHA256 重定向
data/                  外置/挂载数据根；私有对象不进 Git
```

## 严格门

| Gate | 含义 | 主线状态 |
| --- | --- | --- |
| G01 | `main` 有效语义先合入候选 | pass |
| G02 | `/workspace` 与 `/operations` 是唯一产品/运维前门 | pass |
| G03 | Case 身份、as-of、case version、artifact/payload digest 绑定 | pass |
| G04 | 活动 import graph 和 Runtime Registry 最小且无旧引用 | pass |
| G05 | 旧消费者为 0；旧页面 redirect、旧 API typed 410 | pass |
| G06 | 历史非破坏性归档，逐文件 digest/index 可重建 | pass |
| G07 | README、PRD、当前计划、技术图、CI 和机器 manifest 一致 | pass |
| G08 | 当前 Python、TypeScript、Vite 和 browser tests 全绿 | pass：44 tests＋两种数据模式共 12 个 browser tests |
| G09 | DELL/MU/NVDA bounded 业务语义检查 | pass；只限 reviewed Evidence Workspace |
| G10 | 桌面/移动、挂载/未挂载两种 UI 行为 | pass；包含无横向溢出 |
| G11 | secret、startup、Compose/container smoke | pass；含只读 Evidence/可写 state 分离 |
| G12 | 合并并推送 `main` 后从干净工作树完整复证 | pass：clean `origin/main` `cd9990ac` |

唯一机器状态位于 `configs/repository/fin_0_1_3_strict_mainline_rebaseline_acceptance_v1_0.json`；本表不独立拥有最终状态。

## 迁移不变量

1. 归档文件不得被当前 import、Runtime Registry、CI 或产品 UI 消费。
2. 每个归档文件保留 source path、archive path、origin version、原因、替代物、分类和 SHA256。
3. 私有 Evidence 对象、凭据、模型 capture、生成索引和本地运行状态不进 Git。
4. 无 Evidence mount 时产品必须 fail visibly：案例目录可读、详情禁用、readiness=503。
5. 合并前任何 gate 失败都留在本 gate 修复；不得恢复 attempt-specific 旧模块或创建新产品版本。
6. 合并后 proof 必须从干净 `main` 工作树执行；候选分支上的结果不能替代 G12。

## 验收命令

```powershell
python scripts/engineering/verify_active_baseline.py --pretty
python scripts/engineering/build_archive_redirect_index.py --check
python scripts/engineering/check_repository_secrets.py
python -m compileall -q apps src scripts
python -m pytest -q

cd apps/workbench/frontend
npm run typecheck
npm run build
npm run test:e2e
```

挂载私有 reviewed Pack 后另执行三案例业务验收和 browser test。容器必须在未挂载数据时明确返回 `data_mount_required`，不能把缺数据的镜像标为产品 ready。

## G12 clean-main 发现与处置

G12 没有把候选缓存当作证明。第一次 clean-main 自然暴露并在本 gate 关闭三项缺陷：archive SHA 受 checkout 换行影响、后端可退回旧 HTML、Playwright 固定 5173 会撞上 Docker Desktop 的 Windows 排除端口。修复合并 `main` 后，第二份 clean-main 从零安装前端依赖、构建并完成全套复证。前端依赖的唯一权威仍为 `package-lock.json + npm ci`，没有引入 pnpm lock 或第二套工作区。

## 完成语义

G01–G12 全部通过后，只能宣布“FIN 0.1.3 清晰仓库基线已合并主线”。FIN 0.1.3 产品版本仍按当前 S0–S5 计划继续；动态检索、NumericFact、Agentic Research、完整报告和 release 必须分别通过自己的产品门。
