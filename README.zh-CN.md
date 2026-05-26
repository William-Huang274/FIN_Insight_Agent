# FinSight-Agent

[English version](README.md)

FinSight-Agent 是一个面向投研场景的证据约束型金融研究 Agent。当前版本聚焦 SEC filing 分析、公司发布的 earnings-release 语境、离线 market snapshot，以及多轮投研会话中的上下文管理。

当前第一版 demo 路径是受约束的 agent 链路，不是裸模型聊天：

```text
用户问题
  -> Query Contract planner
  -> SEC / 8-K / market-snapshot 信息源选择
  -> BM25 / ObjectBM25 / BGE 检索
  -> Runtime Exact-Value Ledger
  -> Evidence Coverage Matrix
  -> Judgment Plan
  -> DeepSeek synthesis
  -> deterministic gates
  -> 渲染后的答案 + ContextManager session state
```

## 当前范围

公开仓库只包含代码、测试、小型 eval contracts 和可复现的运行文档。私有 SEC/provider 数据、索引、云端运行输出和 API 凭据都不进入 Git。

当前面向简历展示的 SEC Agent 支持：

- SEC 10-K、latest 10-Q、8-K earnings release 的证据检索和 Exact-Value Ledger 校验。
- 离线 market snapshot 证据，包含 `snapshot_id`、`as_of_date`、收益率、事件窗口，以及可用时由 FMP 补充的估值字段。
- 基于 ContextManager 的多轮会话、artifact inspection、答案重渲染和 resume 检查。
- 收口 readiness 评测入口：`scripts/evaluate_sec_agent_resume_closeout_readiness.py`。

Demo 和发布范围入口见：

- [中文 demo 入口](docs/demo/sec_agent_demo_entrypoints_v1.zh-CN.md)
- [英文 demo 入口](docs/demo/sec_agent_demo_entrypoints_v1.md)

发布 checklist 和云端部署说明：

- [中文 v0.1 发布 checklist](docs/release/sec_agent_v0_1_pre_release_checklist.zh-CN.md)
- [英文 v0.1 发布 checklist](docs/release/sec_agent_v0_1_pre_release_checklist.md)
- [中文云端 full-source runbook](docs/deployment/sec_agent_cloud_full_source_runbook_v1.zh-CN.md)
- [英文云端 full-source runbook](docs/deployment/sec_agent_cloud_full_source_runbook_v1.md)

## 环境配置

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

在大规模 SEC 下载前，把 `.env.example` 复制为 `.env`，并设置真实的 SEC User-Agent contact。不要提交 `.env`、API keys、云端密码、私有数据或生成索引。

## Closeout Readiness

本地确定性 readiness，不需要 API key：

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

云端已有真实 DeepSeek full-source run 后，可以把 saved run 目录传给 readiness 聚合器：

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir /root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```

第一版发布范围是 FY2023-FY2025 年报 10-K，加上当前 full30 artifact set 中最新可用的 FY2026 10-Q/8-K 证据。除非 manifest 本身对所选公司包含 FY2027 filing，否则不要声称已经覆盖 FY2027。

## Demo 入口

云端 one-shot full-source DeepSeek demo：

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

云端 two-turn session demo：

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

进入 session 后可用命令：

```text
/state
/context
/answer
/exit
```

## SEC Smoke Test

```powershell
python scripts/smoke_test_sec.py --ticker JPM --year 2024
```

期望本地缓存：

```text
data/raw_private/sec/2024/uncategorized/JPM/10-K.html
data/raw_private/sec/2024/uncategorized/JPM/10-K.metadata.json
```

批量下载第一批科技公司 universe：

```powershell
python scripts/download_sec_filings.py --config configs/sec_tech_universe.yaml
```

技术公司 universe 的缓存按 fiscal year、category 和 ticker 组织：

```text
data/raw_private/sec/2024/mega-cap_software_cloud/MSFT/10-K.html
data/raw_private/sec/2024/ai_gpu_semiconductor/NVDA/10-K.html
```

构建 manifest：

```powershell
python scripts/build_sec_manifest.py
```

默认 manifest 输出：

```text
data/processed_private/manifests/sec_tech_10k_manifest.jsonl
```

从 manifest 构建 section-aware chunks：

```powershell
python scripts/build_sec_chunks.py
```

chunker 优先保留语义边界。每个 chunk 保留父级 block 字段，包括 `block_id`、`block_heading`、`block_type`、`block_part_index` 和 `block_part_count`，避免长 section 被切分后丢失业务语境。

HTML table 会先序列化为原子 `TABLE_START` / `TABLE_END` block。chunker 不会在 table block 内部切分，并会用 `contains_table=true` 标记包含表格的 chunk。

小型 parser smoke：

```powershell
python scripts/build_sec_chunks.py --years 2024 --tickers MSFT,NVDA --output data/processed_private/chunks/sec_tech_10k_chunks_smoke.jsonl
```

转换为统一 EvidenceObject store：

```powershell
python scripts/build_evidence_store.py
```

默认 evidence 输出：

```text
data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl
```

构建并查询 BM25 baseline：

```powershell
python scripts/build_bm25_index.py
python scripts/search_bm25.py "What drove Microsoft cloud revenue growth in 2024?" --ticker MSFT --year 2024 --top-k 5
```

构建并查询 dense embedding baseline：

```powershell
python scripts/build_dense_index.py --device cuda --batch-size 128
python scripts/search_dense.py "What drove Microsoft cloud revenue growth in 2024?" --ticker MSFT --year 2024 --top-k 5 --device cuda
```

云端机器如果无法直连 `huggingface.co`，构建 dense index 前可设置镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

从 ModelScope 下载 Qwen embedding model 并构建单独 dense index：

```bash
python scripts/download_modelscope_model.py --model-id Qwen/Qwen3-Embedding-0.6B --cache-dir data/models_private/modelscope
python scripts/build_dense_index.py \
  --model data/models_private/modelscope/Qwen/Qwen3-Embedding-0___6B \
  --output-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b \
  --device cuda \
  --batch-size 8 \
  --query-prompt-name query \
  --max-seq-length 4096
```

对 seed diagnostic set 评测 BM25、dense 和 hybrid RRF retrieval：

```powershell
python scripts/evaluate_retrieval.py --retrievers bm25,dense,hybrid --device cuda
```

seed evaluation set 是小型诊断集：

```text
eval_sets/sec_tech_10k_seed.jsonl
```

生成的 SEC cache 和 indexes 会被 Git 忽略。
