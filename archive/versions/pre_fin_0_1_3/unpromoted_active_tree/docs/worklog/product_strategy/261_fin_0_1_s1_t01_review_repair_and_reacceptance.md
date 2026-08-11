# 261 FIN 0.1 S1-T01 独立复核修订与二次接受

日期：2026-07-19
状态：`accepted_after_independent_review_repair`

## 问题与首轮复核

用户要求修复 S1-T01 独立复核指出的主要问题并再次评审。首轮 reviewer disposition 为 `changes_requested_before_acceptance`，原因不是当前代码回归失败，而是 v1.0 adapter contract 对以下内容冻结不足：

1. HTTP 202 创建 pending WorkUnit 后，claim、Attempt、dispatch、profile execution 和 terminal commit 的真实时序；
2. `ResearchRunVersion` 与 WorkUnit、Attempt、`EventEnvelope.task_run_id`、Artifact `producer_attempt_id/input_refs` 的精确基数和 lineage；
3. `app.py` composition root 及 existing scheduler/facade/object store 的注入；
4. 当前 ActivityTrace 写入口与 Workbench Next 当前 read-only、T05 目标写入口的过渡边界；
5. D06 `EvidenceService` owner 未进入 target/disposition，以及机器 `unique_owner` 同时编码多个 authority。

## 修订决策

- v1.0 manifest 保留为 supersession pointer，接受合同升级到 `configs/releases/fin_ia_0_1_s1_adapter_map_v1_1.json`；
- API request 只 admission/enqueue 并返回 HTTP 202；profile 不在 request thread 执行；
- 复用 existing `DurableSchedulerService.claim_next -> RuntimeFacade.claim_next_scheduled_attempt` 创建唯一 running Attempt；
- `Fin01ResearchRuntime.execute_claimed_attempt` 只执行 exact claimed Attempt，bounded in-process S1 dispatch hook 属于同一 Runtime/composition，不新增 worker/scheduler family；
- 一个 Attempt 对一个 ResearchRun identity；Event 复用 `task_run_id=research_run_id`；Artifact 用 `producer_attempt_id`、含 Run version 的 `input_refs` 和 Attempt `output_refs` 形成 exact lineage；
- Agent 失败后的 deterministic fallback 使用 existing fork lineage，新建 child WorkUnit、Attempt、ResearchRun 和 profile version；
- `app.py` 明确为唯一 composition root；
- 当前 ActivityTrace 保留过渡写入，Workbench Next 当前只读，T05 才把目标 run action 接到同一 ExecutionApiClient command；
- D06 增加 `evidence_service.py` refactor/target；所有决策只保留一个 machine `unique_owner`，逐对象 owner 写入 `ownership_by_object`；
- object store 先写 immutable object、SQLite 后提交 envelope/event/head；不虚构 distributed transaction。

## 变更文件

- `docs/architecture/repository/FIN_0_1_S1_DECISION_TO_CODE_ADAPTER_MAP_20260719.zh-CN.md`
- `configs/releases/fin_ia_0_1_s1_adapter_map_v1_0.json`
- `configs/releases/fin_ia_0_1_s1_adapter_map_v1_1.json`
- `configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json`
- `docs/worklog/product_strategy/260_fin_0_1_s1_t01_decision_to_code_adapter_freeze.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/capability_status_ledger.jsonl`
- `docs/project_os/root_cause_issue_ledger.jsonl`

## 二次复核门

必须全部通过：

- v1.1 JSON、backlog 和两份 JSONL 可解析；
- D02-D14 exact 13/13，每项一个非复合 `unique_owner` 和非空 `ownership_by_object`；
- D06 `EvidenceService` 同时进入 disposition 和 target；
- D12 target 包含 `app.py`、ActivityTrace、Workbench Next、existing scheduler/facade/store/object store；
- 202 enqueue-only、claim-before-execute、Attempt-to-Run、Event/Artifact lineage 和 fallback child contract 都可由机器字段断言；
- stable source digest 9/9 不变；
- 当前 execution/runtime/Workbench 合同回归通过；
- `git diff --check` 与敏感信息候选扫描通过。

## 边界

本轮仍只有 docs/manifest/governance 变化：`runtime_implementation_changes=0`、`model_calls=0`、`provider_calls=0`、`network_calls=0`、`commercial_data_calls=0`、`business_case_mutations=0`。二次接受只关闭 T01 review dependency，不实现 T02/T03、不关闭 RC-P38-042、不产生 Agent 质量、RG1/RG3/RG4、release 或 production 证据。

## 验证与二次复核结果

- v1.0 pointer、v1.1 manifest、program backlog 均可解析；两份 Project OS JSONL 全量逐行解析通过；
- D02-D14 exact 13/13，machine unique owner 13/13，逐对象 owner 13/13；
- D06 EvidenceService disposition/target 闭环通过；
- D12 的 `app.py`、execution API、ActivityTrace、Workbench Next、existing scheduler/facade/store/object store target 闭环通过；
- HTTP 202 enqueue-only、FastAPI BackgroundTask dispatch、claim-before-execute、crash truth、Attempt/Run/Event/Artifact lineage、existing recovery fork fallback 机器断言通过；
- backlog stable source SHA-256 9/9 一致；
- 当前 execution/runtime/Workbench 基线回归：`34 passed in 21.97s`；这些测试只证明当前基线未损坏，不证明尚未实现的 T02/T03；
- v1.1 manifest SHA-256：`adff280e44d8cc2c0a9fc349a1a6b791752aae95ec521594d067d83f1673ab23`；
- `git diff --check` 通过；候选文件与两份 ledger 新增末行的敏感信息模式扫描通过；postflight 未出现 `apps/`、`src/`、`scripts/` 或 `tests/` runtime source 变更。

二次 reviewer disposition：`pass_after_independent_review_repair_no_implementation_claim`。T01 dependency 关闭；T02/T03 仍为 pending、未执行。
