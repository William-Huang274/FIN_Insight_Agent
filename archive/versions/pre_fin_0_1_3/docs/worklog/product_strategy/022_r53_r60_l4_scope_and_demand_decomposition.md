# 022 R53-R60 L4 Scope And Demand Decomposition

日期：2026-06-29

阶段：R53-R60 product strategy / engineering framework

状态：docs-only clarification

## Prompt

用户要求把“每个切出来的 slice 都要满足企业级/生产要求才算通过”的口径写入 36 文档，并确认 S0-S10 涉及的 R 系列文档是否应先拆成更细的需求单再开始实现。

## Decision

采用 `L4_scope_pass` 作为每个 release slice 的最终 closeout 口径：

- `L4_scope_pass` 不要求每个 slice 都证明全系统 `L4_production_pass`；
- 它要求该 slice 在自己的职责范围内达到 enterprise-grade / production-grade 标准；
- `L1_contract_pass`、`L2_internal_dogfood_pass`、`L3_release_candidate_pass` 以后只作为中间门控，不再作为 slice 通过。

同时确认：S0-S10 不能直接从 R53-R60 高层文档跳到代码实现。必须先做 R 文档到需求单的拆分。

## Work Completed

- 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`：
  - 新增 `0.3 Slice Closeout 统一口径：L4_scope_pass`；
  - 把每个 S0-S10 的 `Target pass level` 改成“中间门控 + Slice closeout”双层口径；
  - 第 5 节改为按 `L4_scope_pass` 生成 `PassLevelDecision`；
  - 新增 `5.1 R 文档到可执行需求单的拆分办法`；
  - 第 7 节把当前里程碑改成 S0/S1/S2-S3/S5+ 的 `L4_scope_pass`。
- 更新 `docs/worklog/00_internal_master_checklist.md`。
- 更新 `docs/worklog/README.md`。

## Result

后续执行顺序被固定为：

1. 先在 S0 产出 `RDocumentInventory`；
2. 再产出 `RDocumentDemandMap`；
3. 再把 demand 拆成可独立 review/test/rollback 的 `DemandTicket`；
4. 再拆成具体 `ImplementationTask`；
5. 每个 slice closeout 必须留下 `GateArtifact` 和 `PassLevelDecision.closeout_level = L4_scope_pass`；
6. S0 未达到 `L4_scope_pass` 前，不进入 S1 主实现。

## Verification

本次为文档更新，未运行 runtime、后端、前端或 eval case。

需要收尾检查：

- `git diff --check`
- 候选文档 secret scan
- conflict marker audit

## Follow-up

- 下一轮真正进入 S0 时，先落 backlog schema / R-document inventory / R-demand map，而不是直接写 runtime code。
- S0 的 machine-readable backlog 应包含 `source_doc`、`source_section`、`slice_id`、`demand_id`、`capability_domain`、dependencies、`scope_l4_acceptance` 和 rollback。
