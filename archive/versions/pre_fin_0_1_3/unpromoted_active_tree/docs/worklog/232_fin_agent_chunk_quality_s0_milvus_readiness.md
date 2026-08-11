# 232 Fin Agent Chunk Quality S0 与 Milvus Readiness

日期：2026-06-04

## 背景

用户要求先建立真正面向 chunk 质量的系统评估体系，补进当前 eval 矩阵，真实跑一次 full238 chunk 审计，然后再判断 Milvus 应该如何插入项目并做实验。

## 决策

新增 S0：Chunk / Retrieval Asset Quality。S0 在 Research Lead 之前运行，专门检查 chunk / EvidenceObject / BM25 / ObjectBM25 资产质量。只有 S0 hard gate 通过后，Milvus 才能进入 retrieval-only 语义召回实验；不能在 chunk id 和 evidence id 不唯一时接入主链路。

Milvus 定位保持为语义召回实验层：

```text
Research Lead route
 -> BM25 / ObjectBM25 精确召回
 -> Milvus semantic recall
 -> BGE rerank
 -> evidence ledger
 -> Specialist
```

## 已完成

- 新增 chunk 质量评估框架：`docs/eval/fin_agent_chunk_quality_eval_framework_v0_1.md`。
- 在投研质量框架中加入 D0 Chunk 与检索资产质量。
- 在分层门控执行文档中加入 S0。
- 在 `configs/fin_agent_quality_rubric_v0_1.json` 中加入 `chunk_quality` stage gate。
- 更新 `configs/retrieval.yaml`，把当前主线从旧 `target_tokens/dense_top_k` 改成实际 `target_words/overlap_words` 和 BM25/ObjectBM25/BGE 主线说明。
- 新增脚本：`scripts/eval_retrieval/audit_sec_chunk_quality.py`。
- 新增测试：
  - `tests/test_sec_chunk_quality_audit.py`
  - `tests/test_sec_chunk_id_uniqueness.py`
- 修复未来 chunk 生成端的重复 block id 风险：`src/ingestion/parse_sec_filing.py` 在同一 filing 内遇到重复 base block id 时追加 `_OCC_02` 后缀。

## 真实 S0 运行结果：第一次审计失败

Run ID：`20260604_sec_chunk_quality_full238_v0_3`

输出：

- `eval/sec_cases/outputs/chunk_quality_audit/20260604_sec_chunk_quality_full238_v0_3/chunk_quality_summary.json`
- `eval/sec_cases/outputs/chunk_quality_audit/20260604_sec_chunk_quality_full238_v0_3/chunk_quality_summary.md`

结果：`fail`

关键指标：

| 指标 | 结果 |
| --- | ---: |
| chunk rows | 89,112 |
| tickers | 238 |
| filings | 1,171 |
| 10-K chunks | 73,282 |
| 10-Q chunks | 12,279 |
| 8-K chunks | 3,551 |
| word p50 / p95 / p99 | 563 / 987 / 1,100 |
| max word count | 2,820 |
| too long rate | 0.0909% |
| duplicate chunk id extra rows | 2,183 |
| evidence rows | 89,112 |
| unique evidence ids | 86,929 |
| duplicate evidence ids | 2,183 |
| BM25 metadata records | 89,112 |
| ObjectBM25 records | 3,035,688 |
| primary core item missing filing rate | 14.51% |
| unbalanced table marker chunks | 30 |

失败项：

- `duplicate_chunk_ids_absent=false`
- `table_markers_balanced=false`
- `split_block_parts_complete=false`
- `primary_core_item_coverage_bounded=false`
- `evidence_rows_match_chunks=false`
- `evidence_ids_unique=false`

解释：

- BM25 records 与 evidence 文件行数一致，不是索引行数没建对。
- 真正问题是 chunk id / evidence id 不唯一，导致同一 `evidence_id` 对应多段文本。
- 重复根因来自 `block_id` 合同不够唯一：同一个 filing 中同一 item 多次被识别成 section 时，block index 会重置，旧 `block_id` 没有 section occurrence 信息。
- 小规模 AES 2023 10-K 重建探针显示，新 `_OCC_02` 保护可消除重复 ID：204 rows、duplicate id 0、occurrence suffix 12。
- 核心 item 缺口集中在部分 10-K parser / section boundary 问题，后续要按 ticker/form 定位修 parser，而不是让下游 agent 猜。

