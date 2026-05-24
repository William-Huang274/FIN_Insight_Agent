# Phase 1 Foundation Worklog

## 2026-05-15 Repository Initialization

Problem or prompt:
Start Phase 1 by creating the project skeleton, setting up Git main/feature
branches, and testing SEC data download feasibility.

Reasoning and decision:
Keep the first implementation focused on SEC filings and evidence retrieval.
Use a private local cache for SEC downloads and generated indexes. Avoid
starting the full agent workflow until retrieval can be evaluated.

Work completed:
- Initialized local Git repository on `main`.
- Added a data-safety `.gitignore` baseline on `main`.
- Created feature branch `feature/phase1-sec-foundation`.
- Added Phase 1 repository skeleton, config files, and worklog scaffold.

Result and evidence:
- Repository is now on `feature/phase1-sec-foundation`.
- EvidenceObject JSONL smoke test wrote and read
  `JPM_2024_10K_ITEM7_CHUNK_0001`.
- SEC smoke test downloaded JPM 2024 10-K:
  - CIK: `0000019617`
  - Report date: `2024-12-31`
  - Filing date: `2025-02-14`
  - Accession: `0000019617-25-000270`
  - Primary document: `jpm-20241231.htm`
  - Local cache: `data/raw_private/sec/JPM/2024/10-K.html`
- Important connector finding: JPM 2024 10-K was not present in the
  `filings.recent` block because SEC had moved it into historical submission
  files. The connector now searches `filings.files` when recent filings do not
  contain the target report year.

Follow-up and safety notes:
- Generated private data remains under `data/raw_private/`,
  `data/processed_private/`, and `data/indexes/`, which are ignored by Git.

## 2026-05-15 SEC Candidate Universe Scan

Problem or prompt:
Assess whether using 2023-2025 SEC filings for Nasdaq technology companies is
feasible for the next data collection step.

Reasoning and decision:
Use SEC 10-K metadata availability as the first feasibility gate before
downloading many large HTML filings. Interpret 2023-2025 by fiscal/report year,
not filing calendar year, because calendar-year companies file FY2025 reports
in early 2026.

Work completed:
- Scanned 10-K metadata for 22 tickers across fiscal years 2023, 2024, and
  2025: `MSFT`, `AAPL`, `NVDA`, `GOOGL`, `META`, `AMZN`, `AVGO`, `ADBE`,
  `CSCO`, `INTC`, `AMD`, `QCOM`, `TXN`, `AMAT`, `MU`, `INTU`, `ADP`, `PANW`,
  `CRWD`, `MDB`, `SNOW`, and `TEAM`.

Result and evidence:
- All 66 ticker-year combinations were found in SEC metadata.
- The scan used metadata lookup only and did not download all filing HTMLs.
- This supports a Phase 1 data scope of a small, sector-diverse Nasdaq tech
  sample before scaling to the full candidate list.

Follow-up and safety notes:
- Recommended first download batch: 8-10 companies across software, internet,
  semiconductors, hardware, cloud, and cybersecurity.
- Keep the first retrieval benchmark smaller than the full 22-company universe
  until parsing and evaluation are stable.

## 2026-05-15 SEC Cache Layout And First Tech Batch

Problem or prompt:
Organize downloaded SEC filings by fiscal year and business category so the
raw data layout supports later category-level retrieval comparisons.

Reasoning and decision:
Use `data/raw_private/sec/<year>/<category_slug>/<ticker>/<form>.html`.
Keep the human-readable category in filing metadata, and use filesystem-safe
slugs for folder names because category labels may contain `/`.

Work completed:
- Added `configs/sec_tech_universe.yaml` with the first 10-company technology
  universe:
  `MSFT`, `AAPL`, `NVDA`, `GOOGL`, `META`, `AMZN`, `AMD`, `ADBE`, `PANW`,
  and `SNOW`.
- Updated the SEC connector cache layout to `year/category/ticker`.
- Added `scripts/download_sec_filings.py` for configured batch downloads.
- Downloaded 30 filings: 10 companies across fiscal years 2023, 2024, and
  2025.

Result and evidence:
- Tech universe raw HTML count: 30.
- Tech universe raw HTML size: 87,434,064 bytes.
- Example path:
  `data/raw_private/sec/2024/mega-cap_software_cloud/MSFT/10-K.html`.
