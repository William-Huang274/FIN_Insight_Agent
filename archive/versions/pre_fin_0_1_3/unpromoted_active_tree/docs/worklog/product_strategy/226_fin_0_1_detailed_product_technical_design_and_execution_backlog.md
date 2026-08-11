# 226 FIN 0.1 产品与工程详设及执行清单

日期：2026-07-17
状态：`detailed_design_v1_documented / implementation_not_started`

## 问题

`REL-PROD-001` 已有完整产品功能范围和 Release 概设，但仍需要执行者自行推断页面、API、对象、状态、权限、代码路径、阶段验收和 rollback。用户明确要求把“概设”升级成不依赖隐含知识的“详设”。

审计同时确认：现有 React `main.tsx` 约 3512 行、FastAPI `app.py` 约 1115 行，历史 R53-R60/generic run 能力很多，但不能直接当成 FIN 0.1 canonical product implementation；若不冻结迁移边界，后续容易继续堆单文件、复制 source of truth 或只交付 JSON/API。

## 决策

1. 新增独立产品与工程详设，Release 概设只保留目标、范围、Point 顺序和 gate。
2. 详设固定 8 个浏览器 routes、10 个 UI read models、`/api/v1` command/query 族、Case workflow projection、event/persistence、权限、typed error 和 next action。
3. 复用现有 React/TypeScript/Vite/FastAPI，但拆成 AppShell、feature modules、typed API client 和 application services；旧 R53-R60 routes 作为 legacy adapter 保留。
4. Point 02-07 拆为 38 个 execution points；每项记录 owner、依赖、代码路径、输出、`skeleton/fixture/full/calibrated` acceptance 和 stop rule。
5. 四周列车按 WS-A/WS-B/WS-C 并行，周末必须有可演示纵向路径；时间不足先减 provider breadth、非 material slots 和视觉 polish，不能删 Evidence/Numeric、Review、Provenance 或 rollback。
6. 详设追加 `P02.0` 九步启动 Runbook；只有 entry/authority/object/route/dependency/OpenAPI/fixture/cross-owner review 全部冻结后，才解锁 `P02.1` 后端 Case service 与 `P02.2` 前端 AppShell 两条并行实现。

## 产出

- `docs/architecture/repository/RELEASE_FIN_IA_0_1_DETAILED_PRODUCT_TECHNICAL_DESIGN_20260717.zh-CN.md`；
- `configs/releases/fin_ia_0_1_detailed_execution_backlog_v1_0.json`；
- ReleaseContract/FeatureScope 新增 detailed design/backlog refs；
- Release 概设、Operating Model、FeatureScope 和 repository index 回指详设。

## 验证目标

- 机器清单包含 Point 02-07 六个 Point、38 个 execution points、15 个唯一 feature IDs；
- 每个 execution point 都有四阶段 acceptance、owner、dependency、path/output 和 stop rule；
- ReleaseContract、FeatureScope、详设和 backlog 引用可解析且文件存在；
- JSONL、Git diff 和 secret scan 在本轮 closeout 执行。

## 本轮校验结果

- Release/FeatureScope/Backlog 三份 JSON 均可解析，`release_id=REL-PROD-001`；
- backlog 包含 Point 02-07 共 6 个 Point、38 个唯一 execution point IDs、15 个唯一 feature IDs；
- 38 个 execution points 均具有 owner、dependency、implementation path、output、stop rule，以及 `skeleton/fixture/full/calibrated` 四阶段 acceptance；
- ReleaseContract、FeatureScope、详设和 backlog 的双向引用均存在；
- capability/root-cause 两份 JSONL 全量逐行解析通过；
- 本轮只校验规划合同与文档引用，没有执行 FIN 0.1 前端、API、runtime、浏览器 E2E 或业务 Case。

## 边界

- 本轮只完成 detailed design 与 machine backlog，没有修改前后端 runtime；
- 没有运行 model、network、paid/full-chain、外部工具、业务 Case mutation 或 production cutover；
- Point 02 实现仍受 `REL-FND-001:POINT01_FOUNDATION_ALPHA_COMPLETE` 阻断；
- exact dependency versions、local identity profile、SQLite/ObjectStore release path、feature flag name 和 Playwright seed 必须在 `P02.0` ADR/lockfile/schema 中冻结，本文不替执行者静默选择。
