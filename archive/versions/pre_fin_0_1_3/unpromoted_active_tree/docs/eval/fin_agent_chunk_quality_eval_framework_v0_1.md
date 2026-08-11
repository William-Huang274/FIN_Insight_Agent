# Fin Agent Chunk 质量评估体系 v0.1

日期：2026-06-04

状态：上游数据资产质量框架；独立于工作日志，接入 `docs/eval/fin_agent_investment_research_quality_framework_v0_1.md` 和 S1-S8 分层门控。

执行脚本：`scripts/eval_retrieval/audit_sec_chunk_quality.py`

## 1. 目标

这个评估体系专门回答一个问题：当前 SEC / 8-K 文本切片本身，是否足够支撑后面的 BM25、ObjectBM25、BGE 重排、专家分析和最终 memo。

它不评价模型写得好不好，也不评价某个 full-chain case 是否通过。它先检查更底层的数据资产：

- chunk 长度是否稳定，是否有异常超长或过短。
- overlap 是否真实存在，切开的上下文是否能接上。
- 表格是否被截断，`[TABLE_START]` / `[TABLE_END]` 是否成对。
- 10-K / 10-Q / 8-K 核心 section 是否覆盖。
- chunk、evidence object、BM25 index 是否一一对齐。
- dense / FAISS / Milvus 是否属于当前主线，还是实验召回层。

如果这一层不通过，后面不能急着调 Specialist prompt 或 Memo Writer。先修 chunk / evidence / index，再做召回和模型评测。

## 2. 当前主线数据合同

当前 full-chain 的主线召回仍是 BM25 / ObjectBM25 / BGE，不是持久向量库。旧配置里仍保留 `data/processed_private` / `data/indexes` 路径，便于本地链路沿用；S0 通过后，本轮可作为后续接入候选的 v0.5 资产在 Z 盘：

| 资产 | 路径 / 说明 |
| --- | --- |
| chunk 文件 | `Z:/FIN_Insight_Agent_artifacts/chunks/sector_depth_full238_us_v0_5_mixed_with_8k_chunks_fy2023_2027.jsonl`，S0 通过资产 |
| evidence object | `Z:/FIN_Insight_Agent_artifacts/evidence_objects/sector_depth_full238_us_v0_5_mixed_with_8k_evidence_fy2023_2027.jsonl`，与 chunk 一一对应 |
| BM25 | `Z:/FIN_Insight_Agent_artifacts/indexes/bm25/sector_depth_full238_us_v0_5_mixed_with_8k_fy2023_2027` |
| ObjectBM25 / SQLite FTS | `Z:/FIN_Insight_Agent_artifacts/indexes/bm25/sector_depth_full238_us_v0_5_mixed_with_8k_fy2023_2027_objects` |
| BGE reranker | `BAAI/bge-reranker-v2-m3` 本地 snapshot，query time 重排 |

当前主线不是持久向量库。它是：

1. SEC / 8-K HTML 转 chunk。
2. chunk 转 EvidenceObject。
3. EvidenceObject 建 BM25。
4. 结构化对象建 ObjectBM25 / SQLite FTS。
5. query time 触发 BM25 / ObjectBM25 候选召回。
6. BGE reranker 在线重排候选。
7. 结果进入 runtime ledger / context rows，再交给 Specialist。

历史 dense / FAISS 索引可以保留作实验基线，但不是当前默认召回层。

## 3. 切片规则

| 来源 | 脚本 / 函数 | 默认目标 |
| --- | --- | --- |
| 10-K / 10-Q | `scripts/data_sec/build_sec_chunks.py` -> `build_chunks_for_filing` | `target_words=900`, `overlap_words=150`, `min_words=80` |
| 8-K earnings release | `scripts/data_sec/build_sec_8k_earnings_chunks.py` -> `build_8k_earnings_chunks` | `target_words=650`, `overlap_words=100`, `min_words=40` |

切片顺序：