## Parser 修复与资产重建

为了让后续召回实验有合格上游，先修 parser / section splitter，再重建 full238 资产。

已修复：

- `src/ingestion/section_splitter.py`
  - 增加 10-K Item 1 的非标准标题识别。
  - 对 split heading 场景先拼 12 行 header window 再识别 item，避免 `Item` / `1A.` / `RISK FACTORS` 被拆开后漏掉。
  - 跳过 table marker 对 section header 的干扰。
  - 增加 nontraditional marker cross-reference 过滤，避免把“see the section titled ...”当成真实 section 开始。
- `src/ingestion/parse_sec_filing.py`
  - 同一 filing 内重复 base block id 会追加 occurrence 后缀，避免生成重复 `chunk_id`。

重建后的 v0.5 资产：

| 资产 | 路径 / 结果 |
| --- | --- |
| primary 10-K / 10-Q chunks | `Z:\FIN_Insight_Agent_artifacts\chunks\sector_depth_full238_us_v0_5_mixed_10k_latest_10q_chunks_fy2023_2027.jsonl`，`88,157` rows |
| 8-K earnings chunks | `Z:\FIN_Insight_Agent_artifacts\chunks\sector_depth_full238_us_v0_5_8k_earnings_chunks_2026_2027.jsonl`，`3,551` rows |
| mixed chunks | `Z:\FIN_Insight_Agent_artifacts\chunks\sector_depth_full238_us_v0_5_mixed_with_8k_chunks_fy2023_2027.jsonl`，`91,708` rows |
| evidence objects | `Z:\FIN_Insight_Agent_artifacts\evidence_objects\sector_depth_full238_us_v0_5_mixed_with_8k_evidence_fy2023_2027.jsonl`，`91,708` rows |
| BM25 | `Z:\FIN_Insight_Agent_artifacts\indexes\bm25\sector_depth_full238_us_v0_5_mixed_with_8k_fy2023_2027`，`91,708` records |
| ObjectBM25 | `Z:\FIN_Insight_Agent_artifacts\indexes\bm25\sector_depth_full238_us_v0_5_mixed_with_8k_fy2023_2027_objects`，`3,148,444` records |

## 真实 S0 运行结果：v0.5 通过

Run ID：`20260604_sec_chunk_quality_full238_v0_5_parser_item_s0_v0_1`

输出：

- `eval/sec_cases/outputs/chunk_quality_audit/20260604_sec_chunk_quality_full238_v0_5_parser_item_s0_v0_1/chunk_quality_summary.json`
- `eval/sec_cases/outputs/chunk_quality_audit/20260604_sec_chunk_quality_full238_v0_5_parser_item_s0_v0_1/chunk_quality_summary.md`

结果：`pass`

关键指标：

| 指标 | 结果 |
| --- | ---: |
| chunk rows | 91,708 |
| tickers | 238 |
| filings | 1,171 |
| 10-K / 10-Q / 8-K chunks | 74,585 / 13,572 / 3,551 |
| word p50 / p95 / p99 | 560 / 987 / 1,099 |
| max word count | 2,820 |
| duplicate chunk id extra rows | 0 |
| duplicate evidence ids | 0 |
| unbalanced table marker chunks | 0 |
| evidence rows | 91,708 |
| BM25 metadata records | 91,708 |
| ObjectBM25 records | 3,148,444 |
| primary core item missing filing rate | 0.64% |

仍需关注但不阻断：

- `long_table_chunks_need_table_aware_review`：表格 chunk 尾部仍有超长样本，后续 exact-value ledger 要继续守住表格数字。
- `some_split_pairs_have_zero_text_overlap`：少量相邻 part 的文本 overlap 为 0，但整体比例 `2.45%`，低于 hard gate。
- `some_filings_missing_expected_items`：还有 6 个 primary filing 缺核心 item，低于 `2%` 阈值，应作为后续 parser 维护项。

