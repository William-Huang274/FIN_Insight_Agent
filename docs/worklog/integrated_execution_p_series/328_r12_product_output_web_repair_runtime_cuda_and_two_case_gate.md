# 328 R12 Product Output / Web Repair / CUDA Runtime Two-Case Gate

## Prompt

用户重启机器并清理 C 盘后，要求继续检查 CUDA 不可用是否与本机空间/pagefile 有关，并继续完成前一轮五项修复：重定义产品输出、补真实 targeted web repair、改 Research Lead 职责、改写作 gate、改 eval 体系；先 smoke，再跑 1-2 个 full-chain case，不允许把失败兜底藏掉。

## Diagnosis

- 本机 `nvidia-smi` 显示 RTX 4060 Laptop GPU 8GB 可用，显存空闲约 7GB。
- C 盘清理后，BGE CUDA 单模型 smoke 可正常加载，约 4.35s，CUDA allocated 约 2.1GB。
- r16 失败根因不是模型 API，而是 Windows pagefile / C 盘空间不足导致 BGE subprocess 加载报 `os error 1455`。
- 本机并发 BGE 不能粗暴全 fallback CPU；应保留 CUDA，但通过 queue 控制并发：
  - `auto/cuda + in_process` 默认串行。
  - `auto/cuda + subprocess` 默认 2 worker queue。
  - 其他 CPU/subprocess/cloud profile 保留更高 fanout。

## Work Completed

- `src/sec_agent/multi_agent_runtime.py`
  - 为 `sec_search_filings` 加 resource retry：CUDA OOM / BGE subprocess access violation / pagefile 类失败先降 batch，再 CPU spillover。
  - 失败 route 不再写入 grouped search cache，避免错误结果污染后续 route。
- `src/sec_agent/workbench/job_runner.py`
  - Workbench R12 eval 默认显式传 `--context-runner subprocess`，避免 in-process native crash。
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - resource-aware fanout policy 更新：本机 `auto/cuda + subprocess` 默认 2 worker。
  - 增加 surface / investment quality gate 对 gap 预算、内部模板、开头信息密度的检查。
- `src/sec_agent/memo_llm.py`
  - Memo supported-claim selector 改为非 gap claim 优先，official product context / company financial fact 优先，source_gap 只在没有正向 claim 时进入主输入。
  - deterministic salvage 跳过 gap-only claim；relationship graph claim 不再把外延 ticker 直接写成核心主线。
- `src/sec_agent/langgraph_orchestrator.py`
  - renderer 清理 `声明卡`、`紧凑验证判断计划`、`官方来源修复`、`产品表面`、`management commentary` 等用户不可读或内部治理词。
  - 新改写后的通用 source boundary 继续按 generic boundary 隐藏。
- Tests
  - 新增/更新 memo selector、relationship graph 展示、renderer internal prose 清洗、resource retry、Workbench subprocess 参数等测试。

## Full-Chain Runs

- `r12_product_output_web_repair_cloud_single_20260615_r17`
  - Scope: cloud capex single case.
  - Result: pass.
  - Summary: `reports/quality/workbench_eval/r12_product_output_web_repair_cloud_single_20260615_r17_agent_graph_vnext_r12_successor_12.json`
- `r12_product_output_web_repair_two_case_20260615_r18`
  - Scope: semicap + cloud capex two case.
  - Result: fail, semicap failed `gap_budget_ok`.
  - Root cause: product/source gap ClaimCards were treated as supported main inputs even after ASML official issuer repair succeeded.
- `r12_semicap_official_product_selection_20260615_r19`
  - Scope: semicap single case, direct CLI without run audit DB.
  - Result: content gates pass, run-audit gate fail because `--run-audit-db-path` was omitted.
- `r12_semicap_official_product_selection_20260615_r20`
  - Scope: semicap single case with Workbench-equivalent run audit DB.
  - Result: fail, only `internal_gate_prose_absent=false`.
  - Root cause: rendered memo leaked `声明卡` / internal boundary prose.
- `r12_semicap_official_product_selection_20260615_r21`
  - Scope: semicap single case with run audit DB.
  - Result: pass.
  - Key metrics: `investment_quality.status=pass`, `surface_readability.status=pass`, run audit required tables non-empty, gap sentence ratio `0.102`.
  - Output: `eval/sec_cases/outputs/multi_agent_vnext_r12_successor_12_eval/r12_semicap_official_product_selection_20260615_r21/`
- `r12_product_output_web_repair_two_case_20260615_r22`
  - Scope: semicap + cloud capex two case.
  - Result: pass, `2/2` cases passed, `real_specialist_quality_passed=2/2`, `failed_cases=[]`.
  - Summary: `reports/quality/workbench_eval/r12_product_output_web_repair_two_case_20260615_r22_agent_graph_vnext_r12_successor_12.json`
  - Output: `eval/sec_cases/outputs/multi_agent_vnext_r12_successor_12_eval/r12_product_output_web_repair_two_case_20260615_r22/`

## Verification

- `python -m py_compile src\sec_agent\memo_llm.py src\sec_agent\langgraph_orchestrator.py src\sec_agent\multi_agent_runtime.py scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py src\sec_agent\workbench\job_runner.py`
- `python -m pytest tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_judgment_memo_verifier.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_operator_permissions.py tests\test_workbench_job_runner.py -q`
  - Result: `148 passed`.

## Decision

- C 盘/pagefile 清理确实影响了 CUDA/BGE subprocess 可用性；清理后 CUDA smoke 和 R12 case 均可跑。
- 不采用全局 CPU fallback。当前主线是 CUDA queue + batch retry + CPU spillover as explicit resource recovery。
- ASML 这类非本地 SEC/FPI 覆盖缺口不能直接暴露 bounded gap；Lead targeted repair 必须先查官方 SEC submissions / company IR / local official source，并把 official product surface 作为 context ClaimCard 交给产品维度。
- source_gap 可以保留为缺口和后续验证项，但不能在有正向 official context / company fact 时抢占 Memo Writer 主输入。

## Remaining

- R12 broader release 仍未完成：12-case successor、10-20 case broader gate、release readiness report 还要在下一轮执行。
- semicap 输出仍有关系图外延信息，当前通过 gate，但未来 broader eval 应继续观察是否需要更强的 focus-ticker narrative constraint。
- 本轮没有更新 Milvus index；本轮用的是已绑定 runtime 的本地 accepted Milvus DB 和结构化检索链路。