- JPM smoke test also works with the new default uncategorized layout:
  `data/raw_private/sec/2024/uncategorized/JPM/10-K.html`.

Follow-up and safety notes:
- Raw SEC HTML and metadata remain ignored under `data/raw_private/`.
- The earlier JPM banking smoke-test cache under the old layout is harmless
  local generated data and is not part of the tech universe benchmark.

## 2026-05-15 SEC Manifest Builder

Problem or prompt:
Create a stable traversal layer so downstream parsers do not need to scan the
raw SEC folder structure directly.

Reasoning and decision:
Build a JSONL manifest from metadata sidecars using the order
`year -> category_slug -> ticker -> *.metadata.json -> matching HTML`. The
manifest is filtered by `configs/sec_tech_universe.yaml` by default so the JPM
smoke-test filing does not enter the tech benchmark.

Work completed:
- Added `src/connectors/sec_filing_manifest.py`.
- Added `scripts/build_sec_manifest.py`.
- Generated
  `data/processed_private/manifests/sec_tech_10k_manifest.jsonl`.

Result and evidence:
- Manifest record count: 30.
- Years: 2023, 2024, 2025.
- Tickers: `AAPL`, `ADBE`, `AMD`, `AMZN`, `GOOGL`, `META`, `MSFT`, `NVDA`,
  `PANW`, and `SNOW`.
- Filter smoke test for 2024 `MSFT` and `NVDA` returned 2 records.

Follow-up and safety notes:
- The manifest is generated under `data/processed_private/`, which is ignored
  by Git.
- The next parser should read this manifest rather than globbing raw HTML
  files directly.

## 2026-05-15 SEC Parser And Chunk Builder

Problem or prompt:
Implement SEC filing parsing and section-aware chunking for the downloaded
10-K HTML filings.

Reasoning and decision:
Use a conservative parser before building retrieval indexes. Extract visible
HTML text, detect 10-K `Item` sections from cleaned line spans, filter out table
of contents entries by requiring an actual Item 1 body span, and emit only the
Phase 1 target sections: Item 1, Item 1A, Item 7, Item 7A, and Item 8.

Work completed:
- Added `src/ingestion/parse_sec_filing.py`.
- Added `src/ingestion/section_splitter.py`.
- Added `scripts/build_sec_chunks.py`.
- Built a small smoke output for 2024 `MSFT` and `NVDA`.
- Built full tech-universe chunks from 30 filings.

Result and evidence:
- `python -m compileall src scripts` passed.
- Smoke test for 2024 `MSFT` and `NVDA` produced 102 chunks:
  - Item 1: 23
  - Item 1A: 35
  - Item 7: 18
  - Item 7A: 2
  - Item 8: 24
- Full tech-universe run produced 1,829 chunks from 30 filings:
  - Item 1: 255
  - Item 1A: 592
  - Item 7: 290
  - Item 7A: 44
  - Item 8: 648
- Chunk word count summary for the full run:
  - Minimum: 32
  - Median: 925
  - Maximum: 1,630
- Output path:
  `data/processed_private/chunks/sec_tech_10k_chunks.jsonl`.

Follow-up and safety notes:
- Generated chunk JSONL is under `data/processed_private/` and is ignored by
  Git.
- Some companies, such as NVDA, use Item 8 as a short cross-reference to
  consolidated financial statements elsewhere in the filing. The parser keeps
  that short Item 8 record instead of inventing a different citation boundary.
- Next step should convert chunks into `EvidenceObject` records and then build
  the BM25 retrieval baseline.

## 2026-05-15 Semantic Block-Aware Chunking Update

Problem or prompt:
Avoid arbitrary chunk splitting that cuts financial business language apart.
When long same-section content must be split, preserve the larger business
block and section context on every part.

Reasoning and decision:
Use SEC Item sections as hard boundaries, then identify semantic blocks inside
each Item from business headings, risk headings, MD&A headings, market-risk
headings, and financial statement/note headings. Split only when a semantic
block exceeds the target retrieval size, and label every split with the same
`block_id`, `block_heading`, `block_type`, `block_part_index`, and
`block_part_count`.

Work completed:
- Added `SecSemanticBlock`.
- Extended `SecFilingChunk` with parent block and part fields.
- Updated chunk IDs from section-only chunks to block-aware IDs such as
  `MSFT_2024_10K_ITEM7_BLOCK_0008_PART_01_OF_02`.