## Milvus 安装与定位

Milvus Lite 已安装在 Z 盘依赖目录，不占用 C 盘：

- 依赖目录：`Z:\FIN_Insight_Agent_artifacts\python_deps\milvus_lite`
- Milvus Lite DB 输出目录：`Z:\FIN_Insight_Agent_artifacts\milvus\<run_id>\milvus_lite.db`

安装方式：

- 先用清华 PyPI 镜像安装 `pymilvus[milvus_lite]` 到 `--target Z:\FIN_Insight_Agent_artifacts\python_deps\milvus_lite`。
- 再单独安装 `milvus-lite`，因为第一次 `pymilvus` 安装没有带出 Milvus Lite runtime。
- 本地 import 与一行插入/搜索 smoke 通过。

定位不变：Milvus 不能替代 BM25、ObjectBM25 和 exact-value ledger。它只能作为语义召回补充层，先在 retrieval-only 里证明能改善关系型、行业深挖和改写问题的可用证据，同时不能拉低精确数值查询。

## Milvus Retrieval-Only A/B

新增脚本：`scripts/eval_retrieval/eval_milvus_retrieval_ab.py`

新增用例：`tests/fixtures/fin_agent_retrieval_ab_cases_v0_1.jsonl`

实验组：

| 组 | 说明 |
| --- | --- |
| BM25 | 文本召回基线 |
| ObjectBM25 | 结构化对象 / exact-value 辅助基线 |
| Milvus semantic only | 只看向量语义召回是否有用 |
| Hybrid RRF | BM25 + ObjectBM25 + Milvus 融合，并用 ticker-balanced selector 保留覆盖 |

Milvus collection metadata 已包含：

```text
ticker / fiscal_year / form_type / source_tier / item_code / category_slug / period_type / contains_table
```

第一次完整 A/B 在 BGE-M3 全长 chunk embedding 上超时，原因是长文本直接进 embedding，显卡计算没有形成稳定吞吐。修正后设置：

- `embedding_max_seq_length=512`
- `vector_text_max_chars=1400`
- `embedding_device=cuda`
- `collection_max_rows=10000`

最终 run：

`20260604_fin_agent_milvus_retrieval_ab_full238_v0_3_balanced_rrf`

结果：`pass`，`12/12` cases 通过。

| 类别 | 通过 |
| --- | ---: |
| exact lookup | 2/2 |
| sector-depth | 6/6 |
| relationship | 2/2 |
| paraphrase | 2/2 |

汇总：

| 指标 | 结果 |
| --- | ---: |
| mean BM25 usable rows | 19.33 |
| mean Milvus usable rows | 17.92 |
| mean Hybrid usable rows | 19.33 |
| collection rows | 7,263 |
| collection tickers | 31 |
| elapsed | 547.1s |

重要观察：

- Semantic-only 对 paraphrase / relationship 有帮助，但在 banking / energy 这类数值和行业术语密集问题上容易收窄到少数 ticker。
- Hybrid RRF 如果不做 ticker-balanced selector，会丢 sector-depth 的覆盖；修复后 sector-depth、relationship、paraphrase 都通过。
- exact lookup 仍必须靠 ObjectBM25 / exact-value ledger，Milvus 不能替代精确数值路径。
- 本轮 `Hybrid` 没有明显提高平均 usable rows，但改善了若干 case 的 ticker coverage，并证明在不伤害 exact lookup 的情况下可以作为召回补充实验。

## 2026-06-05 云端 4090 BGE-M3 建库

目标：把 typed vector Milvus 建库搬到 4090 云端验证，避免本地 8GB 显存加载 BGE-M3 OOM。

云端路径：

