# SEC Agent Demo 入口 v1

[English version](sec_agent_demo_entrypoints_v1.md)

## 公开仓库范围

保留在公开仓库：

- 源码：`src/`、`scripts/`、`configs/`。
- 小型测试和 eval contracts：`tests/`、`eval_sets/`、`docs/eval/`。
- 只包含路径和摘要的工程日志、模型运行账本：`docs/worklog/`、`reports/model_runs/`。
- 不包含私有 filing、原始 provider 输出和凭据的小型 synthetic fixtures。

保持私有或 ignored：

- SEC/raw/provider 数据：`data/raw_private/`、`data/processed_private/`。
- 搜索索引和模型缓存：`data/indexes/`、`data/models_private/`。
- 运行输出：`eval/`、`reports/quality/`、`reports/demo/`、`reports/logs/`。
- API keys、SSH passwords、provider tokens、`.env`、cloud scratch files。

## 本地 Closeout Smoke

这是默认的提交前 readiness 入口。它使用本地 fixtures、确定性 contracts 和非 LLM 主链路检查，不需要 API keys。

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

更快的 contract-only 检查：

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py `
  --skip-main-chain-case-suite `
  --skip-context-load-smoke `
  --skip-latency-profile
```

输出会写到 `reports/quality/resume_closeout/`，该目录被 Git 忽略。

## 云端 Full-Source DeepSeek 检查

当云端已有私有 SEC/8-K/market artifacts 和模型 API key 时使用。API key 只通过环境变量注入。

```bash
export DEEPSEEK_API_KEY="<set-in-shell-only>"
cd /root/autodl-tmp/FIN_Insight_Agent

PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python \
BGE_DEVICE=cuda \
QUERY_PLANNER=llm \
SEC_AGENT_SOURCE_POLICY=SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT \
MANIFEST_PATH=data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl \
BM25_INDEX_DIR=data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027 \
OBJECT_BM25_INDEX_DIR=data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027_objects \
MARKET_EVIDENCE_PATH=data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl \
MARKET_SNAPSHOT_ID=20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1 \
MARKET_AS_OF_DATE=2026-05-22 \
bash scripts/cloud/sec_agent_interactive.sh ask-deepseek \
"结合SEC 10-K、最新10-Q、8-K earnings release 和最近三个月 market snapshot，比较 NVDA、AMD、MSFT、AMZN、GOOGL 的 AI 基本面、管理层解释、市场反应和估值分歧。"
```

运行完成后，把 saved run 目录传给 readiness 聚合器：

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir /root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```

## 真实 Session Demo

用于 two-turn 上下文管理 demo。它会启动由 ContextManager 支撑的 session；后续追问复用同一个 active session 和 artifact refs。

```bash
export DEEPSEEK_API_KEY="<set-in-shell-only>"
cd /root/autodl-tmp/FIN_Insight_Agent

PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python \
BGE_DEVICE=cuda \
QUERY_PLANNER=llm \
SEC_AGENT_SOURCE_POLICY=SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT \
MANIFEST_PATH=data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl \
BM25_INDEX_DIR=data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027 \
OBJECT_BM25_INDEX_DIR=data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027_objects \
MARKET_EVIDENCE_PATH=data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl \
MARKET_SNAPSHOT_ID=20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1 \
MARKET_AS_OF_DATE=2026-05-22 \
bash scripts/cloud/sec_agent_interactive.sh session-deepseek
```

session 内常用命令：

```text
/state
/context
/answer
/exit
```

## Demo 叙事

第一版公开 demo 需要清楚展示这些边界：

- 用户问题是自由形式中文投研问题。
- Planner 选择 SEC 10-K/latest 10-Q/8-K/market snapshot source tiers。
- 工具链负责检索、exact-value ledger 构建、market snapshot 绑定、coverage、Judgment Plan、synthesis、gates 和 rendering。
- follow-up turn 复用 ContextManager 的 active answer，而不是启动无关的新 run。
- Renderer 明确标注 SEC 审计/未审计边界、company-authored 8-K 边界，以及 market snapshot 的 `as_of_date`。

## 当前非生产边界

- JSON-backed session state 适合本地和单进程 demo，不适合多进程服务。
- full-source 质量依赖私有数据和索引，但这些不会进入公开仓库。
- DeepSeek 输出速度由 provider 和模型路由决定；本地 P0 优化集中在非 LLM 的 retrieval、ledger、coverage 和 session overhead。
- Market snapshot 是非实时数据，必须展示 `snapshot_id` 和 `as_of_date`。
