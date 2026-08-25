# S3 工作记录 173：DELL-RSQ-00A—01C 基线、质量协议与 14／9／4 crosswalk 物化

日期：2026-08-25

状态：`deterministic_implementation_materialized / independent_review_pending / G1_false`

## 1. Owner 授权与本片范围

Owner 在 program-level 执行计划完成后明确授权进入实现。本片严格按依赖顺序执行：

1. `DELL-RSQ-00A` baseline manifest；
2. `DELL-RSQ-00B` report/model quality evaluation protocol；
3. `DELL-RSQ-00C` 逐节点调用权限模板；
4. `DELL-RSQ-01A/01B/01C` provider-neutral crosswalk、零调用 materializer 和 audit/model/reader 三投影。

本片没有执行 EP2 Evidence admission、EP3 外源梯子、embedding、reranker、动态 Agent 或 Writer。

## 2. 实现中发现并纠正的合同问题

原计划在一组枚举中同时列出 `technical_chain_closed`、`candidate_admission_pending`、
`source_route_pending`、`narrowed`、`S2_numeric_or_bridge_gap`、`S3_method_parameter` 和
`not_selected_by_unit`。这些不是互斥的同一状态：技术链是否打通、动态单元是否选择、研究缺口处置、
下一合法动作和阶段 owner 是正交维度。压成单枚举会把“Pack→Runtime 技术链已闭合”误读成“商业研究
缺口已闭合”。

实现因此使用多轴合同：

- `technical_chain_state`；
- `unit_selection_state`；
- `research_disposition`；
- `next_legal_action`；
- `source_or_method_type` 与 `stage_owner`。

所有计划要求的受控值仍被保留，但任何 14→9→4 数量变化都不能自动改变 `closed` 或
`proved_information_boundary`。

## 3. 基线与质量治理产物

新增：

- `configs/research/evals/fin_ia_0_1_3_dell_source_report_quality_program_baseline_manifest_v1_0.json`；
- `configs/research/evals/fin_ia_0_1_3_dell_source_report_quality_evaluation_protocol_v1_0.json`；
- `configs/research/evals/fin_ia_0_1_3_dell_source_report_quality_execution_authority_template_v1_0.json`。

baseline 逐文件绑定 R17 private/public、R4 current Pack、R38 private、ProductReadiness public/private、
S2 bridge public/private、质量 Rubric 和 program 文档；同时验证 file SHA-256、JSON self digest、case、
as-of、schema、status，以及 tracked Git blob/commit 或明确的 private-workbench 身份。

冻结基线保持：

- Pack `55 Evidence / 14 gaps / 0 closed / 3 narrowed`；
- dynamic `9` gaps；Writer `4 groups / 10 refs`；S2 `4` bridge gaps；
- ProductReadiness `8` requests，其中 `4 blocked_by_evidence_admission`；
- review packet `18` items，其中 `16 human-required`；
- R17 `P0/P1/P2/P3=0/1/2/1`，engineering `PASS_BOUNDED`，report
  `OPEN_NOT_ASSESSABLE`，qualified human `FALSE_NOT_GRANTED`，formal 8D 为 null。

质量协议冻结 L1/L2 前置、P0–P3、八维 `24/32` 及逐维阈值、claim/source/crosswalk/numeric/counter/
WWC/citation/render packet、三份独立 verdict 和 reason-ref schema。模型自评分、LLM-as-judge formal
签权和作者自评均为 false。

权限模板覆盖 external source、0.6B/4B embedding、baseline/challenger reranker、dynamic Agent、Writer
和 shadow evaluator 八个节点。每个节点都必须另行填写 task-specific `TokenBudgetBasis`、attempt、
input digests、provider/network 上限、capture-first、retry/fallback、exclusive-create 和 failure
disposition；当前全部为 `not_authorized`。

## 4. Crosswalk 编译结果

实现文件：

- `src/sec_agent/research/report_gap_crosswalk.py`；
- `scripts/research/materialize_dell_report_gap_crosswalk.py`；
- `configs/research/evals/fin_ia_0_1_3_dell_report_gap_crosswalk_program_v1_0.json`；
- `tests/test_dell_report_gap_crosswalk.py`。

工程合同提交：`43e3a555421da01fe0b02da49bbd0f957e66a2d2`。

干净工作树上的 R1 零调用物化：

- public：`configs/research/evals/fin_ia_0_1_3_dell_report_gap_crosswalk_result_v1_0.json`；
- private：`data/workbench_private/fin_0_1_3_report_gap_crosswalk/dell-r1/full_result.json`；
- content digest：`10fefe2f980dbdc2194e1c4ef2f058bc7cc7b48b5d73fa4b8453366c8c754d17`；
- public result digest：`09686edf180371f8676abb85b8cda90991bcab144d2e62a06923a3229a2b520c`；
- private full result digest：`bbcfe1946aa85123376161fcd3ada04d59a556c6755ea15c5c8d01262214d4b9`；
- private file SHA-256：`9bd741864c461ce16dc7defc511a90bfba77bf4217d6c9938d12c45d2b66daf8`。

精确计数：

- 14 Pack gaps 全部且只出现一次；
- R38 9 refs 通过唯一 facet 映射到 14 的子集；
- R17 4 groups／10 refs 全部映射，其中 working-capital ref 独立补到 Pack 对应项；
- 5 个 Pack gap 未被 R38 选择；
- 4 个 Pack gap 未被 Writer 引用：price-in、scenario、valuation 和 supplier read-through；
- S2 四个 bridge gaps 中 ASP、units、PVM 映射 Pack，product-profit attribution 保持独立；
- disposition 为 `1 admission-pending / 3 narrowed / 4 S2 numeric-or-bridge / 2 S3 method /
  4 source-route-pending`；closed 与 proved-information-boundary 均为 0。

audit/model/reader 三投影共享同一 content digest。模型视图没有 private path、digest 或期望关闭标签；
读者视图不暴露 EV/GAP/NUM 内部 ID，按业务名称解释 current disposition、意义、改变它所需的证据与
报告位置。PVM 与 product profit 的 `null_until_authorized_inputs` 没有被隐藏。reader citation appendix
仍为 pending，因此 R17 的 P1 没有因本 crosswalk 自动关闭。

## 5. 验证

- 新 crosswalk／governance tests：`17 passed`；
- 与 S2 product bridge、R17 successor 相邻合同合计：`28 passed`；
- `compileall`：通过；
- 四份新增 program/governance JSON：可解析；
- `git diff --check`：通过；
- staged secret-pattern scan：0 finding。

mutation 覆盖 byte drift、missing private、模型自评分、缺 citation packet、14→4 假闭合、duplicate
facet、unknown Writer ref、cross ticker、S2 bridge 冒充 Pack、closed 无 receipt、private leakage、
reader 隐藏 PVM null、dirty worktree 和 output collision。

## 6. 权限与下一门

本片实际调用为 model/provider/network/embedding/reranker/candidate promotion/Evidence promotion/
gap closure 全 0。它只证明 deterministic contract 和 R1 materialization，不关闭 R17 P1、WWC P2、
任何 source gap，也不授予 S1/S2/S3、product、publication 或 release。

按 `DELL-RSQ-01C`，fresh author-separated reviewer 必须只读解释 immutable 14/9/4、检查三投影与
mutation gate。该 verdict 尚未签发，所以 `independent_review_pass=false`、`G1=false`。复核通过后，
下一实现片是并行准备 `DELL-RSQ-02A` 的 4-request/16-item admission packet 与 `03A` residual route
manifest；qualified-human 02B 决定仍不能由 Codex 或模型代签。