- 工作目录：`/autodl-fs/data/fin_agent_milvus_bge_m3`
- Milvus Lite DB：`/autodl-fs/data/fin_agent_milvus_bge_m3/milvus/20260605_fin_agent_milvus_bge_m3_cloud_build_v0_2_local_model/milvus_lite.db`
- Summary：`/autodl-fs/data/fin_agent_milvus_bge_m3/outputs/milvus_retrieval_ab/20260605_fin_agent_milvus_bge_m3_cloud_build_v0_2_local_model/milvus_retrieval_ab_summary.json`
- 本地上传包：`Z:\FIN_Insight_Agent_artifacts\cloud_uploads\milvus_bge_m3_20260605\fin_agent_milvus_bge_m3_payload_20260605.tar.gz`
- 对象种子：`Z:\FIN_Insight_Agent_artifacts\cloud_uploads\milvus_bge_m3_20260605\object_vector_seed_v0_2.jsonl`

环境处理：

- 云端默认 Ubuntu 镜像没有系统 Python，先安装 `python3/python3-venv/python3-pip`。
- 根分区只有 30GB，CUDA wheel 安装会打满根盘；后续全部迁到 `/autodl-fs/data`，并把 venv、pip cache、HF cache、Milvus DB、输出都放在数据盘。
- 云端已有 `/root/miniconda3`，其中 `torch 2.8.0+cu128` 可用，能识别 4090；最终用数据盘 venv `--system-site-packages` 复用 conda CUDA Torch，只在 venv 里补 `sentence-transformers/pymilvus/milvus-lite`。
- 直连 HuggingFace 超时，`hf-mirror.com` 可用。BGE-M3 大权重由镜像下载完成，缺失的 tokenizer / pooling 小文件从本地 snapshot 上传到 `models/bge-m3-local`，大权重用符号链接复用 HF cache。
- 远端 `sentence-transformers 5.5.1 + transformers 5.4.0` 会误走 `AutoProcessor`，BGE-M3 加载失败；已固定到本地验证过的 `sentence-transformers 5.2.3 / transformers 5.2.0 / huggingface-hub 1.5.0`。

建库 run：

`20260605_fin_agent_milvus_bge_m3_cloud_build_v0_2_local_model`

结果：`pass`

| 指标 | 结果 |
| --- | ---: |
| elapsed | 166.1s |
| embedding device | cuda |
| embedding model | `models/bge-m3-local` |
| evidence rows | 7,263 |
| object seed rows | 1,393 |
| total vector rows | 12,996 |
| narrative_chunk | 7,263 |
| table_chunk | 4,340 |
| metric_row | 848 |
| claim_object | 331 |
| table_row | 214 |
| tickers | 31 |
| years | 2025 / 2026 |

CUDA 探针：

- BGE-M3 一条 probe 输出维度 `1024`。
- 4090 识别正常。
- 编码/插入期间显存约 `3.1GB`，`embedding_batch_size=8` 没有 OOM。

Milvus 查询探针：

- 重新打开 Milvus Lite DB 后需要显式 `load_collection()`，否则 collection 处于 `released` 状态不能 search。
- 已在 runner 中补 `load_collection`。
- AI infra 查询能返回 NVDA / VRT 的 relationship / demand evidence，例如：
  - NVDA DGX Cloud / AI model infrastructure claim。
  - NVDA customer AI infrastructure buildout 需要 data centers、energy、capital 的风险/传导 evidence。
  - VRT 数据中心 power / thermal / infrastructure management demand claim。

本轮性质：

- 这是云端 `build-only + search probe`，不是完整 BM25/ObjectBM25/Milvus A/B。
- 下一步如果要正式比较质量，需要把 BM25/ObjectBM25 baseline 或等价远端索引路径接上，再跑 retrieval-only A/B；不能只凭 build-only 认为 Milvus 主线收益已成立。

## 2026-06-05 云端完整 baseline 重建与 A/B 进展

目标：不再上传本地 5GB+ SQLite / BM25 成品，而是在 4090 云端直接从 488MB evidence 重建 baseline，然后跑真实 BM25 / ObjectBM25 / Milvus / Hybrid A/B。

已验证的问题：

