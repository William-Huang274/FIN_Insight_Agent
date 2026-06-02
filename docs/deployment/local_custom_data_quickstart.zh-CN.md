# 自有数据快速接入

[返回中文主文档](../../README.md)

这份文档面向已经克隆仓库、想用自己数据跑完整链路的用户。公开仓库提供代码、测试、配置样例和数据产物合同；SEC 原文、市场数据、索引、模型缓存和 API key 都由用户在本地或自己的运行环境中准备。

## 1. 最小环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

先跑不需要 API key 的结构检查：

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

如果要跑完整生成链路，需要设置 API 模型路由。DeepSeek 是已验证路线之一，也可以换成其他 OpenAI-compatible 接口。

```bash
export LLM_BACKEND=deepseek
export MODEL_NAME=deepseek-v4-pro
export API_KEY_ENV=DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY="<set-in-shell-only>"
```

API key 不要写进 `.env.example`、README、脚本或运行产物。

## 2. 最快接入方式

复制配置模板：

```bash
cp configs/sec_agent_full_source_demo.env.example .env
```

`.env` 会被 Git 忽略。把里面的路径改成你自己的本地数据产物：

```bash
MANIFEST_PATH=data/processed_private/manifests/<your_manifest>.jsonl
BM25_INDEX_DIR=data/indexes/bm25/<your_text_index>
OBJECT_BM25_INDEX_DIR=data/indexes/bm25/<your_object_index>
MARKET_EVIDENCE_PATH=data/processed_private/market/evidence_packs/<your_market_evidence>.jsonl
MARKET_SNAPSHOT_ID=<your_snapshot_id>
MARKET_AS_OF_DATE=<YYYY-MM-DD>
```

检查配置是否能被入口识别：

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh config-full-source-api
```

跑一个短问题，先确认链路能走通：

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh ask-full-source-api \
"结合 10-K、最新 10-Q、8-K 业绩新闻稿和最近三个月市场快照，比较 NVDA、AMD、MSFT 的基本面、管理层解释和市场反应。"
```

多轮会话入口：

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh session-full-source-api
```

## 3. 主链路需要哪些数据产物

| 产物 | 作用 | 对应变量 |
| --- | --- | --- |
| SEC 清单 JSONL | 描述可检索披露文件的公司、财年、表单类型、来源层级和本地路径 | `MANIFEST_PATH` |
| 文本 BM25 索引 | 检索 10-K / 10-Q / 8-K 段落证据 | `BM25_INDEX_DIR` |
| 结构化对象 BM25 索引 | 检索表格、指标和结构化财务对象 | `OBJECT_BM25_INDEX_DIR` |
| 市场快照证据 JSONL | 提供离线价格、收益率、事件窗口和估值语境 | `MARKET_EVIDENCE_PATH` |

市场快照不是所有问题都必需。如果只做 SEC-only 或 SEC + 8-K，可以留空市场变量，并使用相应来源策略。完整演示路径通常使用：

```bash
SEC_AGENT_SOURCE_POLICY=SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT
```

## 4. 从 SEC 数据生成检索产物

先准备一个 universe 配置。可以复制现有配置文件，改成自己的 ticker、分类、年份和 `form_types`。

下载或更新 SEC 10-K / 10-Q：

```bash
python scripts/download_sec_filings.py \
  --config configs/<your_universe>.yaml \
  --form-types 10-K,10-Q \
  --allow-missing
```

构建年报和季报清单：

```bash
python scripts/build_sec_manifest.py \
  --config configs/<your_universe>.yaml \
  --form-types 10-K \
  --years 2023,2024,2025 \
  --output data/processed_private/manifests/<your_10k_manifest>.jsonl

python scripts/build_sec_manifest.py \
  --config configs/<your_universe>.yaml \
  --form-types 10-Q \
  --years 2026,2027 \
  --output data/processed_private/manifests/<your_10q_manifest>.jsonl
```

把多年 10-K 和最新可用 10-Q 合成混合清单：

```bash
python scripts/build_sec_mixed_latest_manifest.py \
  --annual-manifest data/processed_private/manifests/<your_10k_manifest>.jsonl \
  --interim-manifest data/processed_private/manifests/<your_10q_manifest>.jsonl \
  --annual-years 2023,2024,2025 \
  --output data/processed_private/manifests/<your_mixed_manifest>.jsonl
```

解析文本、构建证据对象和索引：

```bash
python scripts/build_sec_chunks.py \
  --manifest data/processed_private/manifests/<your_mixed_manifest>.jsonl \
  --output data/processed_private/chunks/<your_mixed_chunks>.jsonl