1. HTML 清洗，隐藏元素移除。
2. 表格序列化为 `[TABLE_START id=...] ... [TABLE_END]`。
3. 按 SEC item 定位 section。
4. 按 heading / paragraph 构建语义块。
5. 在语义块内按 word window 切 chunk，并保留 overlap tail。

## 4. Hard Gate

| Gate | 要求 |
| --- | --- |
| `parse_errors_absent` | JSONL 解析错误必须为 0 |
| `chunk_ids_present` | 每行必须有 `chunk_id` |
| `duplicate_chunk_ids_absent` | `chunk_id` 不允许重复 |
| `table_markers_balanced` | 表格起止标记必须成对 |
| `char_boundaries_valid` | `char_start < char_end`，边界必须有效 |
| `chunk_length_extremes_bounded` | 极端超长 chunk 比例必须 <= 1% |
| `short_chunk_rate_bounded` | 过短 chunk 比例必须 <= 5% |
| `long_chunk_rate_bounded` | 超长 chunk 比例必须 <= 8% |
| `split_block_parts_complete` | 多 part block 不能缺 part |
| `split_overlap_present` | 多 part chunk 的零 overlap pair 比例必须 <= 5% |
| `primary_core_item_coverage_bounded` | 10-K / 10-Q 核心 item 缺失 filing 比例必须 <= 2% |
| `evidence_rows_match_chunks` | EvidenceObject 与 chunk id 必须对齐 |
| `evidence_ids_unique` | EvidenceObject 的 `evidence_id` 不允许重复 |
| `bm25_records_match_evidence` | BM25 metadata records 必须等于 evidence 文件行数 |
| `object_bm25_present` | ObjectBM25 / SQLite FTS 必须存在 |

## 5. 诊断项

这些项不一定立刻 fail，但会进入 warnings：

- `long_chunk_tail_review_needed`：长度尾部偏重，可能影响 BGE 截断和 Specialist row payload。
- `long_table_chunks_need_table_aware_review`：表格 chunk 超长，需要确认 exact-value ledger 是否能覆盖表格里的数字。
- `some_split_pairs_have_zero_text_overlap`：overlap 真实生效不稳定。
- `some_filings_missing_expected_items`：有 filing 缺核心 item，需要看是不是 SEC 格式特殊还是 parser 失败。
- `bm25_metadata_record_count_mismatch`：BM25 记录数和 evidence 不一致。

## 6. 和现有 Eval 矩阵的关系

新增 S0：Chunk / Retrieval Asset Quality。

| 层级 | 作用 |
| --- | --- |
| S0 | 检查 chunk / evidence / BM25 / ObjectBM25 资产是否能支撑召回 |
| S1 | Research Lead 理解问题和激活 agent |
| S2 | Universe / Relationship 形成经济关系假设 |
| S3 | Evidence Operators 真实召回 / 重排 / ledger |
| S4-S8 | Coverage、Specialist、Aggregator、Memo、Verifier |
| S9-S10 | Renderer / full-chain / multi-turn |

S3 如果出现召回差、ledger rows 缺失、BGE 候选不够，排查顺序必须先看 S0：

1. chunk 是否缺 item。
2. chunk 是否过长导致 BGE 截断。
3. 表格是否被完整保留。
4. EvidenceObject 是否覆盖全部 chunk。
5. BM25 / ObjectBM25 是否基于同一版本数据。

## 7. Milvus 实验门控

Milvus 只能作为语义召回实验层接入，不能替代 BM25、ObjectBM25 和 exact-value ledger。

允许做实验的前提：

- S0 hard gate 通过。
- EvidenceObject 与 BM25 记录数一致。
- 表格边界没有断裂。
- core item coverage 没有系统性缺口。

推荐实验位置：

```text
Research Lead route
 -> BM25 / ObjectBM25 精确召回
 -> Milvus semantic recall
 -> BGE rerank
 -> evidence ledger
 -> Specialist
```

实验先只跑 retrieval-only A/B，不直接跑 full-chain：