- 本地到云端 SSH/SFTP 上传只有约 `1.8-2.1 MiB/s`，传 5GB+ SQLite 成品不合算。
- 云端数据盘顺序写约 `103 MB/s`，瓶颈不是磁盘吞吐，而是跨机上传链路。
- 直接在 `/autodl-fs/data` 上用 SQLite WAL + FTS optimize 建 ObjectBM25，会在最后 `commit / WAL checkpoint / FTS optimize` 附近长时间进入 `D (disk sleep)`，进程卡在 `wait_on_page_bit_common`。
- 解决方式：ObjectBM25 的 SQLite 临时库放到 `/dev/shm`，使用 `journal_mode=MEMORY`、`synchronous=OFF`，并跳过最终 FTS optimize；成品 `records.sqlite` 再一次性复制回数据盘。

本地代码调整：

- `src/indexing/build_object_sqlite_fts_index.py`
  - 新增 `journal_mode`、`synchronous`、`optimize_fts` 参数。
  - 默认仍是 `WAL / NORMAL / optimize=true`，不影响主线默认行为。
- `scripts/data_retrieval/build_object_sqlite_fts_index.py`
  - 新增 CLI 参数：`--sqlite-journal-mode`、`--sqlite-synchronous`、`--skip-fts-optimize`。

云端 run：

`20260605_fin_agent_milvus_bge_m3_cloud_tmpfs_noopt_ab_v0_1`

已完成阶段：

| 阶段 | 结果 |
| --- | ---: |
| structured objects | 已从 full238 evidence 重建 |
| ObjectBM25 records | `3,139,066` |
| ObjectBM25 table / metric / claim | `105,106 / 2,394,547 / 639,413` |
| ObjectBM25 tmpfs build elapsed | `151.668s` |
| ObjectBM25 final DB size | `5.6GB` |
| ObjectBM25 smoke | `object_records=3,139,066`，FTS sample hit 正常 |
| BM25 records | `91,708` |
| BM25 final size | `724MB` |
| Milvus vector rows target | `12,996` |
| BGE-M3 CUDA | 已确认，4090 利用率曾到 `83%`，显存约 `3.1GB` |
| Milvus insert progress | 已确认到 `12,800 / 12,996` |

完整 A/B 结果：

第一次 full A/B run `20260605_fin_agent_milvus_bge_m3_cloud_tmpfs_noopt_ab_v0_1` 在 Milvus Lite 插入/flush/query 后退出但没有 summary，日志尾部只有 gRPC `too_many_pings`，没有 Python traceback。定位后认为问题不是 BGE 或数据缺失，而是 runner 长时间持有 Milvus gRPC 连接，期间还穿插 BM25 / ObjectBM25 的 CPU/SQLite 查询，Milvus Lite 会对空闲 keepalive 返回 `ENHANCE_YOUR_CALM`。

修复：

- runner 新增 `--reuse-milvus-db` / `--reuse-milvus-collection-name`，可复用已成功 build-only 的 Milvus Lite collection。
- full A/B 不再重复插入 12,996 条向量记录。
- 每个 case 的 semantic search 使用短连接：打开 MilvusClient、`load_collection`、search、关闭，再跑 BM25 / ObjectBM25。

最终 run：

`20260605_fin_agent_milvus_reuse_full12_v0_1`

结果：`pass`，`12/12` cases 通过。

| 类别 | 通过 |
| --- | ---: |
| exact lookup | 2/2 |
| sector-depth | 6/6 |
| relationship | 2/2 |
| paraphrase | 2/2 |

汇总：

| 指标 | 结果 |
| --- | ---: |
| mean BM25 usable rows | 19.50 |
| mean Milvus usable rows | 19.08 |
| mean Hybrid usable rows | 19.33 |
| BM25 index rows | 91,708 |
| ObjectBM25 rows | 3,139,066 |
| reused Milvus vector rows | 12,996 |

逐 case 结果：

