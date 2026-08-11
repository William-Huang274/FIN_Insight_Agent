# RD6 Agent Runtime Consumption Contract

- Generated at: `2026-06-26T17:52:42+00:00`
- Status: `pass`
- Company briefs: `603`
- Role evidence packs: `3618`
- Selected evidence refs: `80656`
- Gap refs: `25`
- Invalid selected gap rows: `0`

## Outputs

- `agent_runtime_data_briefs`: `D:\FIN_Insight_Agent\data\manifests\agent_runtime_data_brief_v0_1.jsonl`
- `role_specific_evidence_pack_registry`: `D:\FIN_Insight_Agent\data\manifests\role_specific_evidence_pack_registry_v0_1.jsonl`
- `sqlite`: `D:\FIN_Insight_Agent\data\workbench_private\research_data\agent_runtime_consumption_contract_v0_1.sqlite`
- `summary`: `D:\FIN_Insight_Agent\data\manifests\agent_runtime_consumption_contract_summary_v0_1.json`
- `report`: `D:\FIN_Insight_Agent\docs\internal\vnext_20260610\rd6_agent_runtime_consumption_contract.zh-CN.md`

## Pack Status Counts

| Status | Packs |
| --- | ---: |
| `pass` | `3618` |

## Role Gap Counts

| Role | Gap packs |
| --- | ---: |

## Boundary

- Research Lead 先读 compact data brief，再生成 retrieval / repair plan。
- Specialist 只消费 role-specific EvidencePack 引用，不直接扫散装 JSONL。
- Memo Writer 不接触 raw retrieval / tool observations，只消费 JudgmentState、MemoLogicPlan、verified ClaimCards 和 bounded gaps。
- `planning_or_gap_only` rows 不得进入 selected evidence refs；只能进入 gap summary。
