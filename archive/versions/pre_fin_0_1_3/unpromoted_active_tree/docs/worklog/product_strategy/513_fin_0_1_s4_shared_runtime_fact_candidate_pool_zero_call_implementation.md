# 513｜FIN 0.1 S4 shared-runtime Fact candidate pool 零调用实现

## 结论

用户以“继续”执行 worklog 512 已签发的唯一未来结构包。包 `1/1` 已消费：
Fact candidate generation 已从 Provider 权限移到共享 Runtime 的本地确定性
planner。当前 DELL/MU/NVDA full-fake 均达到
`6 nodes / 12 calls / 12 captures / 9 Artifacts`。

这是 current-worktree 工程实现与 fixture proof，不是独立 fresh-agent proof，更
不是 exact-live 产品验收。T06 保持
`engineering_pass / live_product_blocked / not closed`。

## 实现

- 新增 `fin01.s4.fact_candidate_pool_profile:v1` 和
  `fin01.s4.fact_candidate_pool_plan:v1`。
- 版本化 profile 严格由 `(research_profile_ref, program_cell_id)` 定位，共
  覆盖 DELL、MU、NVDA 三案九个 profile-cell 对。
- 每个 eligible support 必须唯一映射 typed coverage slot，或命中显式
  audit-only rule；unknown role、overlap、scope、digest、minimum 与 capacity
  fault 均在 Provider 前 fail-closed。
- eligible≤6 时完整候选集保留；eligible>6 时根据 typed minima 和稳定本地
  rank 形成恰好 6 个 Provider-visible aliases。
- Provider 只能返回可见池中的 `1..6` 个 candidates；隐藏、cross-case、
  duplicate、第七项均拒绝，不静默截断、不 retry。
- 本地继续全量验证 candidates，并稳定选择最多 3 个最终 Facts。
- 公开 receipt 仅含 profile/catalog/pool digest、计数与 slot count，不含原始
  事实正文或数值。

## 验证

- catalog counts：`0/1/3/6/7/22`
- eligible≤6 完整保留：通过
- permutation stability：通过
- profile/scope/digest/unknown-role/overlap/minimum mutation：fail-closed
- hidden/cross-case/duplicate/seventh candidate：fail-closed
- pre-Provider planner fault：Provider calls=`0`，typed failure telemetry 已物化
- DELL/MU/NVDA：各 `6/12/12/9`
- MU eligible/visible：`5/5、22/6、27/6`
- focused tests：`15 passed`
- 相邻 runtime safety：除历史 current-next allowlist 快照外无功能回归
- credential/model/provider/network/source/admission/live/paired/owner/T07：全 0

实现记录：
`configs/releases/fin_ia_0_1_s4_shared_runtime_deterministic_fact_candidate_pool_planner_minimum_zero_call_implementation_v1_0.json`

实现记录 SHA：
`03af7943dd7c544f6da2c8e93aa6faacebcc15e4774a1f11fcc3c2ab63704a9b`

## 产品边界

RC-P36-084 已从“已授权未实现”推进为
`runtime_injected_current_fixture_proven_independent_fresh_proof_pending`。
RC-P36-080 的正式九 Artifact L1 仍未建立；本轮没有生成、修改或晋升任何真实
业务 Artifact。paired assessment 与 owner acceptance 不具资格，T07 未进入。

## 下一项

`S4-SHARED-RUNTIME-DETERMINISTIC-FACT-CANDIDATE-POOL-PLANNER-INDEPENDENT-FRESH-AGENT-PROOF-DECISION`

下一项需单独授权；本实现不自动授权 credential read、model call、admission、
exact-live、paired assessment、owner acceptance、T06 closeout 或 T07。

## Postflight

- implementation + record + deterministic full-chain：`43 passed`
- capture/terminal/L1 safety：`34 functional passed`；另有 1 条历史
  current-next allowlist 快照未包含本轮新 next，未作为 Runtime 回归处理
- compileall：pass
- release/profile/backlog/preflight JSON：5 份有效
- Project OS JSONL：4 个文件、合计 1,310 行有效
- 下一项 scope preflight：`pass / open blockers 0`
- task 新增内容 credential-pattern scan：0
- `git diff --check`：pass
- Git 基线保持混合工作树：branch=`codex/layered-data-source-expansion`，
  HEAD=`54d2e072`，ahead/behind=`5/0`
- 未 stage、commit 或 push