| Case | BM25 | Milvus | Hybrid | Gate |
| --- | ---: | ---: | ---: | --- |
| retrieval_exact_msft_capex_2026 | 15 | 12 | 15 | pass |
| retrieval_exact_jpm_credit_provision_2026 | 19 | 19 | 19 | pass |
| retrieval_sector_ai_infra_demand_chain | 20 | 20 | 20 | pass |
| retrieval_sector_banking_rates_credit | 20 | 19 | 19 | pass |
| retrieval_sector_healthcare_product_cycle | 20 | 20 | 20 | pass |
| retrieval_sector_energy_cash_flow_capex | 20 | 19 | 20 | pass |
| retrieval_sector_utilities_power_load_regulated | 20 | 20 | 19 | pass |
| retrieval_relationship_cloud_capex_to_ai_suppliers | 20 | 20 | 20 | pass |
| retrieval_relationship_power_demand_to_utilities | 20 | 20 | 20 | pass |
| retrieval_paraphrase_ai_buildout_without_ticker_names | 20 | 20 | 20 | pass |
| retrieval_paraphrase_credit_cycle_without_bank_jargon | 20 | 20 | 20 | pass |
| retrieval_sector_consumer_demand_margin | 20 | 20 | 20 | pass |

工程结论：

- 云端重建 baseline 可行；ObjectBM25 不适合在网络数据盘上直接做 SQLite WAL + FTS optimize。
- `/dev/shm` 临时建库再复制成品，是当前云端环境下更稳的方式。
- BGE-M3 已真实走 CUDA，不是 CPU fallback。
- Milvus semantic-only / Hybrid 对 relationship、paraphrase、sector-depth 可作为补充召回，不应替代 BM25 / ObjectBM25。
- 本轮 Hybrid 没有显著超过 BM25，主要价值是证明不会拉低 exact lookup，并能为关系/改写类 query 提供语义补充；接入 full-chain 时仍需要 feature flag 和 mainline parity gate。

## 2026-06-05 Typed Vector Schema 与专用 Query 改写

目标：继续做 typed vector schema、query expansion、relationship/paraphrase 专用 query 改写，而不是简单扩大 top-k。

治理判断：

- 本轮是 retrieval-only 诊断，不代表 full-chain memo 质量已经提升。
- 允许推进的条件不是 Milvus top-k 更大，而是：
  - collection 有明确 typed metadata，可审计 evidence 来自什么语义视图。
  - relationship / paraphrase case 必须真实命中专用 semantic vector kind。
  - exact lookup 的 ObjectBM25 / metric row 命中不能下降。
  - Hybrid 仍保留 BM25 / ObjectBM25，不把 Milvus semantic-only 提升为替代路径。

代码调整：

- `scripts/eval_retrieval/eval_milvus_retrieval_ab.py`
  - schema version 升级到 `fin_agent_milvus_retrieval_ab_v0.3`。
  - Milvus collection 新增字段：`vector_role`、`semantic_scope`、`intent_tags`、`relationship_role`。
  - evidence chunk 新增两类专用向量视图：
    - `relationship_context`：用于经济联系、需求传导、上下游、客户/供应商、数据中心电力等关系检索。
    - `paraphrase_context`：用于把口语 query 映射到 SEC / 财务术语，比如 credit-cycle、AI buildout、capex、load growth。
  - Object 向量继续分为 `metric_row`、`table_row`、`claim_object`，并补 typed metadata。
  - `_expanded_queries` 从通用同义词扩展改为按 case category 分流：
    - `exact_lookup` 保留指标原词与 ticker 约束。
    - `relationship` 增加 economic linkage / demand transmission / upstream downstream / customer supplier 相关 rewrite。
    - `paraphrase` 增加 plain-language 到 canonical financial terms 的 rewrite。
  - Hybrid RRF 增加 typed balancing：
    - relationship 优先保留 `relationship_context`、`economic_linkage_context`、相关 `intent_tags`。
    - paraphrase 优先保留 `paraphrase_context`、`plain_language_context`、相关 `intent_tags`。
    - sector-depth 允许保留 relationship/paraphrase 辅助视图，但不替代 metric/table/object evidence。
  - eval 输出新增 `vector_role_counts`、`semantic_scope_counts`、`intent_tag_counts`、`relationship_role_counts`。
  - gate 新增 `required_semantic_vector_kind_hit`：relationship 默认要求 `relationship_context`，paraphrase 默认要求 `paraphrase_context`。
  - 修复 typed metadata 聚合 bug：Milvus raw hit 中的字符串字段先归一为 list 再追加，避免 `intent_tags` 字符串被当作 list 聚合。