- Tightened Item 8 heading rules so normal table rows are less likely to
  become standalone semantic blocks.

Result and evidence:
- Smoke test for 2024 `MSFT` and `NVDA` produced:
  - 174 chunks
  - 133 semantic blocks
  - 22 split blocks
- Full tech-universe run produced:
  - 2,919 chunks
  - 2,088 semantic blocks
  - 460 split blocks
- Full run section chunk counts:
  - Item 1: 420
  - Item 1A: 989
  - Item 7: 570
  - Item 7A: 51
  - Item 8: 889
- Full run word count summary:
  - Minimum: 32
  - Median: 448
  - Maximum: 1,683

Follow-up and safety notes:
- Chunk length is now a secondary constraint after semantic boundary
  preservation.
- Some short chunks remain by design where the original filing uses a short
  cross-reference or a concise business heading.
- EvidenceObject builder should map `block_heading` to `subsection` and carry
  the block/part fields in metadata.

## 2026-05-15 Table-Aware Chunking Update

Problem or prompt:
Prevent financial tables from being flattened into ordinary paragraph lines and
split apart during SEC chunking.

Reasoning and decision:
Serialize each HTML `<table>` into an atomic text block before section and
chunk processing. Use `TABLE_START` and `TABLE_END` markers so the chunker can
keep the table header, units, period labels, and rows together. If a block with
tables still exceeds the target retrieval size, split only between paragraphs
or complete table blocks, never inside a table marker pair.

Work completed:
- Updated `extract_sec_html_text` to replace HTML tables with serialized table
  blocks.
- Updated paragraph extraction to treat `TABLE_START ... TABLE_END` as one
  indivisible paragraph.
- Added `contains_table` to `SecFilingChunk`.
- Updated chunk summaries to report `table_blocks`.
- Adjusted section boundary detection so Item headings embedded in one-row SEC
  heading tables start at `TABLE_START`, avoiding broken table markers.

Result and evidence:
- Full tech-universe chunk build produced:
  - 2,842 chunks
  - 1,894 semantic blocks
  - 485 split blocks
  - 598 table-bearing blocks
- Table-bearing chunk count: 982.
- Table marker integrity check found 0 chunks with unmatched `TABLE_START` or
  `TABLE_END`.
- Maximum table-bearing chunk length: 1,765 words.

Follow-up and safety notes:
- Table blocks are preserved for retrieval and citation, but this is not yet a
  full structured table extraction layer. Later numeric extraction should add
  a dedicated table object/table index rather than relying only on text
  serialization.

## 2026-05-15 Evidence Store, BM25, And Dense Retrieval Smoke

Problem or prompt:
在 table-aware chunk 基础上，先把 chunks 统一转换成 EvidenceObject，然后试跑
BM25 和 dense retrieval，验证当前 10-K 语义切分是否能支持基本检索。

Reasoning and decision:
先不进入 hybrid/RRF 或 agent workflow。用 EvidenceObject 作为唯一检索输入，
这样 BM25、dense、后续 reranker 和 citation 都共享同一套 schema。dense 先用
`sentence-transformers/all-MiniLM-L6-v2` 做小模型烟测，目标是验证端到端可行性，
不是最终金融检索模型选择。

Work completed:
- Added SEC chunk to EvidenceObject conversion.
- Added BM25 index builder and retriever.
- Added dense numpy cosine index builder and retriever.
- Added CLI smoke scripts for building and querying both retrieval baselines.
- Synced code and processed SEC data to the cloud workspace
  `/root/autodl-tmp/FIN_Insight_Agent`.

Result and evidence:
- `python -m compileall src scripts` passed locally and on cloud.
- EvidenceObject build:
  - Input chunks: 2,842.
  - EvidenceObjects: 2,842.
  - Table-bearing evidence: 982.
  - Evidence types:
    `business_description` 423, `risk_disclosure` 989,
    `management_discussion` 524, `market_risk_disclosure` 47,
    `financial_statement_or_note` 859.
- BM25 smoke:
  - MSFT 2024 cloud revenue query top hit:
    `MSFT_2024_10K_ITEM7_BLOCK_0003_CHUNK_0001`, MD&A highlights, with
    Microsoft Cloud revenue growth.
  - NVDA 2025 supply/customer concentration query top hits included
    `NVDA_2025_10K_ITEM7_BLOCK_0007_CHUNK_0001` and
    `NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_01_OF_03`.
