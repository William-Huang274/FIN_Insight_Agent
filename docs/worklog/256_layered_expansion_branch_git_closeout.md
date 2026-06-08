# 256 Layered Expansion Branch Git Closeout

日期：2026-06-07

## 问题

`codex/layered-data-source-expansion` 已经累积 staged、unstaged 和 untracked 三类改动。继续切到 Workbench backend P0 / A6 集成前，必须先把当前分支的主线范围收口，避免后续分不清哪些脚本、配置、测试和文档属于本阶段扩容主线。

## 收口口径

本轮允许进入 Git staging 的内容：

- Source contracts：`configs/data_sources`、`configs/relationships`、`configs/entities`、quality rubric / retrieval config。
- Small reproducibility manifests：`data/manifests`、`data/external_reference` 下的公司池、source-plan、download-task summary、market/industry manifest summary。它们是可复现实验合同，不是 raw data / index / model。
- Source code：`scripts/data_expansion`、`scripts/relationships`、`scripts/eval_retrieval`、`scripts/eval_multi_agent`、`scripts/cloud`、`scripts/market`、`scripts/industry`、`scripts/ledger`、`src/*` 中本阶段接入所需改动。
- Tests / fixtures：扩容配置、entity resolution、relationship schema/extractor、chunk audit、Milvus A/B、multi-agent source boundary 和 A4/A5 artifact-root fallback 相关测试。
- Durable docs：`docs/architecture`、`docs/eval`、`docs/worklog`、`reports/model_runs`。
- Ignore hygiene：`.gitignore` 中新增 `data/staging/` 和 pid/log 规则。

本轮不进入 Git staging 的内容：

- `data/raw_private/`、`data/processed_private/`、`data/staging/` raw/cache rows。
- `data/indexes/`、Milvus/SQLite/FTS/BM25/ledger 大型二进制或目录。
- `eval/`、`reports/quality/`、云端输出目录和临时上传包。
- SSH 密码、provider API key、OSS 临时 URL。

## 当前主线状态

- Workbench backend P0 已在独立 worktree `D:\FIN_Insight_Agent_workbench_backend_p0`，分支 `codex/workbench-backend-p0-p2`，相对 `origin/main` 领先且测试已绿；不要把当前脏扩容分支直接混入该后端收口。
- 当前扩容分支用于记录 A0-A5 数据源扩展、retrieval/operator wiring、A2-A5 cloud full-assets gate 和后续 A6 最小移植来源。
- A6 应在干净 backend P0 基线的新 integration branch 上接入 Workbench eval/report，而不是继续在本脏分支里堆运行结果。

## 检查

- `git diff --check` 和 `git diff --cached --check` 无 whitespace error。
- 敏感词扫描未发现真实密钥、SSH 密码或 OSS 临时 URL；命中项仅为 `api_key_env` 字段名、规则字符串或工作日志中的路径说明。
- 未跟踪文件最大约 `1MB`，为 source-plan JSONL；没有 raw/index/model 级大产物。

## 后续 staging 原则

- 使用显式 `git add -- <file...>`，不使用 `git add .`。
- 本分支可以拆成后续提交：
  1. universe/source configs + data expansion manifests/scripts/tests。
  2. relationship/entity/chunk/retrieval/Milvus contracts and tests。
  3. multi-agent expanded A2-A5 runtime wiring and tests。
  4. durable docs/worklogs/model-run ledgers。
- A6 Workbench integration 另起分支，从本分支 cherry-pick 或手工移植最小必要文件。