python scripts/build_evidence_store.py \
  --chunks data/processed_private/chunks/<your_mixed_chunks>.jsonl \
  --output data/processed_private/evidence_objects/<your_mixed_evidence>.jsonl

python scripts/build_structured_objects.py \
  --evidence-path data/processed_private/evidence_objects/<your_mixed_evidence>.jsonl \
  --prefix <your_prefix>

python scripts/build_bm25_index.py \
  --evidence data/processed_private/evidence_objects/<your_mixed_evidence>.jsonl \
  --output-dir data/indexes/bm25/<your_text_index>

python scripts/build_object_bm25_index.py \
  --structured-dir data/processed_private/structured_objects \
  --prefix <your_prefix> \
  --output-dir data/indexes/bm25/<your_object_index>
```

## 5. 增加 8-K 业绩材料

如果希望模型引用管理层解释，需要单独准备 8-K 业绩材料。它的用途是补充公司管理层口径，不能替代 10-K / 10-Q 里的财务事实。

```bash
python scripts/download_sec_8k_earnings.py \
  --config configs/<your_8k_universe>.yaml \
  --allow-missing

python scripts/build_sec_8k_earnings_manifest.py \
  --config configs/<your_8k_universe>.yaml \
  --output data/processed_private/manifests/<your_8k_manifest>.jsonl \
  --gap-output data/processed_private/source_gaps/<your_8k_gaps>.jsonl

python scripts/build_sec_8k_earnings_chunks.py \
  --manifest data/processed_private/manifests/<your_8k_manifest>.jsonl \
  --output data/processed_private/chunks/<your_8k_chunks>.jsonl
```

随后把 8-K chunks 或 evidence 与 10-K / 10-Q 产物合并，再重建 BM25 / ObjectBM25 索引。8-K 来源层级应保持为 `company_authored_unaudited_sec_filing`。

## 6. 增加离线市场快照

市场数据建议先落盘成离线快照，再交给链路使用。不要让模型凭记忆生成“当前价格”。

无 key 价格快照：

```bash
python scripts/market/06_download_yahoo_chart_snapshot.py \
  --tickers-config configs/<your_universe>.yaml \
  --range 3mo \
  --interval 1d \
  --snapshot-id <your_snapshot_id>
```

如果有 FMP free key，可以补充估值字段：

```bash
export FMP_API_KEY="<set-in-shell-only>"

python scripts/market/07_enrich_market_snapshot_valuation_fmp.py \
  --input data/raw_private/market/provider_snapshots/<your_snapshot_id>_daily_bars.csv \
  --snapshot-id <your_snapshot_id> \
  --tickers-config configs/<your_universe>.yaml
```

标准化、建目录、计算分析视图并生成市场证据包：

```bash
python scripts/market/10_normalize_market_snapshot_fixture.py \
  --input data/raw_private/market/provider_snapshots/<your_snapshot_id>_daily_bars.csv \
  --snapshot-id <your_snapshot_id> \
  --as-of-date <YYYY-MM-DD> \
  --provider yahoo_chart \
  --benchmark-tickers SPY,QQQ

python scripts/market/20_build_market_snapshot_catalog.py

python scripts/market/30_compute_market_analytics.py \
  --snapshot-id <your_snapshot_id> \
  --window 3M \
  --benchmark-ticker QQQ

python scripts/market/40_build_market_evidence_pack.py \
  --snapshot-id <your_snapshot_id> \
  --window 3M
```

把生成的 `MARKET_EVIDENCE_PATH`、`MARKET_SNAPSHOT_ID` 和 `MARKET_AS_OF_DATE` 写入 `.env`。

## 7. 推荐验证顺序

1. 跑本地结构检查：

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

2. 检查 `.env` 配置：

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh config-full-source-api
```

3. 用 2-3 家公司跑一个短问题，确认检索、数值台账和市场证据都出现。

4. 用 `session-full-source-api` 跑两轮会话，第二轮只聚焦一家公司或一个指标。

5. 把生成的运行结果目录交给就绪检查器：

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```

## 8. 安全边界

- `.env`、API key、原始 SEC 文件、市场数据、索引和运行输出都不要提交。
- 市场快照必须带 `snapshot_id` 和 `as_of_date`。
- 数据清单没有覆盖的公司、表单或期间，应在覆盖检查里暴露缺口，不要让模型补写成“已覆盖”。
- 行业和关系数据只能支持研究范围、经济机制和假设，不能当成已确认合同或客户事实。
- 如果要做多用户服务，需要替换 JSON 会话存储；当前默认更适合演示、评测和单进程研究工作流。
