# 322 R3/R5/R10/R12 Runtime Release Gate Activation

日期：2026-06-14

## Prompt

用户要求把以下六项做完，并且第四点先跑 1-2 个 full-chain 用例：

1. R3 Milvus 从“已建库”推进到 runtime 正式可用。
2. R5 GPU BGE queue / scheduler 做本地或云端高并发验证。
3. R10 cloud/load 级别后端压测。
4. R12 full-chain regression / online eval / release gate 先跑 1-2 个激活 case。
5. Eval 真实运行闭环由 R12 填满 failure/gold/online eval/latency-cost trend。
6. 前端 / Workbench 用 R12 真实 run 验证产品级 trace。

## Decision

- 不把 Milvus 作为 exact-value authority；只接入 `semantic_recall_supplement_not_exact_value_authority`。
- R12 只执行 2 个 diagnostic full-chain 激活 case，不提前跑 12-case successor 或 10-20 case broader gate。
- 对 R12 暴露的问题做 root-cause 修复：healthcare 产品收入事实已被选中但被误标为 `fundamentals`，因此修 ClaimCard 维度绑定，而不是放宽 eval gate。
- Workbench trace 的问题通过升级 artifact inspector 解决，让现有 inspect 面板识别 vNext multi-case eval root，而不是再做一个一次性查看脚本。

## Work Completed

- 新增 `configs/runtime/milvus_runtime_603_local_v0_1.json`，把 accepted 603-company local Milvus Lite DB、collection、embedding model、vector count 和 claim boundary 写入 runtime config。
- `RuntimePathRegistry` 支持 `FINSIGHT_MILVUS_RUNTIME_CONFIG`，并把 Milvus db / collection / embedding model / vector kind / config path 暴露到 baseline registry。
- `sec_milvus_semantic_search` 从 stub 升级为真实 Milvus Lite + bge-m3 query route，输出 `source_family=milvus_semantic`、`exact_value_authority=false`、collection stats 和 source gaps。
- R3 readiness gate 现在会真实调用 Milvus route；`run_r0_r11_readiness_gate.py --include-cloud-gates` 在本地 accepted DB 下 `cloud_gaps=[]`。
- 新增 `scripts/runtime_bridge/run_r5_gpu_bge_scheduler_smoke.py`，验证 CUDA BGE slot、CPU spillover、token-budget tier routing、模型加载和缓存命中 proxy。
- `job_runner.py` 不再强制 Workbench eval 用 CPU BGE；默认改为 `auto`，允许 CLI / env 指定 `cuda`。
- 新增 `scripts/runtime_bridge/run_r10_backend_load_sla_smoke.py`，覆盖 Java gateway、file queue、Python worker pool、SSE、resume、run_audit 和 object store 压力。
- 修复 `task_worker._pop_file_task` 并发 file queue race；多个 local worker 同时 glob pending 文件时不会因后移动者 FileNotFound 而失败。
- 修复 R10 resume 判定：progress=0 是合法重置状态，不能被 `or -1` 误判。
- 修复 `d_series_fact_selection`：`financial_metric:revenue` 如果带非总表/非调整项 `product_or_segment`，生成 deterministic ClaimCard 时归入 `product_and_production`；`Other revenues` 等仍归 `fundamentals`。
- 升级 `task_worker` 的 Eval Store 写入：future Workbench eval 会记录 case latency/cost/token metrics，并把 pass case 写成 gold candidate。
- 新增 `scripts/runtime_bridge/run_r12_eval_runtime_loop_gate.py`，从真实 R12 summary 回填和验证 Eval Store 的 case result、metric trend、failure/quality queue、gold candidate 和 dashboard snapshot。
- 升级 `inspect_run_artifacts`：识别 `real_chain_eval_summary.json` 的 vNext multi-case eval root，并索引每个 case 的 score、memo、ClaimCards、typed gaps、gate matrix、run audit、context memory、checkpoints、pre-memo fact selection 和 rendered answer。
- 更新 `13_09_11_remaining_full_completion_plan.zh-CN.md` 和 `00_internal_master_checklist.md`，把 R3/R5/R10/R12 当前状态从 pending/cloud gap 改为本轮真实结果。

## Verification

