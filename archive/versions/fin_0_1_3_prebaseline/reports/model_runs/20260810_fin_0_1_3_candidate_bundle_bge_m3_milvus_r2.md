# Model Run: FIN 0.1.3 CandidateBundle BGE-M3／Milvus R2

## Summary

- Date: `2026-08-10`.
- Attempt: `20260810_s1_candidate_bundle_object_bm25_bge_m3_milvus_linux_r2`.
- Status: `terminal_succeeded_physical_sparse_dense_build`.
- Result digest: `6b239d7b2642efd51edc5f89587b28ab544a0e4a27d3a94a264a4c32975c1ce7`.
- Purpose: publish one current six-case CandidateBundle population to ObjectBM25 and local BGE-M3／Milvus after the immutable R1 directory-store failure.
- This was a local embedding/index run, not an LLM run, retrieval evaluation, Evidence promotion or report generation.

## Bound Inputs And Resources

- Clean implementation commit: `afc627f5aef90c9652bae3d21a5be5b7aaa0892b`.
- Authority digest: `a8889058d76a7fd0813ec722d4032356f83e750b0cb5a2696f142ec6ab6a08fd`.
- Manifest specs: 93; DELL/MU/NVDA/ORCL/ASML/ANET=`15/16/14/19/10/19`.
- Model: offline local BGE-M3, CPU, 1024 dimensions, 12 batches.
- Runtime: Ubuntu-22.04 WSL2; directory-backed Milvus Lite profile.
- Network/provider/LLM/document fetch/vector search/rerank/Evidence=`0/0/0/0/0/0/0`.

## Physical Result

- ObjectBM25 records=`93`; sparse candidate state remains `candidate_only_not_evidence`.
- BGE model loads=`1`; embedding batches/vectors=`12/93`.
- Milvus database/collection creates=`1/1`; insert batches/vectors=`12/93`; flush/count/metadata/reopen=`2/2/1/1`.
- Collection manifest reports `current_seq=93`, dimension `1024`, `COSINE` and `FLAT`.
- Directory artifact has 6 files, 7 directories and 1,011,008 bytes; artifact digest=`aebe67d0c143e23c1bf3dd2887443caf338d44226af37699bfd3defd03d63f35`.
- The same artifact digest was verified before and after whole-root publication to the fresh v2 root.
- Wall time=`103088.753 ms`; embedding=`48849.692 ms`; model load=`3911.37 ms`.

## Interpretation And Boundary

R2 closes the physical-publication defect exposed by R1: the current backend's directory store is now inspected, closed, reopened, content-bound and published as one immutable root. It also removes the old-index absence as an excuse for later dense ranking results.

R2 does **not** prove that BGE or fusion retrieves useful financial evidence. No query or vector search ran. The next governed result must compare exact, ObjectBM25, BGE-M3 and fusion on all six cases, with candidate-ceiling and concrete business-error attribution before any reranker or Evidence promotion.
