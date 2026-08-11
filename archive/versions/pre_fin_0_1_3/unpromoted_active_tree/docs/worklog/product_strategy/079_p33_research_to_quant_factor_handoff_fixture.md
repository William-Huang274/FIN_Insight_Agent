# 079 P33-1.5 Research-to-Quant Factor Handoff Fixture

日期：2026-07-05

## 目标

关闭 P32 deferred contract `l3_research_to_quant_factor_handoff_contract_v0_1`，用 no-paid deterministic fixture 证明研究判断只能进入内部量化验证对象，而不能绕过 PIT、leakage guard、human approval 或 no-advice 边界。

## 本轮工作

- 修复 S9 Research-to-Quant handoff payload contract：
  - `src/sec_agent/r53_r60_research_to_quant_lab.py`
  - 新增一等 SQL runtime table：`research_judgment_cards_s9`，记录 `judgment_card_id`、`thesis_driver_id`、source refs、authority boundary、counter-view、failure-view、forbidden claims。
  - factor / signal payload 现在包含 `judgment_card_ids`、`signal_definition`、`candidate_feature_refs`、`point_in_time_data_manifest`、`human_approval_policy`。
  - `judgment_card_ids` 不再使用 `thesis_driver_id` 代替，而是指向可 SQL 解析、可追责的 `research_judgment_cards_s9` rows。
  - approved dataset plan 现在包含 `backtest_plan_id` 和 no-live/no-advice backtest policy。
  - blocked dataset plan 现在包含 `blocked_before_backtest_plan=true`。
- 新增 P33-1.5 fixture：
  - `src/sec_agent/p33_research_to_quant_factor_handoff_fixture.py`
  - `scripts/engineering/run_p33_research_to_quant_factor_handoff_fixture.py`
  - `tests/test_p33_research_to_quant_factor_handoff_fixture.py`
- 生成 fixture artifact：
  - `data/manifests/p33_research_to_quant_factor_handoff_fixture_v0_1.json`
  - `docs/internal/vnext_20260610/p33_research_to_quant_factor_handoff_fixture_report.zh-CN.md`
- 更新 registry / source docs / ledgers：
  - `docs/project_os/p32_active_registry_promotion_ledger.jsonl`
  - `docs/project_os/p33_execution_plan_ledger.jsonl`
  - `docs/project_os/capability_status_ledger.jsonl`
  - `docs/project_os/current_context_pack.zh-CN.md`
  - `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
  - `docs/internal/vnext_20260610/r53_r60_p32_method_pattern_learning_gate.zh-CN.md`
  - `docs/worklog/00_internal_master_checklist.md`

## Root-Cause 修复

P33-1.5 发现的关键问题不是 S9 没有量化验证表，而是 S9 和 P32 L3 contract 之间的字段映射不够显式：

- L3 input contract 要求 `judgment_card_ids`、PIT manifest 和 human approval policy。
- L3 output contract 要求 approved candidate 有 `backtest_plan_id`、leakage result、approval state 和 ResearchExperienceRecord。
- 旧 S9 主要依赖 `thesis_driver_id`、dataset plan 和 backtest result 隐含表达这些信息，不利于后续 Research Lead / QuantResearchAssistant / Workbench 直接消费。

修复方式是在 S9 materialization 阶段补齐 payload contract，而不是在 P33 fixture 里临时拼字段。

2026-07-05 追加 root-cause 修复：

- subagent 复核指出 `judgment_card_ids` 如果只是 `thesis_driver_id` 替代，不能满足 P32 对 JudgmentCard -> FactorHypothesis 的可审计输入要求。
- 已将 `research_judgment_cards_s9` 作为 S9 一等对象落库，P33 fixture 新增 `judgment_card_audit` 和 gate `p33_1_5_judgment_cards_are_first_class_source_backed`。
- 验收要求：每个 handoff payload 的 `judgment_card_ids` 都必须解析到 SQL row，且 row 必须有 source refs、authority boundary、counter-view、failure-view、no-advice / no-live-trading forbidden claims；payload id 不能等于 `thesis_driver_id`。

## 验收结果

P33-1.5 repo fixture 通过：

- S9 Research-to-Quant 保持 `S9_L4_scope_pass`。
- 3 个 candidates 都带完整 L3 input mapping。
- 3 个 `judgment_card_ids` 均解析到 `research_judgment_cards_s9`，`direct_thesis_id_substitute_count=0`。
- 2 个 approved candidates 都带完整 L3 output mapping，包括 `backtest_plan_id`。
- 1 个 unapproved derivatives candidate 在缺 source / approval 时 fail closed：无 PIT rows、无 backtest plan/result、无 paper/live trading。
- PIT rows 有 publish / available / asof / tradable / label timestamps，backtests 只能在 passed leakage guard 后出现。
- FactorCard 和 ResearchExperienceRecord 写入，且所有结果保留 no-investment-advice boundary。

Registry 最新状态：

- `active_registry_ready_count=15`
- `deferred_count=0`
- P33-1 closeout 完成，下一步进入 P33-2 runtime assimilation。

## 验证命令

```powershell
python -m pytest tests/test_p33_research_to_quant_factor_handoff_fixture.py tests/test_r53_r60_research_to_quant_lab.py -q
python -m py_compile src/sec_agent/r53_r60_research_to_quant_lab.py src/sec_agent/p33_research_to_quant_factor_handoff_fixture.py scripts/engineering/run_p33_research_to_quant_factor_handoff_fixture.py
python scripts/engineering/run_p33_research_to_quant_factor_handoff_fixture.py --root .
python scripts/engineering/validate_p32_registry_promotion.py --output data/manifests/p32_registry_promotion_validation_v0_1.json
python -m pytest tests/test_p32_registry_promotion_validation.py tests/test_p33_research_to_quant_factor_handoff_fixture.py -q
```

结果：

- P33-1.5 + S9 tests：`11 passed`
- P33-1.5 fixture script：`status=pass`
- P32 registry promotion validator：`status=pass`，`15/0`
- P32 promotion + P33-1.5 tests：`9 passed`
- P33-1 横向 deterministic suite：`33 passed`

## 边界

- 本轮没有调用 paid LLM。
- 本轮没有跑 full-chain。
- 本轮只证明 Research-to-Quant factor handoff contract 的 runtime alignment。
- 不证明真实可交易 alpha、生产 PIT security master、交易成本/容量/滑点建模、paper trading adoption 或任何对外投资建议。

## 下一步

进入 `P33-2 Runtime Assimilation`：

1. 汇总 15 个 active registry contracts 为 Research Lead 可读 runtime registry。
2. 让 Research Lead / ContextEngine / ProductIntelligenceGraph / Fundamental / Capital / CustomerDeployment / JudgmentCard / MemoLogicPlan 真正按合同协作。
3. 用 deterministic fixture 证明 writer 输入是 writer-ready judgment material，而不是 raw evidence dump。
