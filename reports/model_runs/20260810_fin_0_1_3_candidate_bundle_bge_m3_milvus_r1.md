# Model Run: FIN 0.1.3 CandidateBundle BGE-M3／Milvus R1

## Summary

- Date: 2026-08-10.
- Attempt: `20260810_s1_candidate_bundle_object_bm25_bge_m3_milvus_linux_r1`.
- Status: `terminal_failed_physical_sparse_dense_build_no_retry`.
- Purpose: build one fresh ObjectBM25 and local BGE-M3／Milvus physical index from the same six-case 93-spec CandidateBundle manifest.
- This was a local embedding/index run, not LLM inference, retrieval evaluation, Evidence promotion or report generation.

## Bound Inputs And Resources

- Clean implementation commit: `566d5223dca1d6d28dc802cd4bfa4fa6cc1a477e`.
- Authority digest: `0ca08fecf6d759fbea23b83b5efee0052ac9072302fbe8475a43c37dc2dd4260`.
- Manifest specs: 93; DELL/MU/NVDA/ORCL/ASML/ANET=`15/16/14/19/10/19`.
- Model: local offline `BAAI/bge-m3`, CPU, 1024 dimensions, batch size 8.
- Runtime: Ubuntu-22.04 WSL2; torch `2.10.0+cpu`; sentence-transformers `5.2.3`; pymilvus `3.0.0`; milvus-lite `3.0`.
- Network/provider/LLM/document fetch/vector search/rerank/Evidence=`0/0/0/0/0/0/0`.

## Observed Execution

- BGE model loads=`1`; embedding batches=`12`; vectors=`93`.
- Milvus store creates=`1`; collection creates=`1`; insert batches=`12`; acknowledged vectors=`93`.
- The failed working root contains a directory store with manifest `current_seq=93`, Parquet `93 rows / 15 columns / 625,086 bytes`, and FLAT index `381,056 bytes`.
- Terminal result digest: `3d26e82ab103a404a01ed2af759bc09063b5cc13c604e6b5d9080f64e3830af5`.

## Failure And Interpretation

The publisher checked `database_path.is_file()`. In this bound backend, the `.db` URI materialized as a directory, so the run failed with `candidate_bundle_physical_dense_database_missing` before private receipt and final-root publication.

This does not establish a BGE, corpus or retrieval-quality failure. The physical bytes are partial failed-run evidence only and cannot be queried or promoted as the product index. R1 is consumed, immutable and has no retry.

## Successor Gate

Implement backend-declared file/directory artifacts, complete success/failure counters, canonical directory receipts and whole-root publication. Prove one synthetic vector and clean reproducibility before one fresh R2. No automatic R3 is permitted on a new storage L1.