- Dense smoke on cloud:
  - GPU: NVIDIA GeForce RTX 4090.
  - Model: `sentence-transformers/all-MiniLM-L6-v2`.
  - Embedding dim: 384.
  - Records: 2,842.
  - Dense index size: about 18.2 MB.
  - Build elapsed: about 51.5 seconds after using the Hugging Face mirror
    endpoint.
  - MSFT 2024 cloud revenue dense top hit matched the BM25 top hit.
  - NVDA 2025 dense top hits included customer concentration and supply-chain
    risk evidence.

Follow-up and safety notes:
- Direct `huggingface.co` access from the cloud host timed out; setting
  `HF_ENDPOINT=https://hf-mirror.com` made model download work.
- Current dense CLI reloads the embedding model per query, so query scripts are
  acceptable for smoke tests but not for interactive evaluation. Add an
  in-process retrieval runner/API before larger query sets.
- This is retrieval feasibility evidence only. It does not yet prove final
  retrieval quality because there is no gold query set or evaluation metric.

## 2026-05-15 Seed Retrieval Evaluation

Problem or prompt:
对当前 BM25/dense 召回效果做一个可重复的评估，而不是只看两条手写 smoke query。

Reasoning and decision:
先建立一个小型 seed gold set：30 条公司/年份明确的问题，每条标注 1-2 个
current EvidenceObject IDs。这个集合用于诊断召回链路，不作为最终人工 benchmark。
同时比较两种检索场景：ticker/year 已由上游 agent 识别后的 filtered 检索，以及
不带 metadata filter 的全库检索。

Work completed:
- Added `eval_sets/sec_tech_10k_seed.jsonl`.
- Added retrieval evaluation utilities and `scripts/evaluate_retrieval.py`.
- Added hybrid RRF retriever and `scripts/search_hybrid.py`.
- Ran cloud evaluation for BM25, dense MiniLM, and hybrid RRF.
- Saved detailed JSON reports under `reports/retrieval_eval/`.

Result and evidence:
- Filtered mode, using ticker/year from the gold query:
  - BM25: MRR 0.568, Hit@5 0.833, Hit@10 0.867, Mean Recall@10 0.833.
  - Dense MiniLM: MRR 0.628, Hit@5 0.833, Hit@10 0.867, Mean Recall@10 0.833.
  - Hybrid RRF: MRR 0.701, Hit@5 0.867, Hit@10 1.000, Mean Recall@10 0.950.
- Unfiltered full-corpus mode:
  - BM25: MRR 0.325, Hit@5 0.600, Hit@10 0.733, Mean Recall@10 0.700.
  - Dense MiniLM: MRR 0.462, Hit@5 0.633, Hit@10 0.733, Mean Recall@10 0.683.
  - Hybrid RRF: MRR 0.521, Hit@5 0.700, Hit@10 0.733, Mean Recall@10 0.667.
- Main report:
  `reports/retrieval_eval/sec_tech_10k_seed_eval_summary.md`.

Follow-up and safety notes:
- Hybrid RRF is the best current baseline when ticker/year filters are applied.
- Full-corpus retrieval is materially weaker, so company/year parsing and
  query routing should be treated as first-class retrieval components.
- The seed set must be human-reviewed and expanded before making final quality
  claims.

## 2026-05-15 ModelScope Qwen Embedding Evaluation

Problem or prompt:
用户希望试用 Qwen 系 embedding，并要求从魔塔社区下载模型。

Reasoning and decision:
未使用生成式 Qwen3.5 foundation model 直接做 embedding；本次选择 ModelScope 上的
`Qwen/Qwen3-Embedding-0.6B` 作为 Qwen 系官方 embedding 模型。为了不低估
Qwen embedding，对 query 编码启用模型自带的 `query` prompt，并将文档最大长度
设为 4096。

Work completed:
- Added ModelScope download script.
- Added dense index metadata support for `query_prompt_name` and
  `max_seq_length`.
- Downloaded Qwen3-Embedding-0.6B to ignored private model cache.
- Built `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b/`.
- Evaluated dense Qwen and Qwen+BM25 RRF on filtered and unfiltered seed sets.

Result and evidence:
- Model cache size: about 1.2 GB.
- Index build elapsed: about 86.5 seconds.
- Dense index size: about 26 MB.
- Embedding dimension: 1024.
- Filtered dense Qwen: MRR 0.709, Hit@5 0.867, Hit@10 0.933,
  Mean Recall@10 0.917.
