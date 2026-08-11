# 395 — S3-T09 Verifier typed-ref 与语义 finding 零调用处置

日期：2026-07-25
状态：`L2_repaired / L1_pass_for_retained_content / L3_findings_carried / T09_blocked`

## 目标与授权

用户以“可以”授权执行上一项
`S3-T09-VERIFIER-TYPED-SCOPED-REF-L2-RECOVERY-AND-L1-SEMANTIC-FINDINGS-DISPOSITION-ZERO-CALL`。
本轮不授权模型、Provider、网络、来源、工具、新 admission、第二次
exact-live、captured-output promotion、Artifact 合成、paired comparison、
owner acceptance、T10、S4、release 或 production。

## L2 根因修复

最早 faulty contract 是 output-v4 Verifier 的 exact-ref representation：
request 只写 `exact ref`，Provider 返回现有三字段 typed scoped-ref，本地
validator 却只接收 nonblank string。

修复后：

- request 使用 `CellScopedResearchIdentityPolicy.wire_schema("claim")`；
- local validator 对同一 scoped identity surface 做精确 membership 校验；
- raw local ID、unknown、wrong kind、wrong Cell、duplicate 均 typed fail-closed；
- 不做 trim/case-fold/fuzzy match/identity guessing/silent rewrite；
- pre-Artifact Verifier 当前只支持 Claim refs，Artifact refs 不冒充进入该合同；
- Provider schema、validator 与 fake Provider 继续共享 request contract。

## L1 finding 审计

只读审计上一 exact-live 的 12 个 restricted captures，没有重新调用模型，
没有把 capture 晋升为 Artifact。

1. `scope_digest_mismatch`
   - Writer scope digest 由本地从每个已验证 Claim scope 直接派生；
   - capture 没有给出与 canonical scope digest 冲突的证据；
   - 处置为 `not_substantiated_model_finding`，该检查归本地 deterministic owner。
2. `unresolved_cross_cell_conflict`
   - Lead 中确有两个 unresolved conflict；
   - Writer limitations 完整保留全部 upstream `cannot_support` 边界；
   - 没有把 cannot-infer 改写成支持结论；
   - 处置为已披露的 L3 analytical-quality debt，不构成 L1 硬错误。
3. `unattributed_company_total_margins`
   - 两个 Memo rendering 均明确写“公司整体”；
   - 没有归因到 AI 基础设施、Data Center、accelerator 或 segment；
   - 处置为已披露的 L3 分析 gap，不构成 unsupported attribution。

因此，对当前 retained node content 没有确认 L1 hard-integrity violation。
这不等于历史 Run 成功，也不等于 T09 产品完成。

## 实现与证据

- `apps/workbench/backend/application/bounded_agent_executor.py`
- `scripts/releases/audit_fin_ia_0_1_s3_t09_verifier_typed_scoped_ref_and_semantic_findings_zero_call.py`
- `configs/releases/fin_ia_0_1_s3_t09_verifier_typed_scoped_ref_l2_recovery_and_l1_semantic_findings_disposition_v1_0.json`
- `tests/contract/test_fin_0_1_s3_t09_verifier_typed_scoped_ref_l2_recovery.py`
- `docs/architecture/fin_0_1_s3_cell_scoped_research_identity_contract_v1.md`

## 验证

- restricted capture read-only audit：pass，12 captures、7 refs、5 unique refs；
- typed refs 全部 exact known Claim refs；
- locally assembled Claim scope digests：exact；
- Writer limitations 与全部 upstream boundaries：exact；
- focused regression：`62 passed`；
- Specialist/Lead/Writer/layered 相邻回归：`72 passed`；
- 一次全量 S3-T09 单批执行在 300 秒外层限制后没有返回 assertion
  汇总，结果标为 inconclusive；确认并停止该次 pytest 进程，没有把超时冒充
  pass 或 fail；
- strict JSON 检查发现 backlog `next_action` 内有 20 组历史重复键；保留
  最新有效字段，把较早重复值改为带阶段前缀的 historical 字段，未删除历史
  值，严格 duplicate-key 解析现已通过；
- 下一零调用 proof-decision scope 的 Project OS preflight：pass。

历史 `failed/failed/failed`、Artifact=0、paired comparison=false、
owner acceptance=false 均保持不变。本轮模型/Provider/网络/来源/工具/
admission/Run/Artifact/promotion/comparison/owner write 均为 0。

## 下一步

仅进入需另行授权的零调用 decision：

`S3-T09-LAYERED-VERIFIER-TYPED-REF-AND-FINDING-DISPOSITION-FRESH-AGENT-PROOF-DECISION`

在该 decision、fresh proof、Project OS preflight 与后续独立 issuance authority
之前，不签发 admission，不执行第二次 exact-live。