测试夹具调整：

- `tests/fixtures/fin_agent_retrieval_ab_cases_v0_1.jsonl`
  - 2 个 relationship case 明确要求 `required_semantic_vector_kinds=["relationship_context"]`。
  - 2 个 paraphrase case 明确要求 `required_semantic_vector_kinds=["paraphrase_context"]`。

本地测试：

- `python -m compileall scripts/eval_retrieval/eval_milvus_retrieval_ab.py` -> pass
- `pytest tests/test_milvus_retrieval_ab_design.py tests/test_sec_chunk_id_uniqueness.py tests/test_sec_chunk_quality_audit.py -q` -> `11 passed`

云端 build-only run：

`20260605_fin_agent_milvus_typed_schema_query_v0_3_cloud_build_r0`

结果：`pass`

| 指标 | 结果 |
| --- | ---: |
| total vector rows | 23,093 |
| narrative_chunk | 7,263 |
| paraphrase_context | 6,792 |
| table_chunk | 4,340 |
| relationship_context | 3,305 |
| metric_row | 848 |
| claim_object | 331 |
| table_row | 214 |
| collection | `fin_ab_20260605_fin_agent_milvus_typed_schema_query_v0_3_cloud_build_r0_1780647929` |

云端 4-case smoke：

`20260605_fin_agent_milvus_typed_schema_query_v0_3_rel_para_smoke_r1`

结果：`pass`，relationship `2/2`，paraphrase `2/2`。

关键确认：

- `retrieval_relationship_cloud_capex_to_ai_suppliers`
  - Milvus semantic top rows 命中 `relationship_context=20`。
  - Hybrid 命中 `relationship_context=14`、`paraphrase_context=8`。
  - `required_semantic_vector_kind_hit=true`。
- `retrieval_relationship_power_demand_to_utilities`
  - Milvus semantic top rows 命中 `relationship_context=20`。
  - Hybrid 命中 `relationship_context=16`。
  - `required_semantic_vector_kind_hit=true`。
- `retrieval_paraphrase_ai_buildout_without_ticker_names`
  - Milvus semantic top rows 命中 `paraphrase_context=20`。
  - Hybrid 命中 `paraphrase_context=13`、`relationship_context=12`。
  - `required_semantic_vector_kind_hit=true`。
- `retrieval_paraphrase_credit_cycle_without_bank_jargon`
  - Milvus semantic top rows 命中 `paraphrase_context=20`。
  - Hybrid 命中 `paraphrase_context=16`。
  - `required_semantic_vector_kind_hit=true`。

云端 12-case full retrieval-only A/B：

`20260605_fin_agent_milvus_typed_schema_query_v0_3_full12_r0`

结果：`pass`，`12/12`。

| 类别 | 通过 |
| --- | ---: |
| exact lookup | 2/2 |
| sector-depth | 6/6 |
| relationship | 2/2 |
| paraphrase | 2/2 |

汇总：

| 指标 | 结果 |
| --- | ---: |
| mean BM25 usable rows | 19.50 |
| mean Milvus usable rows | 18.9167 |
| mean Hybrid usable rows | 19.5833 |
| failed cases | 0 |

逐类观察：

- exact lookup：2 个 case 都通过，Hybrid 保留 `metric_row/table_row/table_chunk`，没有因为语义视图扩展破坏 exact metric gate。
- relationship：2 个 case 都通过新 gate，Hybrid 明确命中 `relationship_context`，说明关系类不再只靠 BM25 文本词命中。
- paraphrase：2 个 case 都通过新 gate，Hybrid 明确命中 `paraphrase_context`，说明口语 query 到 SEC/财务术语的桥接已进入检索结果。
- sector-depth：6 个 case 全部通过，relationship/paraphrase context 作为补充视图出现，有助于给 Specialist 提供更接近“研究假设/经济传导”的上下文。

限制：