- Filtered hybrid RRF + Qwen: MRR 0.640, Hit@5 0.867, Hit@10 0.967,
  Mean Recall@10 0.950.
- Unfiltered dense Qwen: MRR 0.634, Hit@5 0.833, Hit@10 0.900,
  Mean Recall@10 0.867.
- Unfiltered hybrid RRF + Qwen: MRR 0.519, Hit@5 0.767, Hit@10 0.867,
  Mean Recall@10 0.833.

Follow-up and safety notes:
- Qwen dense is now the best dense baseline and strongly improves full-corpus
  retrieval over MiniLM.
- Simple equal-weight RRF can hurt Qwen's ranking, so the next hybrid iteration
  should test weighted RRF or dense-first retrieval with BM25 fallback.
- Model weights remain ignored under `data/models_private/`.

## 2026-05-15 Retrieval Metric And Qwen Batch Probe

Problem or prompt:
用户要求除了 Hit 以外补充 nDCG 和 Precision，检查是否召回不相关内容、真值是否
排在前面，并说明当前真值是怎么判断的。同时建议利用 4090 显存调大 Qwen 的
max length 和 batch size。

Reasoning and decision:
把 `precision@k` 和 `nDCG@k` 加到 evaluation code 和 JSON 报告里。对当前 seed
set 明确标注：这些真值是从当前 EvidenceObject store 中由 agent 选出的直接回答
问题的 evidence IDs，不是穷尽人工 relevance labels。因此 precision 只能解释为
对 seed qrels 的命中比例，不能直接等同于真实不相关率。

Work completed:
- Updated retrieval evaluation to emit per-query and summary
  `precision@k` / `nDCG@k`.
- Re-ran MiniLM BM25/dense/hybrid evaluation on cloud.
- Rebuilt Qwen dense index with `max_seq_length=8192` and batch sizes 16/32.
- Re-ran Qwen seq8192 dense and hybrid evaluation.
- Pulled updated eval reports and runtime JSON back to the local repo.

Result and evidence:
- Current Qwen tokenizer length over 2,842 EvidenceObjects:
  - Median: 791 tokens.
  - P95: 1,742 tokens.
  - Maximum: 3,536 tokens.
  - Over 4,096 tokens: 0.
- Filtered mode:
  - Dense Qwen seq8192: MRR 0.716, Hit@10 0.933, Precision@10 0.117,
    nDCG@10 0.747.
  - Hybrid RRF + Qwen seq8192: MRR 0.649, Hit@10 0.967,
    Precision@10 0.123, nDCG@10 0.711.
- Unfiltered mode:
  - Dense Qwen seq8192: MRR 0.652, Hit@10 0.900, Precision@10 0.110,
    nDCG@10 0.689.
  - Hybrid RRF + Qwen seq8192: MRR 0.541, Hit@10 0.867,
    Precision@10 0.107, nDCG@10 0.595.
- Runtime:
  - seq8192 batch 16: 96.76 seconds, 8.984 GB peak CUDA allocated.
  - seq8192 batch 32: 105.67 seconds, 16.700 GB peak CUDA allocated.

Follow-up and safety notes:
- Qwen dense should remain the main dense baseline for now.
- Equal-weight RRF can increase Hit@10 while hurting MRR/nDCG, so the next
  retrieval experiment should test weighted RRF or dense-first retrieval with
  BM25 fallback.
- Larger `max_seq_length=8192` is not needed for the current corpus because no
  current evidence text exceeds 4,096 Qwen tokens.
- No credentials or private connection details were written to repo logs.

## 2026-05-15 Complex Finance Query Retrieval Probe

Problem or prompt:
用户要求围绕当前 10 家公司的常见金融问题和更深的金融分析问题直接查询 top5
evidence，用人工检查判断当前 retrieval 指标是否真正有价值。

Reasoning and decision:
使用云端已构建的 Qwen3-Embedding-0.6B seq8192 batch16 dense index 作为主检索器，
并同时检查 equal-weight BM25+dense RRF。每个问题同时保存 filtered top5 和
unfiltered top5：filtered 模拟上游 agent 已识别 ticker/year 的场景，unfiltered
用于暴露错公司/错年份漂移。

