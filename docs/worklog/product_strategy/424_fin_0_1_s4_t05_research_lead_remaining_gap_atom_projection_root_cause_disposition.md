# 424｜FIN 0.1 S4-T05 Research Lead remaining-gap atom projection 根因处置

日期：2026-07-27
状态：`zero_call_disposition_complete / implementation_pending`

## 1. 问题

DELL R4 exact-live 的九个 Specialist segment 与三个 WWC 路径均通过，但 Research Lead 在显式 `remaining_gaps=1..4` 合同下返回 8 项，触发 `s3_bounded_research_lead_v3_cardinality_above_maximum`。R4 保持 `failed/failed/failed`、Artifact=0，未执行 paired assessment。

用户授权本轮只完成 `RC-P36-061` 零调用根因处置，不授权 runtime 修改、模型调用、replacement admission、第五次 DELL execution、paired assessment 或 S4-T06。

## 2. 零调用审计

- Provider 返回完整 JSON，`finish_reason=stop`，Research Lead 使用 965/1800 output tokens。
- Request 和本地 validator 都显式声明 `1..4`，因此不是 schema drift；直接故障是模型 cardinality nonconformance。
- 当前 validator 顺序是 list type → cardinality → item shape/text/authority/semantic。它在数量门禁处退出，因此历史 8 项没有逐项完成 shape、authority 和 semantic 校验。
- 历史 capture 与 terminal truth 不能被追溯截断、重写或重新分类。
- `fin01.agent_acceptance.layered_hard_integrity_and_quality:v1` 明确把可安全修复的 cardinality 放在 L2 recoverable protocol，而不是 L3 quality-only。现行 Research Lead 路径仍将该偏差直接 terminalize，构成 runtime alignment gap。

## 3. 决策

选择版本化共享合同：

`fin01.s3.research_lead_gap_atom_deterministic_projection:v1`

未来 Provider 只返回 `remaining_gap_atoms` 候选原子：

- `statement`
- `claim_ids`
- `what_would_change_task_ids`

Provider 不生成 canonical `gap_id`、rank 或自由分数。候选没有独立语义数量上限，继续受现有 raw-wire byte 与 node token hard envelope 约束。

本地 runtime 必须先逐项完成 exact shape、非空文本、alias kind/membership、authority、identity、semantic 与 hard-capacity 校验。只有全部候选通过且唯一偏差是候选数大于 4 时，才按以下稳定 tuple 选择 Top 4：

1. 有 non-empty what-would-change task；
2. linked Claim 最大不确定性：`cannot_infer > hypothesis > bounded_inference > fact_supported`；
3. 覆盖的 program Cell 数；
4. linked Claim 数；
5. canonical atom digest；
6. Provider ordinal。

本地随后生成 gap IDs、执行 exact alias expansion，并只把 1..4 个 canonical `remaining_gaps` 交给 Writer/Verifier。模型 statement 和 refs 不改写。

溢出记录为 non-terminal L2 finding：

`research_lead_gap_atom_overflow_deterministically_projected`

finding 必须记录 candidate/selected/overflow counts、policy ref、selected ordinals 和候选 digests，不持久化 raw statement/ref 文本，也不能隐藏 Provider nonconformance。

## 4. 硬边界

- 1..4 个有效候选：正常通过，无 overflow finding。
- 超过 4 个且全部逐项有效：L2 recoverable，确定性投影至 4。
- 0 个候选：必需语义输出缺失，L2 unrecoverable。
- malformed、blank、non-string candidate：fail-closed，不得静默丢弃。
- unknown/wrong-kind/cross-Cell/out-of-surface ref：L1 hard integrity failure。
- invalid/truncated JSON 或真实 byte/token/storage/security capacity 耗尽：unrecoverable/hard failure。
- 排序输入缺失或不一致：fail-closed，不猜测。

## 5. 明确拒绝与后传

- 不把上限从 4 改成 8；这只是移动阈值。
- 不只修改 Prompt、换 Provider 或重跑；这不修复可恢复协议的 owner。
- 不静默保留前四项，也不重写历史 capture。
- 不把所有 cardinality/item 错误降为 L3。
- 不增加 DELL 或 DeepSeek 特判。
- dependency/conflict/variant 和其他节点的通用 judgment-atom 框架、跨 Provider strict-schema capability matrix 后传 `S4-T10-to-S5`。
- 跨阶段 gap identity 与语义去重后传 S5 或更晚。

## 6. 产物

- `configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_remaining_gaps_cardinality_zero_call_root_cause_disposition_v1_0.json`
- `tests/contract/test_fin_0_1_s4_t05_dell_research_lead_remaining_gaps_cardinality_root_cause_disposition.py`
- S4 detailed/program backlog、Project OS ledgers/context/handoff、S4/Program execution plan 同步更新。

## 7. 验证

- `python -m pytest -q tests/contract/test_fin_0_1_s4_t05_dell_research_lead_remaining_gaps_cardinality_root_cause_disposition.py`
  - `6 passed in 0.36s`
- 完整 `test_fin_0_1_s4*.py`
  - `169 passed in 8.49s`
- 下一项 scoped Project OS preflight
  - `pass`
  - `open_full_chain_blocker_count=0`
- 变更涉及的 JSON/JSONL 逐项解析
  - `pass`

本轮没有运行模型、Provider、网络、Source、Tool、admission、ResearchRun、Artifact、paired assessment 或 Human Review，也没有修改 runtime。

## 8. 下一项

`S4-T05-DELL-RESEARCH-LEAD-REMAINING-GAP-ATOM-DETERMINISTIC-PROJECTION-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该项需独立授权，只允许实现上述最小共享合同、fake Provider 正负矩阵和 deterministic regression；不得直接签发 admission 或重跑 DELL。
