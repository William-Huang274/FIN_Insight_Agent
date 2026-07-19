# 116 P35 AI Infra Supervisor Dogfood

日期：2026-07-09

## 背景

用户要求以 WorkBuddy 的 AI infra supply-chain case 为对照，不再停留在“我们的输出边界更严”这类解释，而是亲自作为 supervisor 使用 FIN_Insight_Agent 当前零件，最终产出一份合格研究报告，并记录过程中发现的系统不足、补源路径、方法反思和工程修复方向。

本轮不直接跑 paid LLM / true full-chain。Project OS full-chain preflight 仍阻止 broad full-chain，因为 `RC-P30-001` 和 `RC-P30-002` 仍 open。

## 工作内容

1. 读取 P34 handoff、Project OS ledgers、P34 route / adapter / live attempt / no-paid audit / fact-table projection 状态。
2. 审计 WorkBuddy 原 case 与 9 个补充 HTML cases，确认其强项是 decision surface + source hunting + visual report，弱项是 source-grade / numeric sanity / claim-level lineage。
3. 运行 P34 scoped no-paid chain 复核：
   - `run_p34_ai_semis_source_route_plan.py --strict`
   - `run_p34_ai_semis_adapter_fixtures.py --strict`
   - `run_p34_ai_semis_live_route_attempts.py --live-probe --timeout-seconds 20 --strict`
   - `run_p34_ai_semis_no_paid_quality_audit.py --strict`
   - `run_p34_scoped_memo_writer_payload_preflight.py --run-id p35_dogfood_recheck_p34_payload_20260709_r1 --strict`
   - `run_p34_fact_table_projection_and_goldcase_alignment.py`
4. 新增 P35 deterministic dogfood runner，把当前用户题面转成 5 segment x 12 dimension x 60 cell 的 `DecisionSurfaceFramework`，并对照 P34 runtime rows 与 WorkBuddy samples 产出 gap audit。
5. 作为 supervisor 额外补源 15 条官方 / 官方 PDF / 官方镜像 / 政府源，写入 source supplement ledger，供报告使用，但明确标记尚未 runtime-ingested。
6. 写出正式投研与 dogfood 结合报告。

## 新增产物

- `src/sec_agent/p35_ai_infra_supervisor_dogfood.py`
- `scripts/eval_multi_agent/run_p35_ai_infra_supervisor_dogfood.py`
- `tests/test_p35_ai_infra_supervisor_dogfood.py`
- `docs/project_os/p35_ai_infra_decision_surface_framework_v0_1.json`
- `docs/project_os/p35_ai_infra_current_system_gap_audit_v0_1.json`
- `docs/project_os/p35_ai_infra_source_supplement_ledger_v0_1.json`
- `docs/internal/vnext_20260610/p35_ai_infra_supervisor_dogfood_framework.zh-CN.md`
- `docs/internal/vnext_20260610/p35_ai_infra_supervisor_dogfood_report.zh-CN.md`

## 关键发现

P34 当前数据不是差到不能写。问题是当前题面的决策面没有成为 runtime contract。P34 可以用 21 条 accepted runtime rows、2 个 typed gaps、7 个 analyst fact-table blocks 通过自己的 bounded gate，但仍缺这次用户肉眼关心的 HBM、SMCI/HPE、CoWoS 细分、semicap peer panel 和 price-in cells。

WorkBuddy 之所以看起来更好，是因为它先做用户可见的 Decision Surface，再联网补源和渲染 HTML。FIN 的优势不应是更多边界声明，而应是同样强的 Decision Surface 加 claim-level source-grade、numeric sanity、typed gap 和 Workbench cell review。

本轮补源证明很多材料公开可得，不是源不存在。缺口在：source-hunter loop 没有由 missing decision cell 驱动，parser 没把官方 PDF / press table 提成 value/unit/period/product rows，writer 也不该在上游故事不完整时负责补完整故事。

2026-07-09 用户追问后补充三点：