Work completed:
- 设计并执行 12 条复杂查询：
  - 常见金融问题：云收入、iPhone/Services、数据中心收入、AWS margin/capex、
    广告收入/AI capex、广告/cloud/capex。
  - 深度金融问题：ARR/RPO、consumption/RPO/customer metrics、platformization
    /billings/RPO、segment mix/margin/inventory、supply-chain/customer risk、
    liquidity/leases/commitments。
- 保存 raw top5 JSON 和人工检查报告。
- 建立对应 model run ledger。

Result and evidence:
- Probe runtime: 19.209 seconds after model load.
- Unfiltered dense top5 中，目标 ticker/year 命中 41/60；说明 metadata filter
  仍然是必须组件，不是可选优化。
- Filtered top5 的人工判断：
  - Good: MSFT cloud/AI margin, AAPL iPhone/Services margin, SNOW
    consumption/RPO/customer metrics, AMD segment/margin/inventory, and NVIDIA
    supply/customer risk with hybrid.
  - Partial: AMZN AWS/capex, META ads/AI capex, GOOGL ads/cloud/capex, ADBE
    ARR/RPO, AMZN liquidity/leases/commitments.
  - Weak: PANW platformization/billings/RPO.
- Raw report:
  `reports/retrieval_eval/sec_tech_10k_complex_query_probe.md`.

Follow-up and safety notes:
- 当前 seed metrics 有价值，但只能说明已知 evidence IDs 的排序，不足以证明
  深度金融问题的多 facet 覆盖。
- 下一步应把这类复杂问题转成 reviewed qrels，并实现 query decomposition 或
  facet-aware retrieval；在此之前不建议直接上 reranker。
- No credentials or private connection details were written to repo logs.

## 2026-05-15 Complex Multi-Facet Retrieval Evaluation

Problem or prompt:
用户要求把复杂问题做成多 facet qrels，并实现 query decomposition 或 facet-aware
retrieval，检查相对 dense/hybrid baseline 的效果。

Reasoning and decision:
先把上一轮 12 条复杂金融问题拆成可评估的 qrels：每条复杂 query 包含 3 个
facet，每个 facet 标注当前 EvidenceObject store 中可直接支撑该 facet 的 evidence
IDs。为了验证 decomposition 本身和融合策略的差异，同时测试 naive RRF 和
facet-first round-robin 两种融合方式。

Work completed:
- Added `eval_sets/sec_tech_10k_complex_multifacet.jsonl` with 12 complex
  queries and 36 facet labels.
- Added multi-facet evaluation metrics:
  `facet_coverage@k`, `all_facets_hit@k`, and `facet_mrr`.
- Added facet-aware retrieval utilities with RRF and round-robin fusion.
- Added `scripts/evaluate_multifacet_retrieval.py`.
- Ran local BM25 diagnostic and cloud Qwen filtered/unfiltered evaluations.

Result and evidence:
- Filtered Qwen results:
  - `dense`: nDCG@10 0.766, FacetCov@10 0.833, AllFacets@10 0.583.
  - `hybrid`: nDCG@10 0.794, FacetCov@10 0.889, AllFacets@10 0.667.
  - `facet_dense RRF`: nDCG@10 0.689, FacetCov@10 0.806,
    AllFacets@10 0.417.
  - `facet_hybrid RRF`: nDCG@10 0.679, FacetCov@10 0.778,
    AllFacets@10 0.417.
  - `facet_dense_rr`: nDCG@10 0.852, FacetCov@10 0.889,
    AllFacets@10 0.667.
  - `facet_hybrid_rr`: nDCG@10 0.853, FacetCov@10 0.917,
    AllFacets@10 0.750.
- Unfiltered Qwen results:
  - `dense`: nDCG@10 0.674, FacetCov@10 0.806, AllFacets@10 0.500.
  - `facet_dense_rr`: nDCG@10 0.743, FacetCov@5 0.750,
    AllFacets@10 0.417.
- Summary report:
  `reports/retrieval_eval/sec_tech_10k_complex_multifacet_eval_summary.md`.

Follow-up and safety notes:
- 当前 multi-facet qrels 是 agent-authored diagnostic labels，不是最终人工
  reviewed benchmark；precision 只能解释为命中当前 gold IDs 的比例。
- Query decomposition 有价值，但 naive RRF 会把 facet query 的候选冲散；
  facet-first round-robin 更符合多维金融问题的证据覆盖目标。
