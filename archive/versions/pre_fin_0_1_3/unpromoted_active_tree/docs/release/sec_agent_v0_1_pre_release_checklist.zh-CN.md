# SEC Agent v0.1 发布前最终检查清单

[English version](sec_agent_v0_1_pre_release_checklist.md)

> 历史说明：本文记录早期 full30 / SEC Agent 阶段的发布检查，不代表当前 FinSight-Agent 603-company 扩展链路状态。当前公开状态请优先阅读根目录 README 和 `docs/eval/fin_agent_public_eval_summary.zh-CN.md`。

日期：2026-05-26

## 发布范围

这是第一版面向简历展示的受约束 SEC 投研 Agent：

- 信息源层级：SEC 10-K、latest SEC 10-Q、SEC 8-K earnings release、offline market snapshot。
- 公司范围：full30 私有云端 artifact set。
- 当前 filing 覆盖：FY2023-FY2025 10-K，加上 accepted manifest 中 latest FY2026 10-Q/8-K rows。
- Market snapshot: `20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1`，`as_of_date=2026-05-22`。

## Checklist

- [x] 真实 LLM planner-contract eval：
  - Cloud report: `reports/query_contracts/planner_eval_v1/release_closeout_deepseek_eval_20260526_r3.json`
  - Result: `5/5` pass，`meets_step1_acceptance=true`
  - Metrics: `task_type_accuracy=1.0`，`required_task_coverage=1.0`，`metric_family_recall=0.96`，`year_compliance=1.0`，`source_boundary_violation_rate=0.0`，`schema_validation_pass_rate=1.0`
  - 验收前的根因修复：将 closeout planner eval 对齐到 manifest 已证明的 FY2023-FY2026 范围；task coverage 统计纳入 caveat/forbidden-claim 中的边界术语；从 planner contracts 中剥离用户未请求的 analyst-consensus、macro 和 geopolitical tasks。

- [x] 公开范围和 secret-scan contract：
  - 公开：`src/`、`scripts/`、`configs/`、`tests/`、`eval_sets/`、`docs/`、`reports/model_runs/`、`.env.example`、metadata/config files。
  - 私有/ignored：`data/raw_private/`、`data/processed_private/`、`data/indexes/`、`data/models_private/`、`eval/`、`reports/quality/`、`reports/query_contracts/`、cloud scratch files、`.env`、API keys、SSH passwords。
  - `.gitignore` 已排除私有和生成路径，包括 raw retrieval JSON/JSONL/CSV outputs，以及生成的 `reports/model_runs/*.json` files。
  - 最终 tracked-file scans 没有发现私有 data/index paths、cloud endpoints、API-key literals、SSH passwords、FMP key literals 或 private-key blocks。

- [x] README 和 demo entrypoints：
  - Root README 已说明第一版受约束 agent 链路、closeout readiness 命令、cloud full-source demo、session demo 和非密钥凭据处理方式。
  - 中文主文档：`README.md`。
  - 详细 demo 入口：`docs/demo/sec_agent_demo_entrypoints_v1.md` 和 `docs/demo/sec_agent_demo_entrypoints_v1.zh-CN.md`。

- [x] 云端部署和 index rebuild runbook：
  - Runbook: `docs/deployment/sec_agent_cloud_full_source_runbook_v1.md`
  - 中文 runbook: `docs/deployment/sec_agent_cloud_full_source_runbook_v1.zh-CN.md`
  - 内容包括 private artifact contract、full30 ObjectBM25 rebuild command、真实 DeepSeek planner gate command 和 saved-run readiness command。

- [x] merge 前最终验证：
  - Local JSONL 和 Python syntax checks 通过。
  - Local pytest: final `main` merge workspace 中 `83 passed`。
  - Local readiness: `reports/quality/resume_closeout/20260526_210019_resume_closeout_readiness_local_v1.json`，`blocker_fail_count=0`；本地 warning 属于预期，因为公开 workspace 不包含私有 full-source artifacts。
  - Cloud full-source readiness blocker failures 为 `0`，P0 readiness `pass=6/6`。
  - 真实 DeepSeek planner gate 在根因修复后通过。

- [x] 版本 commit、tag 和 main merge：
  - Main commit: `ac692bc Release SEC agent v0.1 resume demo`
  - Release tag: `v0.1.0-resume-demo`
  - Merge target: local `main`

## 非阻塞后续项

- 在声明生产级并发前，用 DB/Redis/file-lock backed transactions 替换 JSON-store request locking。
- 用真实 partial production run 验证 stage-level resume，不只依赖 fixture-backed resume。
- 为 price-only 和 valuation-capable market snapshots 增加 provider capability registry。
- 私有 full-source artifacts 继续排除在公开仓库外；公开仓库只发布可复现命令和摘要型 model-run evidence。
