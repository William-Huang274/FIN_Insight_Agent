# 103 P33 Gold-depth Runtime Assimilation

日期：2026-07-07

## 问题

用户确认下一步不是继续加门控，而是把 AI/Semis humanmade gold 内容接进真实链路：

```text
Evidence Fusion / ProductIntelligenceGraph / Specialist / Aggregate / MemoLogicPlan
```

上一轮状态是 `HumanmadeGoldSetAudit` 已经接到 Memo Writer 前，但当前 accepted aggregate r7 仍失败。失败说明已有工程 gate 只能阻断 paid writer，不能让 briefing pack 自动变深。

## 决策

本轮按 Project OS / Global Stewardship 口径执行：

- 不跑 paid LLM；
- 不跑 full-chain；
- 不扩 case；
- 不把 gate pass 当作 gold workpaper pass；
- 修最早 owned runtime consumption 缺口：human source rows / ProductIntelligenceGraph edges / specialist judgment material / MemoLogicPlan 没有统一进入当前 aggregate checkpoint。

## 完成内容

### 1. Runtime assimilation

新增 `assimilate_ai_semis_gold_depth_content_pack()`：

- 把 `ai_semis_gold_depth_content_pack` 的 rows 合并进 `evidence_fusion_bundle.authority_rows`；
- 把 ProductIntelligenceGraph investment edges 写入 `product_intelligence_graph_projection`；
- 把 specialist answer-exemplar style materials 写入 `gold_specialist_judgment_materials`；
- 生成 `gold_depth_claim:*` 和 `gold_depth_judgment:*`；
- 合并进 `verified_judgment_plan` / `judgment_plan`；
- 合并进 `memo_logic_plan.required_item_answer_plan`、`sections`、`judgment_cards` 和 `evidence_to_thesis_bridge`；
- 在 `lead_review_checkpoint` 记录 `humanmade_gold_depth_review`。

### 2. Stale unsupported claims supersession

本轮发现原始 r7 的旧 `unsupported_claims` 会继续否决已经补入的 gold-depth material，例如：

- GOOGL TPU product specs；
- DELL AI server margin quality / GPU pass-through / backlog conversion。

修复方式不是删除边界，而是把已由 gold-depth material 解决的旧 unsupported row 移到：

```text
gold_resolved_unsupported_claims
```

并保留：

```text
boundary_preserved_in = gold_depth_claim.cannot_infer
```

未被解决的 market/capital-flow、customer concentration、export-control 等仍保留为 typed unsupported boundary。

### 3. CLI 和报告

`scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py` 新增：

```text
--assimilate-gold-depth-content
--assimilated-aggregate-out
```

并修正 markdown 报告措辞：

- 原始 accepted r7 fail baseline 与 assimilated checkpoint pass 必须区分；
- assimilated pass 只允许作为 scoped paid Memo Writer node 的候选输入；
- 不允许误记为 full-chain、模型对比、case expansion 或 accepted gold workpaper pass。

## 产物

- `src/sec_agent/humanmade_gold_set_runtime.py`
- `scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py`
- `tests/test_p33_humanmade_gold_set_runtime_quality_gate.py`
- `docs/project_os/humanmade_gold_set_runtime_quality_gate_v0_1.json`
- `docs/project_os/humanmade_gold_set_runtime_quality_gate_assimilated_v0_1.json`
- `docs/project_os/ai_semis_gold_depth_content_pack_v0_1.json`
- `docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json`
- `docs/internal/vnext_20260610/p33_humanmade_gold_set_runtime_quality_gate_v0_1.zh-CN.md`
- `docs/internal/vnext_20260610/p33_humanmade_gold_set_runtime_quality_gate_assimilated_v0_1.zh-CN.md`

## 验证

运行命令：

```text
python -m py_compile src/sec_agent/humanmade_gold_set_runtime.py scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py
python -m pytest tests/test_p33_humanmade_gold_set_runtime_quality_gate.py -q
python scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py
python scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py --assimilate-gold-depth-content --json-out docs/project_os/humanmade_gold_set_runtime_quality_gate_assimilated_v0_1.json --md-out docs/internal/vnext_20260610/p33_humanmade_gold_set_runtime_quality_gate_assimilated_v0_1.zh-CN.md --content-pack-out docs/project_os/ai_semis_gold_depth_content_pack_v0_1.json --assimilated-aggregate-out docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json
```

结果：

```text
py_compile: pass
targeted tests: 8 passed

baseline accepted r7:
  HumanmadeGoldSetAudit.status = fail
  allow_paid_memo_writer = false
  BriefingPackQualityGate.fail_count = 6

assimilated checkpoint:
  HumanmadeGoldSetAudit.status = pass
  allow_paid_memo_writer = true
  BriefingPackQualityGate.fail_count = 0
  NegativeFailureGates.status = pending_final_memo
  NegativeFailureGates.fail_count = 0
```

## 更新的 source-of-truth

- `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/capability_status_ledger.jsonl`
- `docs/project_os/root_cause_issue_ledger.jsonl`
- `docs/worklog/README.md`

## 边界

这一步证明的是 no-paid runtime consumption：

```text
human source rows / PIG investment edges / specialist judgment material
 -> Evidence Fusion / JudgmentPlan / MemoLogicPlan
 -> HumanmadeGoldSetAudit pass
```

它不证明：

- paid Memo Writer prose 质量；
- renderer / verifier 通过；
- Workbench dogfood；
- broad full-chain；
- DeepSeek / GPT 模型对比；
- case expansion；
- accepted gold workpaper。

下一步只有在用户明确批准后，才可从：

```text
docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json
```

跑一个 scoped paid Memo Writer node。若输出仍像搜索结果总结，必须定位最早 faulty artifact，不能继续烧 full-chain token。
