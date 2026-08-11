# 032 S9 Research-to-Quant Lab L4 Scope Artifacts

日期：2026-06-29

## 目标

把 R53 的 Research-to-Quant Lab 从技术草案落成可审计 runtime slice：研究证据和 thesis driver 可以转成 `FactorHypothesis`，但必须经过 human approval、PIT dataset、leakage guard、deterministic validation、risk attribution 和 FactorCard 才能进入后续观察。S9 不做真实交易、不做外部投资建议，也不允许 LLM 绕过审批直接生成可交易规则。

## 本轮完成

- 新增 `src/sec_agent/r53_r60_research_to_quant_lab.py`：
  - `SignalObservation`；
  - `FactorHypothesis`；
  - `FeatureSpec` / `LabelSpec` / `UniverseSpec`；
  - `HumanApprovalDecision`；
  - `DatasetBuildPlan` / `PITDatasetRow`；
  - `LeakageGuardResult`；
  - `FactorAnalysisResult` / `BacktestResult`；
  - `RiskAttribution`；
  - `PaperTradingControl`；
  - `FactorCard`；
  - `ResearchExperienceRecord`；
  - S9 quality gates / summary / closeout report。
- 新增 `scripts/engineering/build_r53_r60_s9_research_to_quant_lab.py`，可从仓库根目录重建 S9。
- 新增 `tests/test_r53_r60_research_to_quant_lab.py`，验证 schema、traceability、approval、PIT、防泄漏、backtest、FactorCard、paper-trading boundary、experience record 和 repeat build。
- 更新 `docs/architecture/agent_graph_vnext/28_r53_research_to_quant_lab_technical_plan.zh-CN.md`，记录 S9 v0.1 runtime closeout。
- 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`，写入 S9 closeout。

## 生成物

- `configs/r53_r60/s9_research_to_quant_lab_schema_v0_1.json`
- `data/manifests/r53_r60_s9_research_to_quant_lab_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s9_research_to_quant_lab_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s9_research_to_quant_lab_l4_scope_pass.zh-CN.md`
- 私有 runtime DB：`data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`（不提交 Git）

## 真实构建结果

输入：

- S8 `Secondary Market / Capital Feedback Pack` SQL rows；
- `capital_feedback_signals_s8` bounded signal refs；
- 当前 S1 runtime task spine。

输出：

- `SignalObservation`：`3`
- `FactorHypothesis`：`3`
- approved factor：`2`
- blocked candidate：`1`
- `FeatureSpec`：`2`
- `LabelSpec`：`2`
- `UniverseSpec`：`2`
- human approvals：`7`
- `DatasetBuildPlan`：`3`
- `PITDatasetRow`：`24`
- `LeakageGuardResult`：`3`
- `FactorAnalysisResult`：`2`
- `BacktestResult`：`2`
- `RiskAttribution`：`2`
- `PaperTradingControl`：`3`
- `FactorCard`：`3`
- `ResearchExperienceRecord`：`3`
- quality gate：`12 pass / 0 fail`
- release decision：`S9_L4_scope_pass`
- next slice unlocked：`S10`

## 关键边界

- Approved dataset build 和 backtest 均要求 `HumanApprovalDecision`。
- 未审批 derivatives/gamma candidate 不生成 PIT rows，不进入 backtest，只生成 blocked FactorCard / ResearchExperienceRecord。
- PIT rows 必须带 `feature_publish_time`、`feature_available_time`、`tradable_after`、`label_window_start`、`source_refs`、provenance。
- Backtest 只是 deterministic smoke，证明对象链路和门控，不证明 alpha。
- FactorCard 全部带 `no_investment_advice`、failure scenarios、risk exposure、allowed next actions、forbidden actions。
- Paper trading 全部保持 `not_started_requires_separate_human_approval`，没有真实订单或模拟订单执行。

## 验证

- `python -m py_compile src\sec_agent\r53_r60_research_to_quant_lab.py scripts\engineering\build_r53_r60_s9_research_to_quant_lab.py`
- `python -m pytest tests/test_r53_r60_research_to_quant_lab.py -q`
- `python scripts\engineering\build_r53_r60_s9_research_to_quant_lab.py --root .`

## 后续

- S10：Enterprise Hardening / Release Candidate，把 S0-S9 串成 release candidate 级验证，包括 auth/RBAC、load/chaos/SLA、incident dashboard、release readiness report 和 online eval feedback loop。
- R53 后续：生产历史 security master、真实 feature store、Qlib / vectorbt / Alphalens / LEAN adapter、paper trading monitor、Workbench quant UI 和长期 FactorLifecycleLedger。
