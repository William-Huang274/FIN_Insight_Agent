# 106 P33 Multi-case Gold-set No-paid Artifact Scope

日期：2026-07-07

## 问题

用户要求按四项推进：

1. AI/Semis deep case 做 fresh all-specialist gold pass。
2. 8 个 rubric gold cases 补 artifact-backed evidence-depth pack。
3. 6 个 negative gold cases 编译成 failure fixtures。
4. 跑 no-paid matrix audit。

通过条件是先用 deterministic / no-paid artifacts 证明 gold-set 研究质量尺子已经能被各节点消费，质量未达标前不允许通过，也不允许直接烧 paid full-chain。

## 决策

本轮不跑 paid LLM、paid specialist、paid Memo Writer、full-chain、模型对比、新检索、爬虫或 parser。先关闭当前 1-4 的 artifact scope，并明确它不是 live runtime / human dogfood / release pass。

## 完成内容

- 在 `src/sec_agent/humanmade_gold_set_runtime.py` 中新增 multi-case gold-set artifact builders：
  - `build_ai_semis_fresh_all_specialist_gold_pass()`
  - `build_multicase_goldset_evidence_depth_packs()`
  - `compile_negative_gold_failure_fixtures()`
  - `run_multicase_goldset_no_paid_audit()`
- 新增 runner：`scripts/eval_multi_agent/run_p33_multicase_goldset_no_paid_audit.py`。
- 新增测试：`tests/test_p33_multicase_goldset_no_paid_audit.py`。
- 生成 artifacts：
  - `docs/project_os/p33_multicase_goldset_no_paid_audit_v0_1.json`
  - `docs/internal/vnext_20260610/p33_multicase_goldset_no_paid_audit_v0_1.zh-CN.md`
  - `docs/project_os/p33_multicase_goldset_evidence_depth_packs_v0_1.json`
  - `docs/project_os/p33_ai_semis_fresh_all_specialist_gold_pass_v0_1.json`
  - `docs/project_os/p33_negative_gold_failure_fixtures_v0_1.json`

## 结果

No-paid audit strict mode 通过：

- `case_count=15`
- `artifact_ready_count=15`
- `fresh_all_specialist_pass_count=1`
- `negative_fixture_pass_count=6`
- `runtime_contract_ready_count=15`
- `blocking_case_count=0`

这说明 1 个 deep、8 个 rubric、6 个 negative gold cases 在 artifact-depth / fresh-specialist / negative-fixture 范围内已具备可运行工件。AI/Semis deep case 不再依赖 targeted repaired composite 冒充 fresh all-specialist。

## 验证

已运行：

```text
python -m py_compile src/sec_agent/humanmade_gold_set_runtime.py scripts/eval_multi_agent/run_p33_multicase_goldset_no_paid_audit.py
python scripts/eval_multi_agent/run_p33_multicase_goldset_no_paid_audit.py --strict
python -m pytest tests/test_p33_multicase_goldset_no_paid_audit.py -q
python -m pytest tests/test_p33_humanmade_gold_set_runtime_quality_gate.py tests/test_p33_humanmade_gold_set_matrix_audit_runner.py -q
```

## 边界

- Rubric / negative case 的 evidence-depth pack 是 gold-exemplar-backed artifact，不代表 live source ingestion、crawler、parser 已真实覆盖对应行业。
- 没有证明 paid Memo Writer prose、final rendered workpaper、真实 Workbench dogfood、human reviewer acceptance、full-chain、模型对比、case expansion 或 release readiness。
- `RC-P33-019-humanmade-gold-set-runtime-depth-gap` 仍保持 open，只是从 “multi-case artifact-depth blocked” 推进为 “artifact scope pass，live runtime / human acceptance pending”。

## 下一步

下一步不能直接跑 full-chain 或模型对比。应选择少量 gold cases，把 artifact-backed packs 接入真实 runtime：

1. source route / parser / specialist / aggregate / writer payload 逐节点消费。
2. 区分 exemplar-backed artifact 与真实 live rows。
3. 对选中 case replay renderer / final verifier / Workbench projection。
4. 再做真实 Workbench dogfood 和人工 reviewer acceptance。