- Ticker/year routing 仍然是必须组件。全库无过滤检索下，dense baseline 更稳，
  hybrid RRF 噪声更明显。
- 下一步应做人审 multi-facet qrels，再测试 automatic decomposition、dense-first
  BM25 fallback 或 reranker。

## 2026-05-15 Qwen3.5 27B GPTQ Serving Diagnostic

Problem or prompt:
用户要求先不要设置 fallback，排查当前 Qwen3.5 27B 4bit 量化版本为什么输出慢，
以及是否误用了 CPU 推理。

Reasoning and decision:
停止继续跑业务 demo，转为最小 vLLM serving benchmark。重点检查模型配置、
vLLM device、CPU offload、GPU 利用率、首轮/第二轮短输出 token/s，并验证
`enforce_eager` 是否是主因。

Work completed:
- 确认云端无残留进程和显存占用。
- 检查 `Qwen/Qwen3.5-27B-GPTQ-Int4` 的 `config.json`。
- 分别测试 `offload=14GB`、`offload=10GB`、`offload=6GB` 和
  `offload=10GB + CUDA graph/torch compile`。
- 建立 model run ledger:
  `reports/model_runs/20260515_phase1_qwen35_27b_gptq_serving_diagnostic.md`。

Result and evidence:
- 不是 CPU-only 推理。vLLM 日志显示 `device_config=cuda`，使用
  `gptq_marlin` 和 FlashAttention；生成时 GPU memory 约 21.4GB，GPU util
  100%。
- 当前模型不是理想的纯文本 planner。配置包含 `vision_config`、image/video
  token，vLLM profiling 进入 `qwen3_vl.py`、`embed_multimodal`、`visual`。
- `offload=14GB` 第二轮短输出约 0.71 tok/s。
- `offload=10GB` 第二轮短输出约 0.97 tok/s。
- `offload=6GB` 即使 `max_model_len=2048` 也在 multimodal profiling 阶段 OOM。
- 关闭 `enforce_eager` 后 cold start 增加到约 360s，第二轮仍约 0.93 tok/s，
  不是主要瓶颈。

Follow-up and safety notes:
- 当前 artifact 标记为 `diagnostic-only`，不继续作为 planner/summarizer demo
  主线。
- 下一步应换纯文本 quantized instruct 模型；进入业务链路前先通过 serving gate：
  无 `vision_config`、无 multimodal profiling、尽量 `cpu_offload_gb=0`，短 JSON
  第二轮生成至少达到数 tok/s。
- 不推广被 fallback 兜底生成的业务 demo 结果。

## 2026-05-15 Qwen3.5 9B Resident Full-Chain Demo

Problem or prompt:
用户要求改用 Qwen3.5-9B 常驻在当前 4090 云端上，把 planner 到总结阶段的
全链路 demo 跑通，并用日常任务、综合研究、深度推理三类 query 检查实际效果。

Reasoning and decision:
27B GPTQ 在 4090 24GB 上必须 CPU offload，不能作为交互式主线。9B 权重约
18GB，vLLM 可用 `language_model_only=True` 和 `skip_mm_profiling=True`
进入 text-only 路径，因此先作为当前单卡主线 demo。实验不启用 planner
fallback，避免把兜底 query 当成 decomposition 效果。

Work completed:
- 将 demo 脚本泛化为 `scripts/run_qwen_planner_evidence_demo.py`。
- 默认模型改为 `Qwen/Qwen3.5-9B`，默认 `cpu_offload_gb=0`、
  `gpu_memory_utilization=0.86`、`planner_max_tokens=1024`。
- 增加 `language_model_only`、`skip_mm_profiling`、`allow_fallback_planner`
  参数；默认不允许 planner fallback。
- 在云端用 hybrid retrieval、CPU dense query encoder、batched verifier 跑完
  三类 query。
- 建立 model run ledger:
  `reports/model_runs/20260515_phase1_qwen35_9b_full_chain_demo.md`。

Result and evidence:
- 9B serving gate 通过：vLLM 日志显示 `device_config=cuda`、text-only mode、
  无 CPU offload；`gpu_memory_utilization=0.86` 下 KV cache 约 59,068 tokens。
- 第一次 `gpu_memory_utilization=0.92` 因云端另一个进程占用约 1.75GB 显存而
  启动失败；降到 0.86 后成功。
- 第一次 `planner_max_tokens=512` 三题都因 JSON 截断解析失败；改成 compact
  JSON prompt 和 1024 tokens 后三题 planner 均解析成功。