| 组 | 说明 |
| --- | --- |
| BM25/ObjectBM25 baseline | 当前主线 |
| Milvus semantic only | 看语义召回能否找到相关材料 |
| Hybrid RRF | BM25/ObjectBM25 + Milvus 融合后再 BGE，必须保留 ticker-balanced 选择器 |

通过标准：

- route 成功和真实 evidence 质量要分开看；route 成功不代表 evidence 可以进入 Specialist。
- sector-depth / relationship / paraphrase case 的 usable evidence rows 和 ticker coverage 不能低于 BM25 基线；如果只是个别 case 提升，先保持实验层，不直接升主线。
- exact lookup 的 ledger 命中率不能下降，ObjectBM25 / exact-value ledger 必须继续保留。
- 最终传给 Specialist 的 evidence rows 更丰富，但 verifier hallucination gate 不变差。
- 延迟和资源消耗在可接受范围内，并记录 embedding 截断策略。

已跑真实诊断：

| Run ID | 结论 |
| --- | --- |
| `20260604_sec_chunk_quality_full238_v0_5_parser_item_s0_v0_1` | S0 `pass`，`91,708` chunks，`238` tickers，duplicate chunk/evidence id 为 0，primary core item missing filing rate `0.64%` |
| `20260604_fin_agent_milvus_retrieval_ab_full238_v0_3_balanced_rrf` | retrieval-only A/B `pass`，`12/12` cases；Hybrid 不伤 exact lookup，但平均 usable rows 没明显超过 BM25 |

Milvus 实验结论：

- Milvus semantic-only 不能替代 BM25；银行、能源这类数值和行业术语密集问题上会偏窄。
- Hybrid RRF 需要 ticker-balanced selector，否则 sector-depth 会丢行业覆盖。
- 当前可以考虑 feature-flag 实验接入，但不能把 Milvus 作为默认主线，也不能取消 ObjectBM25 / exact-value ledger。

## 8. 执行命令

```powershell
python scripts\eval_retrieval\audit_sec_chunk_quality.py `
  --chunks-path Z:/FIN_Insight_Agent_artifacts/chunks/sector_depth_full238_us_v0_5_mixed_with_8k_chunks_fy2023_2027.jsonl `
  --evidence-path Z:/FIN_Insight_Agent_artifacts/evidence_objects/sector_depth_full238_us_v0_5_mixed_with_8k_evidence_fy2023_2027.jsonl `
  --bm25-index-dir Z:/FIN_Insight_Agent_artifacts/indexes/bm25/sector_depth_full238_us_v0_5_mixed_with_8k_fy2023_2027 `
  --object-bm25-index-dir Z:/FIN_Insight_Agent_artifacts/indexes/bm25/sector_depth_full238_us_v0_5_mixed_with_8k_fy2023_2027_objects `
  --run-id 20260604_sec_chunk_quality_full238_v0_5_parser_item_s0_v0_1 `
  --strict
```

输出：

```text
eval/sec_cases/outputs/chunk_quality_audit/<run_id>/chunk_quality_summary.json
eval/sec_cases/outputs/chunk_quality_audit/<run_id>/chunk_quality_summary.md
```

Milvus retrieval-only A/B：

```powershell
python scripts\eval_retrieval\eval_milvus_retrieval_ab.py `
  --run-id 20260604_fin_agent_milvus_retrieval_ab_full238_v0_3_balanced_rrf `
  --collection-max-rows 10000 `
  --top-k 20 `
  --bm25-top-k 60 `
  --object-top-k 60 `
  --milvus-top-k 60 `
  --embedding-batch-size 32 `
  --embedding-max-seq-length 512 `
  --vector-text-max-chars 1400 `
  --insert-batch-size 512
```

输出：

```text
eval/sec_cases/outputs/milvus_retrieval_ab/<run_id>/milvus_retrieval_ab_summary.json
eval/sec_cases/outputs/milvus_retrieval_ab/<run_id>/milvus_retrieval_ab_summary.md
```