- Milvus Lite 在进程结束阶段仍偶发 gRPC `too_many_pings` warning，但本轮 run 返回码为 0，summary 完整；当前仍只建议作为诊断/实验路径。
- `paraphrase_context` 与 `relationship_context` 是从已有 evidence 文本和规则触发词构造的语义视图，不是外部真实客户/供应商图谱。
- 对 full-chain 的价值还需要下一步接入 Specialist layer 后验证：真实 context rows 是否进入 prompt、ClaimCard 密度是否提高、memo 是否更像投研报告。

## 验证

- `pytest tests/test_sec_chunk_id_uniqueness.py tests/test_sec_chunk_quality_audit.py -q` -> `4 passed`
- `pytest tests/test_sec_agent_10q_source_contract.py tests/test_sec_agent_8k_earnings_source.py -q` -> `80 passed`
- `python -m compileall src/ingestion/parse_sec_filing.py scripts/eval_retrieval/audit_sec_chunk_quality.py` -> pass
- `python scripts/eval_retrieval/audit_sec_chunk_quality.py --run-id 20260604_sec_chunk_quality_full238_v0_3 --strict` -> fail by S0 hard gate, expected diagnostic result
- `python -m compileall scripts/eval_retrieval/eval_milvus_retrieval_ab.py` -> pass
- `python scripts/eval_retrieval/audit_sec_chunk_quality.py --run-id 20260604_sec_chunk_quality_full238_v0_5_parser_item_s0_v0_1 --strict` -> pass
- `python scripts/eval_retrieval/eval_milvus_retrieval_ab.py --run-id 20260604_fin_agent_milvus_retrieval_ab_full238_v0_3_balanced_rrf ...` -> pass，`12/12`
- `pytest tests/test_milvus_retrieval_ab_design.py tests/test_sec_chunk_id_uniqueness.py tests/test_sec_chunk_quality_audit.py -q` -> `8 passed`
- 云端 `python scripts/eval_retrieval/eval_milvus_retrieval_ab.py --milvus-build-only --embedding-model models/bge-m3-local --device cuda ...` -> pass，`12,996` vector rows
- 云端 Milvus search probe -> pass，重新打开 DB 后 `load_collection()` 可返回 NVDA / VRT AI infra evidence
- 云端 tmpfs ObjectBM25 rebuild -> pass，`3,139,066` object rows，`151.668s`
- 云端 BM25 rebuild -> pass，`91,708` evidence rows
- 云端 2-case Milvus reuse smoke -> pass，exact lookup + AI infra sector-depth `2/2`
- 云端 12-case Milvus reuse full A/B -> pass，`12/12`
- `python -m compileall scripts/eval_retrieval/eval_milvus_retrieval_ab.py` -> pass，v0.3 typed schema/query rewrite
- `pytest tests/test_milvus_retrieval_ab_design.py tests/test_sec_chunk_id_uniqueness.py tests/test_sec_chunk_quality_audit.py -q` -> `11 passed`
- 云端 v0.3 typed schema build-only -> pass，`23,093` vector rows，其中 `relationship_context=3,305`、`paraphrase_context=6,792`
- 云端 v0.3 relationship/paraphrase 4-case smoke -> pass，`4/4`，typed semantic vector gate 全部通过
- 云端 v0.3 12-case full retrieval-only A/B -> pass，`12/12`

## 后续

- Milvus 不进入主线替代 BM25；如接入 full-chain，只能作为 `SEC_AGENT_MILVUS_HYBRID_RECALL` 这类 feature flag 后的实验路径。
- 接入时必须保留 BM25/ObjectBM25/exact-value ledger，并沿用 ticker-balanced Hybrid RRF，不能使用 semantic-only。
- 接入 full-chain 前，先做 S3 retrieval-only mainline parity：sector-depth / relationship / paraphrase 不低于 BM25 usable rows，exact lookup ledger hit 不下降，延迟预算单独记录。
- 对剩余 6 个 primary filing core item gap 做 parser 维护，避免未来行业覆盖扩展时被放大。
- 下一步如果要接入主链路，需要把 `relationship_context/paraphrase_context` 映射成 Specialist 可见的 context row 字段，并给 runtime ledger 增加 typed evidence counters，不能只把 Milvus summary 留在离线 eval。