1. 报告中说 parser / 抽取器不稳定，并不是单指 SEC 向量库或 SQL 数据库。SEC / XBRL / filing text / 13F 基础层仍有价值；本 case 的更大缺口在非 SEC 官方披露、非美 IR PDF、press table、HBM / CoWoS operating metrics、segment peer panel 和 source-grade numeric rows 没有稳定进入 runtime。
2. 本轮报告没有充分使用财务估值、投融资、基金持仓、13F、衍生指标和市场反馈数据。原因不是项目不适用，而是 P35 runner 没有把 S8 capital-market pack、valuation layer、ownership layer 和 derivatives / market-snapshot layer 接到 60 个 decision cells。
3. 图谱、skill 和模型编排也不是没问题。图谱需要从 relationship graph 升级为 value-capture graph；skill 需要从提示约束升级为 cell-level runtime contract；编排需要由 supervisor 盯 missing cells，触发 source hunter / parser / graph / specialist / capital-market pack，而不是让各节点各自交 evidence summary。

## Dogfood 执行方式边界

本轮是 supervisor-level dogfood，不是完整线上 multi-agent / DeepSeek 节点复跑。

实际执行：

- 读取 Project OS、P34 handoff、P34 route / adapter / live attempt / no-paid audit / fact-table projection artifacts。
- 审计 WorkBuddy 本地 HTML、task JSON、trace。
- 运行 P34 scoped no-paid runner 复核 source route、adapter、live attempts、quality audit、writer payload preflight 和 fact-table projection。
- 新增 P35 deterministic runner，生成 decision surface framework 与 gap audit。
- 由 Codex supervisor 手工 official-first 补源 15 条，并写出 source supplement ledger 和研究报告。

未执行：

- 未通过实际 MCP 知识库检索、重排、SQL/vector/RAG 工具链按 cell 自动取数。
- 未触发 Research Lead、source hunter、parallel specialists、aggregate、writer 的完整线上编排。
- 未让各 subagent 真实加载各自 prompt / skill / graph pack 后产出独立判断。
- 未运行 paid DeepSeek writer、true full-chain、model comparison。
- 未把补源 rows 回灌成 accepted runtime rows，也未证明 graph/specialist/writer 消费了这些 rows。

结论：P35 足以定位 runtime 缺口，但不能记为完整 multi-agent dogfood closeout。下一步若要验证 agent 体验，必须跑真实节点链路，并记录每个节点 consumed inputs、produced cells、missing cells、补源动作和 reviewer verdict。

## 验证记录

- `python scripts/eval_multi_agent/run_p35_ai_infra_supervisor_dogfood.py --strict`
  - `status=current_system_gap_audit_completed_no_paid_llm`
  - `segment_count=5`
  - `dimension_count=12`
  - `decision_surface_cell_count=60`
  - `missing_cell_count=25`
  - `workbuddy_samples_read=9`
- `python -m pytest -q tests/test_p35_ai_infra_supervisor_dogfood.py`
  - `3 passed`

后续完整验证见本轮最终回执。

## 未运行

- paid LLM
- true full-chain
- model comparison
- case expansion
- release eval

## 下一步

1. 将 `p35_ai_infra_source_supplement_ledger_v0_1.json` 转成真实 source-route attempts、parser fixtures 和 normalized runtime rows。
2. 实现 `DecisionSurfaceContract`，并让 Research Lead、source routes、specialists、MemoLogicPlan、writer payload、verifier 都围绕 cell completeness 工作。
3. 实现 `SourceHunterLoop`，missing/weak cells 先 official-first 补源，补不到才写 attempt-backed typed gap。
4. 将 S8 capital-market pack、13F / ownership、valuation、market reaction 和衍生指标接入每个 chain 的 price-in cells。
5. 把 relationship graph 升级为 value-capture graph，并把 bottleneck rent、pass-through、capex lag、export risk、margin dilution 写成边属性。
6. 把 report renderer 升级为先输出 decision surface / risk matrix / evidence ranking / what-would-change，边界声明附着在 cell 下。