- `python -m py_compile src/sec_agent/mcp_tool_registry.py src/sec_agent/runtime_bridge/paths.py src/sec_agent/runtime_bridge/baseline.py src/sec_agent/runtime_readiness.py src/sec_agent/workbench/job_runner.py scripts/runtime_bridge/run_r5_gpu_bge_scheduler_smoke.py scripts/runtime_bridge/run_r10_backend_load_sla_smoke.py`
- `python -m pytest tests/test_d_series_fact_selection.py tests/test_multi_agent_real_llm_chain_eval.py -q`：`32 passed`
- `python -m pytest tests/test_workbench_artifacts.py tests/test_workbench_backend.py::test_workbench_backend_lists_and_starts_controlled_eval_runner tests/test_workbench_backend.py::test_workbench_backend_starts_diagnostic_probe_eval_runner_without_strict -q`：`8 passed`
- `python scripts/runtime_bridge/run_r10_backend_load_sla_smoke.py --tasks 8 --workers 3 --audit-rows 24 --output-dir reports/quality/r10_backend_load_sla_smoke`：`pass`，8/8 task success，SSE heartbeat present，resume pass，p95 约 `2062ms`。
- `python scripts/runtime_bridge/smoke_java_python_bridge.py --task-mode workbench_eval --eval-id agent_graph_vnext_diagnostic_probe --limit 2 --run-id r12_activation_diagnostic_probe_milvus_bound_20260614_r2 --bge-device cuda --worker-run-timeout-s 3600`：`SUCCESS`，Workbench summary `2/2 pass`。
- `python scripts/runtime_bridge/run_r12_eval_runtime_loop_gate.py --workbench-summary reports/quality/workbench_eval/r12_activation_diagnostic_probe_milvus_bound_20260614_r2_agent_graph_vnext_diagnostic_probe.json --output-path reports/quality/r12_eval_runtime_loop_gate/r12_eval_runtime_loop_gate_report.json`：`pass`，Eval Store counts include `eval_gold_promotion=2`、`eval_failure_event=18`、`eval_metric_result=70`。
- Workbench artifact inspector over `eval/sec_cases/outputs/multi_agent_vnext_diagnostic_probe_eval/r12_activation_diagnostic_probe_milvus_bound_20260614_r2`：`pass`，2 cases, artifact_count `23`。
- `python scripts/runtime_bridge/run_r0_r11_readiness_gate.py --include-cloud-gates --output-dir reports/quality/r0_r11_readiness_local_milvus_bound`：`pass`，gate_count `13`，cloud_gap_count `0`，Milvus row_count `662908`，query_row_count `5`。
- `python scripts/runtime_bridge/run_r5_gpu_bge_scheduler_smoke.py --cuda-slots 3 --task-count 6 --device auto --run-model-smoke --require-cuda --output-dir reports/quality/r5_gpu_bge_scheduler_smoke`：`pass`，CUDA device `NVIDIA GeForce RTX 4060 Laptop GPU`，bge-m3 embedding_dim `1024`，CUDA memory reserved about `2188MB`。

## Results

- R3 已从“已建库”推进到 runtime path registry + real retrieval route gate 可用。
- R5 已有本地 CUDA queue smoke 和 CPU spillover 审计，不再一开始全部 fallback CPU。
- R10 本地 load smoke 已覆盖 gateway、queue、worker callback、SSE、resume、SQL audit 和 ObjectStore 压力。
- R12 两个激活 case 已通过，且首轮暴露的 healthcare 产品收入 deterministic claim 维度绑定问题已修复。
- Eval Store 已有真实 R12 case result、latency/cost metrics、failure/quality queue、gold candidates 和 dashboard snapshot。
- Workbench artifact inspector 能识别 R12 vNext multi-case eval root，用户可从 eval root 追到每个 case 的 memo、evidence/ClaimCards、gap、gate、context、run_audit 和 final rendered answer。

## Follow-up

- 仍未跑 12-case successor、10-20 case broader gate 和最终 release readiness report。
- R12 output quality audit 仍提示高 token 成本、Memo Writer / Verifier 成本高、claim/token 效率低，以及 product specialist visible rows 偏少；这些已进入 Eval Store quality queue，下一轮应优化 role-specific selector、Memo Writer 输入压缩和 verifier 成本。
- R5/R10 仍只是本地高并发 smoke；后续需要云端/生产形态 SLA gate 覆盖真实 worker pool、provider latency、token/cost、DB/ObjectStore 写入压力和失败恢复。
- Milvus 只能作为 semantic recall supplement；任何 exact financial value 仍必须来自 ledger / SEC structured source / approved fact selection。

## Safety Notes

- 未把 DeepSeek key 或云端密码写入文件。
- 生成的 `reports/quality/*`、`eval/sec_cases/outputs/*` 和 `data/workbench_private/*` 是运行产物，默认不作为 Git 跟踪候选。
