# 257 Expanded A6 Workbench Eval Integration

日期：2026-06-07

## 问题

扩容链路在 `codex/layered-data-source-expansion` 已完成 A2-A5 云端 gate，并且 Workbench backend P0 已有 trace、token、runtime 和 eval report 能力。继续做 A6 时不能在脏工作树里直接跑真实评测，否则后续很难区分哪些代码属于扩容主线、哪些属于 Workbench 后端、哪些只是一次性运行产物。

## 决策

- 从干净的 Workbench backend P0 基线另起 `codex/expanded-a6-workbench-eval` 分支。
- 把扩容分支的 source/contracts/tests/docs 通过 cherry-pick 接到 backend P0，而不是直接混合两个工作树。
- A6 先接入 Workbench eval runner/report wrapper，真实 DeepSeek smoke/main 后续通过 Workbench profile 和云端 603-company full-assets 路径运行。
- `/api/evals/run` 允许传入一次性 `api_key_value`，只作为 subprocess 环境变量注入，不写入 profile、SQLite、job args 或报告。

## 完成

- 新增 Workbench eval catalog：
  - `expanded_a6_full_chain_smoke`：默认运行 3 个代表 case，覆盖 exact、standard、sector-depth。
  - `expanded_a6_full_chain_main`：运行 `tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl` 中全部 17 个 full-chain / multi-turn case。
- 新增 wrapper `scripts/workbench/run_expanded_a6_eval.py`，封装 `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`，并输出 Workbench 可读 summary JSON。
- Workbench summary 记录：
  - pass/fail、case/category metrics、failed checks。
  - agent-level token rollup、runtime summary、trace/job env ids。
  - artifact 路径和 secret-safety 字段。
- `apps/workbench/backend/app.py` 支持 `/api/evals/run` 接收瞬时 `api_key_value`。
- `src/sec_agent/workbench/job_runner.py` 支持 A6 runner 命令构建、strict mode 和 transient DeepSeek secret env 注入。
- 补充 Workbench backend/job runner/wrapper 单测，验证 secret 不进入 args 或 job metadata。

## 验证

- `python -m py_compile apps/workbench/backend/app.py src/sec_agent/workbench/job_runner.py scripts/workbench/run_expanded_a6_eval.py`
- `git diff --check`
- `python -m pytest tests/test_workbench_expanded_a6_eval.py tests/test_workbench_job_runner.py tests/test_workbench_backend.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_workbench_profiles.py -q`
  - 结果：`84 passed`

## 未运行

- 本轮没有跑真实 DeepSeek A6 smoke/main，没有消耗 provider token。
- 本轮没有把用户提供的 provider key 写入任何文件或 profile。
- 本轮没有生成 `reports/quality/workbench_eval/` 下的真实运行报告；该目录仍应按生成物规则处理，不默认进入 Git。

## 后续

- 在云端 full combined 603 assets / Milvus / market / industry / combined ledger 路径就绪的 Workbench profile 下，先跑 `expanded_a6_full_chain_smoke`。
- smoke 通过后再跑 `expanded_a6_full_chain_main`，并把 Workbench 报告中的 token、runtime、trace、失败桶作为 A6 是否进入默认 expanded route 的证据。
- 历史 worklog 存在并行分支造成的 `231/232` 编号重复；本轮只记录冲突事实，不重编号历史文件。