- v2 总 wall time 约 286.9s，其中 resident model load 约 90.1s；三题链路
  分别约 58.5s、61.9s、62.6s。
- Planner 生成 12 个 SearchTask；24 个候选经 verifier 标注为 8 direct、
  14 partial、2 false。
- 12 个 task pack 中 7 个找到 direct evidence，5 个只有 partial/no direct。
- Apple 日常 query evidence quality 为 `good`；Microsoft/Alphabet 综合研究
  和 NVIDIA 深度推理均为 `mixed`，主要瓶颈是部分 facet top-2 候选没有直接证据。

Follow-up and safety notes:
- 该 run 标记为 `diagnostic-only`；model verifier 标签和最终答案不能当作人工
  评测结论。
- 当前主要瓶颈从 serving 可行性转为 evidence coverage：Alphabet cloud/capex、
  NVIDIA CSP demand 等 facet 需要更深的 per-task retrieval/verification 或更强
  reranker。
- 下一步优先做 structured decoding/guided JSON，避免 planner/verifier 格式不稳；
  同时对 missing-direct task 自适应扩大候选和上下文扩展。

## 2026-05-16 Qwen3.5 9B Evidence-Pack Hardening V3-V6

Problem or prompt:
用户要求继续推进 9B 常驻 planner-to-synthesis demo，检查 planner、解析、召回、
verifier、最终总结链路的实际表现，并继续改善复杂金融问题的 evidence coverage。

Reasoning and decision:
当前产品目标更接近 precision-sensitive financial evidence pack，而不是普通 RAG
top-k 引用。因此改动重点放在三个位置：结构化输出稳定性、缺 direct 时的
bounded adaptive verification、以及 query variant fusion 的噪声控制。table
rescue 作为诊断项测试，但不作为默认策略，除非它能证明提升 direct coverage
且不显著增加 false/partial 噪声。

Work completed:
- Added vLLM structured JSON decoding for planner, verifier, and synthesis.
- Added adaptive verification: first verify top-2, then only for missing-direct
  tasks verify extra candidates up to `adaptive_verify_k`.
- Added task query variants and variant fusion.
- Added original-query-priority variant fusion with `variant_original_quota=2`.
- Added revenue/capex-specific query variants such as `disaggregated revenues`
  and `purchases of property and equipment`.
- Added optional table-rescue verification, then set default back to
  `--table-rescue-k 0` after diagnostics showed no direct-gain benefit.
- Ran cloud v3, v4, v5, and v6 on Qwen3.5-9B text-only vLLM with no CPU offload.
- Pulled all v3-v6 demo JSON/log artifacts back to local `reports/demo/`.

Result and evidence:
- v2 baseline: 7/12 task packs with direct evidence, 24 verified candidates,
  8 direct / 14 partial / 2 false, 286.9s total.
- v3 structured + adaptive: 7/12 direct, 44 verified, 8 direct / 24 partial /
  12 false, 358.6s total.
- v4 variants: 8/12 direct, 52 verified, 12 direct / 22 partial / 18 false,
  419.0s total.
- v5 original-query-priority variants: 8/12 direct, 44 verified, 9 direct /
  23 partial / 12 false, 414.2s total.
- v6 table-rescue diagnostic: 9/12 direct, 50 verified, 10 direct / 25 partial /
  15 false, 402.4s total.
- v6's direct improvement came from the new `disaggregated revenues` query
  variant, which moved `GOOGL_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001` into
  adaptive verification for the Alphabet cloud revenue task.
- Table rescue triggered on three tasks and verified six extra candidates, but
  did not add a direct hit in this query set.
- Remote demo process was confirmed stopped after v6 completion.
- Detailed ledger:
  `reports/model_runs/20260515_phase1_qwen35_9b_full_chain_demo.md`.

Follow-up and safety notes:
- Keep structured JSON, adaptive verification, task query variants, and
  original-query-priority fusion as the current demo default.
- Keep `--table-rescue-k` available for diagnostics, but default it to `0`.
- Remaining weak facets are MSFT AI capex, GOOGL AI capex, and NVIDIA CSP-demand
  durability. These likely need better financial-task wording, reviewed qrels,
  and a precision-oriented semantic reranker/verifier gate rather than wider
  blind recall.
- No credentials or private connection details were written to repo logs.
