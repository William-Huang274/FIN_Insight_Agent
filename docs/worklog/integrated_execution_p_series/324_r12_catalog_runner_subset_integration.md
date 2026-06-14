# 324 R12 Catalog Runner Subset Integration

日期：2026-06-14

## Prompt

用户确认 50-case catalog 设计没有问题，允许继续按下一步推进。

## Decision

- 不新增另一套 JSONL fixture 作为主入口；把 50-case catalog 作为 canonical source。
- 主 eval runner 增加 catalog loader / subset selector，并把 catalog case 展开为现有 full-chain runner 可消费的 runtime case schema。
- Workbench 增加 catalog subset eval id，避免前端或 Java gateway 只能启动旧 diagnostic fixture。
- 本轮只做 runner/subset 接入和 dry-run 验证，不跑 DeepSeek full-chain。

## Work Completed

- 新增 `src/sec_agent/eval_case_catalog.py`：
  - `load_case_catalog`
  - `expand_case_catalog`
  - catalog case -> runtime eval case adapter
  - family 到 category / execution mode / agents / tool gates / depth gates 的映射
  - release subset membership metadata。
- 更新 `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`：
  - 新增 `--case-catalog-path`
  - 新增 `--case-subset`
  - 新增 `--case-family`
  - 新增 `--dump-expanded-cases-path`
  - 新增 `--dry-run-cases`
  - eval summary 增加 `case_catalog` metadata。
- 更新 `src/sec_agent/workbench/job_runner.py`：
  - 新增 `agent_graph_vnext_r12_successor_12`
  - 新增 `agent_graph_vnext_broader_release_20`
  - 新增 `agent_graph_vnext_load_mix_15`
  - 这三个 eval id 传 `--case-catalog-path tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json` 和对应 `--case-subset`。
- 更新测试：
  - `tests/test_vnext_50_case_catalog.py`
  - `tests/test_multi_agent_real_llm_chain_eval.py`
  - `tests/test_workbench_job_runner.py`
  - `tests/test_workbench_backend.py`
- 更新 `docs/architecture/agent_graph_vnext/14_vnext_50_case_eval_catalog.zh-CN.md` 和 `docs/worklog/00_internal_master_checklist.md`。

## Verification

- `python -m py_compile src\sec_agent\eval_case_catalog.py scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py src\sec_agent\workbench\job_runner.py`
- `python -m pytest tests/test_workbench_job_runner.py::test_build_g11_full_chain_eval_command_targets_vnext_fixture tests/test_workbench_job_runner.py::test_build_run_audit_full_chain_smoke_eval_command tests/test_workbench_job_runner.py::test_build_diagnostic_probe_eval_command_is_non_strict tests/test_workbench_job_runner.py::test_build_r12_successor_eval_command_targets_case_catalog_subset tests/test_workbench_job_runner.py::test_build_broader_release_and_load_mix_eval_commands_target_catalog_subsets -q`：`5 passed`
- `python -m pytest tests/test_vnext_50_case_catalog.py tests/test_multi_agent_real_llm_chain_eval.py::test_multi_agent_real_llm_chain_dry_run_resolves_catalog_subset tests/test_workbench_backend.py::test_workbench_backend_lists_and_starts_controlled_eval_runner tests/test_workbench_backend.py::test_workbench_backend_starts_catalog_subset_eval_runner_without_secret_args -q`：`9 passed`
- Manual dry-run:
  - `python scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py --case-catalog-path tests\fixtures\fin_agent_vnext_50_case_catalog_v0_1.json --case-subset load_mix_15 --dry-run-cases ...`
  - result: `case_count=15`, family distribution `L1=10 / L3=1 / L6=4`。

## Results

- CLI 和 Workbench 现在都能直接按 catalog subset 执行：
  - `r12_successor_12`
  - `broader_release_20`
  - `load_mix_15`
- 旧 JSONL fixture 入口未破坏。
- 本轮发现并同步了旧测试中的 BGE 默认设备断言：runtime 已经是 `auto`，测试不应再期待 `cpu`。

## Follow-up

- 把当前 2-case diagnostic probe 与 catalog #23/#24 建立显式映射。
- 对 `r12_successor_12` 先跑 artifact-reuse / node replay gate，再挑 2-3 个新增 case 跑 full-chain live。
- 后续将 Eval Store 的 dataset/case registry 与 catalog id、subset id、criteria version 进一步绑定。

## Safety Notes

- 未写入 API key 或云端密码。
- Manual dry-run 产生的 `.tmp_vnext_catalog_*` 临时文件已删除。
- 本轮没有跑 DeepSeek full-chain，不产生新的模型成本。
