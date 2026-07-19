# 120 - P38 Repository deep audit / cleanup / reference graph

记录时间：2026-07-11

## 用户要求

在按新 PRD/TECH 实施前，先做项目深度审计和仓库整理：

- 清理生成缓存和明确冗余代码，必要时迁入 archive；
- 盘点当前代码、脚本、测试、RAG、向量库、数据库和图谱成果；
- 对照 PRD/TECH 判断已实现、已验证和未闭环能力；
- 生成脚本/文档功能关系图与引用图，并作为持续维护资产；
- 为后续代码增长增加复杂度、安全冗余和可追溯约束。

## 完成内容

### 仓库整理

- 清理 69 个 `.tmp_*`、tmp/cache/pycache 生成目标，释放约 1.46 GB。
- 将 4 个无当前 runtime/test/package export 引用的 v0.1 检索原型迁入 `archive/code/v0_1_retrieval_prototypes/`。
- 保留大型 DB/index/RAG/raw/reports/eval 资产，未做无 lineage 的破坏性删除。
- 为 archive 增加 README、替代方向和禁止 active runtime 反向依赖的规则。

### 持续结构审计

新增：

- `configs/repository/architecture_inventory_policy_v0_1.json`
- `configs/repository/code_health_guard_policy_v0_1.json`
- `src/sec_agent/repository_architecture_inventory.py`
- `scripts/engineering/build_repository_architecture_inventory.py`
- `scripts/engineering/check_repository_architecture_guard.py`
- `tests/test_repository_architecture_inventory.py`
- `data/manifests/repository_architecture_inventory_v0_1.json`
- `data/manifests/repository_code_health_guard_v0_1.json`
- `docs/architecture/repository/REPOSITORY_ARCHITECTURE_MAP.zh-CN.md`
- `docs/architecture/repository/REPOSITORY_DEEP_AUDIT_20260711.zh-CN.md`

最终静态图记录 1,690 个节点、7,302 条引用边、885 个 stable-entrypoint 可达对象、0 Python parse error、0 missing stable entrypoint、0 未裁决 review candidate。机器可读 JSON 保留完整 node/edge，Markdown 保留可读功能图、目录职责、复杂度热点和数据资产摘要。

### 测试审计

- full collection：1,949 tests。
- full local pytest：1,938 passed / 12 failed，约 9 分 11 秒。
- repository inventory/guard targeted tests：3 passed。
- 12 个失败不涉及本轮归档文件，主要属于 D-series conflict contract、schema 类型、unit gate、registry/budget 版本漂移、renderer surface 边界、依赖真实本地数据的 specialist selector 非 hermetic 测试，以及 chain performance 5/7。

本轮没有为了“全绿”放宽 Evidence/permission/safety gate。新增 root-cause issue 要求先冻结合同、隔离 fixture store、版本化 budget/source family，再决定修实现还是修测试预期。

### 数据资产结论

- `data/` 约 75 GB、11,706 files。
- 静态 inventory 识别 78 个数据库、40 个 index artifacts、19 个 lexical indexes、3 个 vector/Milvus artifacts、488 个 manifests。
- 历史 registry 声明 22 个 index snapshots、约 1,258.5 万 records；Milvus 581 tickers / 662,908 vectors；ProductIntelligenceGraph 603 companies / 36,046 nodes / 71,034 edges。
- 这些数字证明资产沉淀，不证明所有记录 freshness、authority、numeric lineage 或 DecisionSurface runtime consumption 已通过。

## PRD/TECH 对齐判断

当前代码主体是“多代可用资产 + 分散 runtime/fixture”，不是新 PRD stable object graph 的完整实现。主要缺口仍是：

- Lead/specialist/aggregate 未统一消费 DecisionSurfaceCell；
- EvidenceRequest/Candidate/PromotionDecision/NumericTrace 未形成唯一证据主干；
- ToolGateway、ContextInjectionPlan、WorkUnit/Attempt、DecisionSurfacePack、LeadReviewDecision 尚未成为统一 runtime source of truth；
- Workbench 仍缺 decision-cell review 与跨 artifact consistency；
- trajectory eval/self-improvement 资产丰富但未统一；
- P36 supervisor supplement 仍不能算 runtime evidence。

## 复杂度与安全规则

- 7 个核心 Python 文件超过 4,000 行，前端 `main.tsx` 也超过 3,500 行；这些文件进入 grandfathered budget，不允许继续无界增长。
- 新增未登记 4,000 行热点、active dependency on archive、缺失 stable entrypoint、Python parse error、tracked secret/private/generated roots 将使 guard 失败。
- 新职责应拆成 pure contract、selector、state transition、adapter，并配 characterization/contract test。
- 权限、证据晋升、artifact version、idempotency、tenant/license 和 release hash 应在共享 gate 实现，不在各 agent 复制安全逻辑。

## 明确边界

- 未运行 paid LLM；
- 未运行 true full-chain；
- 未运行 source ingestion 或 parser promotion；
- 未关闭 P36 blocker；
- 未把旧 fixture/slice 宣称为 vNext runtime 完成；
- 未 commit 或 push。
