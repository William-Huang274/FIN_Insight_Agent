# 077 P33-1.3 Capital Market Feedback Fixture

日期：2026-07-05

## 目标

关闭 P32 deferred contract `l3_capital_market_feedback_contract_v0_1`，用 no-paid deterministic fixture 证明二级市场 / 资本反馈信号可以进入 Research Lead / JudgmentCard / writer-ready material，但不能被提权为公司基本面、产品 KPI、实时资金流、单股 gamma/borrow exact 或投资建议。

## 本轮工作

- 新增 P33-1.3 fixture：
  - `src/sec_agent/p33_capital_market_feedback_fixture.py`
  - `scripts/engineering/run_p33_capital_market_feedback_fixture.py`
  - `tests/test_p33_capital_market_feedback_fixture.py`
- 生成 fixture artifact：
  - `data/manifests/p33_capital_market_feedback_fixture_v0_1.json`
  - `docs/internal/vnext_20260610/p33_capital_market_feedback_fixture_report.zh-CN.md`
- 更新 registry promotion：
  - `l3_capital_market_feedback_contract_v0_1` 从 `deferred_pending_l4_fixture` 晋升为 `active_registry_ready_runtime_alignment_only`。
  - `p32_registry_promotion_validation_v0_1.json` 当前为 `active_registry_ready_count=13`、`deferred_count=2`。
- 更新 source docs / ledgers：
  - `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
  - `docs/internal/vnext_20260610/r53_r60_p32_method_pattern_learning_gate.zh-CN.md`
  - `docs/project_os/current_context_pack.zh-CN.md`
  - `docs/project_os/p33_execution_plan_ledger.jsonl`
  - `docs/project_os/capability_status_ledger.jsonl`
  - `docs/worklog/00_internal_master_checklist.md`

## Root-Cause 修复

第一次 repo 级 fixture 失败不是因为二级市场数据不可用，而是 S8 信号边界生成不够硬：

- `market_proxy_not_fundamental_fact` 失败：`market_proxy_row_count=3487`，只有 `1809` rows 带足禁止提权边界。
- `exact_credit_and_statement_facts_separated` 失败：`exact_fact_row_count=4670`，`exact_fact_boundary_ok_count=0`。

根因在 `src/sec_agent/r53_r60_secondary_market_capital_feedback.py` 的 `insert_signal`：

- 当 source row 自带 `forbidden_claims` 时，S8 直接照抄 source-specific 禁止项；
- 没有再合并 pack role / authority class 的默认禁止外推边界；
- 真实输出中部分 holder / exact filing / exact statement rows 缺少 `investment_recommendation`、`realtime_flow`、`current_fund_flow_without_flow_source` 等 downstream 必需边界。

修复方式：

- `insert_signal` 现在把 source-specific forbidden claims 与 `default_forbidden_claims(pack_role, authority_class)` 合并去重。
- 新增 S8 回归断言：exact filing / exact financial statement rows 必须带 `investment_recommendation` 禁止项。

这属于上游 root-cause 修复，不是放松 P33 gate。

## 验收结果

P33-1.3 repo fixture 通过：

- 603 issuer packs。
- 14,706 capital-feedback signals。
- 634 typed gaps。
- 4,221 graph edges。
- 21 source roles 均有 authority / frequency / lag policy / commercial boundary / forbidden claims。
- 3,487 market / holder proxy rows 均不能提权为基本面、产品 KPI、实时资金流或投资建议。
- 1,678 lagged holder rows 均禁止写成实时买盘或 current buying pressure。
- 4,670 exact filing / exact financial statement rows 均与投资建议和市场隐含推断分离。
- writer-facing judgment material 共 42 rows，均带 evidence/gap refs、allowed/forbidden claims、cannot_promote_to 和 writer instruction。

## 验证命令

```powershell
python -m pytest tests/test_r53_r60_secondary_market_capital_feedback.py tests/test_p33_capital_market_feedback_fixture.py -q
python scripts/engineering/run_p33_capital_market_feedback_fixture.py
python scripts/engineering/validate_p32_registry_promotion.py --output data/manifests/p32_registry_promotion_validation_v0_1.json
python -m pytest tests/test_p32_registry_promotion_validation.py -q
```

结果：

- S8 + P33-1.3 local regression：`10 passed`
- P33-1.3 fixture：`status=pass`
- P32 registry promotion validator：`status=pass`
- P32 promotion tests：`4 passed`

## 边界

- 本轮没有调用 paid LLM。
- 本轮没有跑 full-chain。
- 本轮只证明 capital-market feedback contract 的 runtime alignment。
- 不能据此声称 paid memo quality、实时 OPRA/borrow/gamma、完整商业资金流或对外投资建议能力已就绪。

## 下一步

P33-1 剩余两个 deferred contracts：

1. `P33-1.4 workbench_artifact_review_surface`
2. `P33-1.5 research_to_quant_factor_handoff`

推荐下一步先做 Workbench surface fixture，因为 P33-2 runtime assimilation 和后续 gold workpaper 都需要用户能从最终判断 drill down 到 evidence、JudgmentCard、gap、gate、artifact 和 review action。
