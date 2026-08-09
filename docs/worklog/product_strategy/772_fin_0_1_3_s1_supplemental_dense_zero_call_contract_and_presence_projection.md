# 772 — FIN 0.1.3 S1 supplemental dense 零调用合同与 10/10 presence projection

## 结论

`S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH` 内的增量稠密索引结构包已经通过零调用证明，但尚未执行真实 BGE embedding 或 Milvus 写入。

两份 immutable supplemental manifest 对应 4 份已捕获官方文件，共产生 410 条完整 source-derived vector specs：DELL 279、MU 128、TSM 3；10-K 279、10-Q 118、8-K 10、6-K 3。每条保持原 evidence ID、ticker、fiscal year、form、URL、publication date、accession、capture digest 与 manifest lineage，仍是 candidate-only，不是 Evidence。

## 防 Gold 泄漏与真实边界

全量 410 条规格先编译并形成 terminal digest `63cd6fad6f6be5ee3a1a82ce3a35840174b183a12087a1597bc1cbfc07b301cd`，随后才读取 Owner qrels 和旧库诊断。qrels 因此只能衡量构建结果，不能决定哪些 source rows 被嵌入。新增库不得覆盖历史 662,908-vector collection，跨库只允许 rank-only RRF 和 canonical evidence identity 去重，禁止直接比较不可校准的 raw scores。

13 个 fake embedding/insert batches 精确终态 410；旧库写入为 0。以下 8 类 mutation 均 fail closed：duplicate evidence identity、capture lineage 缺失、cross-case identity、Owner target absent、旧库或既有目标路径碰撞、embedding dimension 错误、partial insert acknowledgement、raw-score federation。失败时不发布 terminal manifest。

## Presence 解释

旧库 10 个唯一 Owner-selected targets 中已有 5 个。另 5 个缺失 identity 均自然存在于 410 条完整 supplemental corpus，而不是单独按 qrels 拼出的金答案：

- DELL FY2026 10-K `CHUNK_0059`；
- MU Q3 FY2026 8-K `CHUNK_0001`、`CHUNK_0003`；
- MU Q3 FY2026 10-Q `CHUNK_0053`；
- TSM Q2 2026 6-K `CHUNK_0001`。

因此真实 successor 完整构建后，federated physical presence 的预期门为 `10/10 unique、18/18 qrel rows`。这不是 semantic ranking pass：R2 仍有已在旧库却未进 top10/top24 的语义缺口，必须等新库实际存在后用冻结 same-matrix 再测。

## 下一步

1. 先提交并推送当前零调用结构包；
2. 以 clean implementation commit 单独签发一次 410-vector incremental build authority；
3. 真实执行只允许本地 BGE-M3、一个新 Milvus Lite DB/collection、0 retry/network/provider/model/rerank/Evidence；
4. 构建后独立 metadata presence 复证 10/10；
5. 只有 presence 真实通过，才另行判断是否签一次 unchanged-matrix dense/fusion successor。

current-quarter exact SQL `0/6`、external official `4/12`、reranker absent 和 downstream research utilization 均未被本项关闭。

## 证据

- `configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_dense_index_policy_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s1_internal_supplemental_dense_index_zero_call_proof_v1_0.json`
- `src/sec_agent/s1_internal_supplemental_dense_index.py`
- `tests/contract/test_fin_0_1_3_s1_internal_supplemental_dense_index.py`
