# 209 Multi-agent Step17 Gateway Retry Stability

日期：2026-05-31

## Prompt

用户继续要求排查当前 full-chain Specialist 问题，并判断是 Specialist 输出质量问题，还是无法理解上游传入的任务/证据。

## Diagnosis

对比 `185/186` 的目标和 Step17 运行台账后，结论是：上游任务解析、权限矩阵、数据视图和真实 retrieval 主链路已经接入；本次不稳定主要来自 LLM provider transport 层，而不是 Specialist 无法理解上游指令。

失败样例：

```text
run_id: 20260531_step17_specialist_retry_ai_infra_cuda_deepseek_v0_1
case: ma_real_sector_ai_infra_full_chain_real_retrieval
result: fail
root symptom: all 4 specialists failed after 3 attempts with provider_error URLError [Errno 2]
research_lead: pass
universe_relationship: pass
evidence_operators: real retrieval pass, sec_search BM25/BGE pass
```

同一进程 stop-after-coverage 复现实验显示：检索/BGE 后直接调用 `fundamental_analyst` 可成功返回 `SpecialistMemolet`，说明失败不是证据视图或 prompt 合同必然错误，而是 full-chain 长链路下的临时 provider/proxy transport 风险。

## Work Completed

- 在 `src/sec_agent/llm_gateway.py` 增加公共 transport retry：
  - 默认 `LLM_GATEWAY_TRANSPORT_RETRIES=1`；
  - 支持 `LLM_GATEWAY_TRANSPORT_RETRY_BACKOFF_S` 和 `LLM_GATEWAY_TRANSPORT_RETRY_MAX_BACKOFF_S`；
  - HTTP `408/409/425/429/500/502/503/504` 和底层 transport exception 可重试；
  - invalid URL 不重试；
  - 成功/失败结果都记录 `transport_attempt_count` 和 `transport_failures`。
- 在 Research Lead、Universe Relationship、Specialist、Memo LLM 的 model call summary 中保留 transport retry 诊断字段。
- 在 `src/sec_agent/langgraph_orchestrator.py` 修正 verifier diagnostics provider/model 回填：当 verifier 只保存 `calls` 而没有顶层 provider/model 时，从 calls 回填，避免 ledger 误显示空 provider。
- 保留 Specialist provider-error outer retry，并把失败 Specialist 透传为 partial-scope caveat，避免下游 memo 把失败 lens 当作完整分析。

## Verification

单测：

```text
python -m pytest tests/test_llm_gateway.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_specialist_real_evidence_eval.py tests/test_multi_agent_real_llm_chain_eval.py -q
result: 28 passed
```

真实 DeepSeek + CUDA BGE 单 case 复跑：

```text
run_id: 20260531_step17_gateway_retry_ai_infra_cuda_deepseek_v0_1
gate: pass
case_count: 1
passed: 1
real_specialist_quality_passed: 1
tool_calls: 9
failed_checks: 0
memo_status: draft
claim_verification: pass
specialist_verification: pass
```

真实 DeepSeek + CUDA BGE 4 case 稳定性轮次：

```text
run_id: 20260531_step17_gateway_retry_sector_depth_4case_cuda_deepseek_v0_1
gate: pass
case_count: 4
passed: 4
failed: 0
pass_rate: 1.0
total_tool_calls: 39
real_retrieval_required_cases: 4
real_specialist_quality_required_cases: 4
real_specialist_quality_passed: 4
```

Case-level audit：

| Case | Gate | Memo | Claim | Specialist | Tool calls | SEC calls | BGE candidates | CUDA |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| AI infra | pass | draft | pass | pass | 11 | 6 | 96 | true |
| Banking | pass | draft | pass | pass | 9 | 4 | 52 | true |
| Healthcare | pass | draft | pass | pass | 11 | 5 | 73 | true |
| Energy / Utilities | pass | draft | pass | pass | 8 | 4 | 60 | true |

## Interpretation

- `execute_evidence_operators` 已经是真实执行，不是 dry-run；`sec_search_filings` 有真实 context rows、candidate rows 和 BGE rerank rows。
- BGE 不是没拉起来；runtime summary 显示 `bge_device=cuda`、`cuda_available=true`，且每个 case 的 `candidate_sent_to_bge > 0`。
- Specialist 已能正确消费上游传入的 role-specific data view，并在 `source_family` / `evidence_refs` / bounded rows 限制下通过真实 evidence quality gate。
- 之前 AI infra 失败不是业务理解主因，而是 provider transport 层稳定性和失败透传不足；已通过 gateway retry 和 ledger diagnostics 修复。

## Evidence Paths

- Failed diagnostic run:
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_specialist_retry_ai_infra_cuda_deepseek_v0_1/real_chain_eval_summary.json`
- Single-case recovery run:
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_gateway_retry_ai_infra_cuda_deepseek_v0_1/real_chain_eval_summary.json`
- 4-case stability run:
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_gateway_retry_sector_depth_4case_cuda_deepseek_v0_1/real_chain_eval_summary.json`
- Model run report:
  - `reports/model_runs/20260531_multi_agent_step17_gateway_retry_sector_depth_full_chain_deepseek_v0_1.md`

## Follow-up

- 将 gateway retry 参数纳入 workbench/profile 配置，而不是只靠运行时环境变量。
- 扩展 non-contiguous multi-turn / resume / artifact-inspection 真实 full-chain eval。
- 若要把 Step17 从 diagnostic-only 提升为 mainline gate，需要冻结 fixture、artifact versions、token budgets、gateway retry profile 和 BGE device policy。
