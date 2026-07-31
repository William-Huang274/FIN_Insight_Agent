# 515｜FIN 0.1 S4 Fact candidate pool independent proof failure

## 结论

用户以“继续”执行 worklog 514 授权的唯一 independent zero-call proof package。
proof 在第一个 disposable Runtime 中失败，第二个 Runtime 按 stop contract 未
启动。没有重试、修补或 live。

## 执行

- proof runner：
  `scripts/releases/prepare_fin_ia_0_1_s4_shared_runtime_fact_candidate_pool_independent_fresh_proof.py`
- runner SHA：
  `413788cd534e9b0eca006598ac976bf493dc87073fff44d48e76bf9c120d5332`
- Python compile：pass
- planned disposable roots / fresh processes：`2 / 2`
- started roots / successful roots：`1 / 0`
- runtime-a pytest：`11 passed / 9 failed`
- runtime-b：未启动
- 临时 root：已清理

runner 复制 backend、src、contract tests、release configs 与 scripts，不复制
78GB data 或历史 reports。子进程清除 Provider credential 环境，并在 socket
connect/create_connection 层 fail-closed。

## 首个可信失败

phase=`runtime_a_fresh_python_pytest_matrix`，
code=`disposable_worker_failed_pytest_exit_1`。

terminal tail 至少保留：

- `test_downstream_failure_preserves_all_prior_and_failing_capture`
  的 `output_state_machine-12` 参数；
- final MU Artifact numeric/identity/manifest/trace mutation test；
- capture-v2 terminal-result materialization test。

runner 只把 stdout/stderr 末尾 500 字符放入异常，没有持久化完整日志与 9 个
failed node IDs。因此当前根因未建立：可能是 disposable package 缺少 fixture
dependency，也可能是 Runtime 依赖原工作树隐含状态。不能把它归为模型问题、
网络问题或已证实的业务合同回归。

## 安全边界

- source Runtime/profile repair：0
- credential presence/value read：0
- model/provider/network/source/tool：全 0
- admission/exact-live/paired/owner/T07：全 0
- automatic retry / second proof：0
- target canonical runtime：proof 时段无写入路径；目标最后写入时间为
  `2026-07-31T01:05:31.7303508+08:00`

## 结果

failure result：
`configs/releases/fin_ia_0_1_s4_shared_runtime_deterministic_fact_candidate_pool_planner_independent_fresh_agent_proof_failure_result_v1_0.json`

failure result SHA：
`23f6fca95ad7a2a1d6ae34d4c3077efa1f84d77c00a7c452b9f535461e7f79eb`

RC-P36-084 未关闭。新增
`RC-P36-085-s4-independent-proof-disposable-runtime-hermeticity-and-failure-observability`。
T06 继续为 `engineering_pass / live_product_blocked / not closed`。

## 下一项

`S4-T06-INDEPENDENT-FACT-CANDIDATE-POOL-PROOF-FIRST-DISPOSABLE-RUNTIME-FAILURE-ROOT-CAUSE-OR-BLOCK-DISPOSITION-DECISION`

下一项只允许零调用处置；不得自动修 runner、第二次 proof、admission 或 live。

## Postflight

- failure result + authority history tests：`10 passed`
- failure/backlog JSON：3 份有效
- Project OS JSONL：4 个文件、合计 1,319 行有效
- 下一 disposition scope preflight：`pass / open blockers 0`
- 第二次 disposable invocation / proof rerun：`0 / 0`
- Runtime/profile repair：0
- model/provider/network/admission/live：全 0
