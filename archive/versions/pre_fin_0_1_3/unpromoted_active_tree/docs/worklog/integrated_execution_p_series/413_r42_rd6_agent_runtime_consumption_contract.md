# R42 RD6 Agent Runtime Consumption Contract

## Problem

RD0-RD5 已经把 raw inventory、source provenance、parser ledger、Gold Mart、Graph Store 和 Retrieval Index Registry 建起来，但 agent runtime 仍需要稳定消费入口。否则 Research Lead 仍可能依赖 prompt 记忆和散装 JSONL，specialist 仍可能拿到混杂证据，Memo Writer 仍可能被 raw retrieval / tool observation 污染。

## Decision

把 RD0-RD5 主账本压成两个 runtime-facing contract：

- `AgentDataBrief`：每家公司一条 compact brief，给 Research Lead 做 retrieval / repair / specialist dispatch planning。
- `RoleEvidencePack`：每家公司每个 specialist role 一条 pack，只含可进入 evidence bundle 的 Gold Mart refs；gap-only rows 单独登记，不得进入 selected evidence。

Memo Writer 输入边界同步固化：只允许 `JudgmentState + MemoLogicPlan + verified ClaimCards + bounded gaps + role_evidence_pack_refs`。

## Work Completed

- 新增 `src/sec_agent/agent_runtime_consumption_contract.py`。
- 新增 `scripts/data_expansion/build_agent_runtime_consumption_contract.py`。
- 新增 `tests/test_agent_runtime_consumption_contract.py`，覆盖 company brief、role pack、gap-only 防提权和 SQLite parity。
- 物化：
  - `data/manifests/agent_runtime_data_brief_v0_1.jsonl`
  - `data/manifests/role_specific_evidence_pack_registry_v0_1.jsonl`
  - `data/manifests/agent_runtime_consumption_contract_summary_v0_1.json`
  - `data/workbench_private/research_data/agent_runtime_consumption_contract_v0_1.sqlite`
  - `docs/internal/vnext_20260610/rd6_agent_runtime_consumption_contract.zh-CN.md`
- 更新 24 文档和 master checklist。

## Result And Evidence

真实构建结果：

| Metric | Value |
| --- | ---: |
| status | `pass` |
| company data briefs | `603` |
| role EvidencePacks | `3,618` |
| expected role EvidencePacks | `3,618` |
| selected evidence refs | `80,656` |
| gap refs | `25` |
| invalid selected gap rows | `0` |
| SQLite briefs / packs | `603 / 3,618` |

样例审计：

- `NVDA` brief：exact facts `37`，bounded signals `171`，planning gaps `0`。
- 非美样例 `000660.KS`、`005930.KS`、`1211.HK` 均有 fundamental / product / industry / market / capital / risk 六类 pack。

Verification:

- `python -m py_compile src/sec_agent/agent_runtime_consumption_contract.py scripts/data_expansion/build_agent_runtime_consumption_contract.py`
- `python -m pytest tests/test_agent_runtime_consumption_contract.py -q` -> `3 passed`
- `python scripts/data_expansion/build_agent_runtime_consumption_contract.py` -> `status=pass`

## Boundary And Follow-Up

- RD6 证明每家公司、每个 specialist role 都有稳定可消费 EvidencePack，不证明每家公司每个研究维度都有同等深度。深度差异仍由 RD7 / full-chain eval / case design 审计。
- `planning_or_gap_only` rows 只作为 gap refs，不进入 selected evidence refs。
- 下一步 RD7 需要把 raw fetch、parser、chunk/table、retrieval lineage、source authority misuse、graph evidence、role pack selection 和 full-chain release gate 接成统一 Data Quality / Release Eval Gate。
