# Internal Master Checklist

## Repository Foundation

- [x] Initialize local Git repository with `main`.
- [x] Create feature branch without a `codex` prefix.
- [x] Add private data and generated artifact ignore rules.
- [x] Add Phase 1 project skeleton.
- [x] Add EvidenceObject schema and JSONL helpers.
- [x] Add SEC EDGAR connector with recent and historical submission lookup.
- [x] Add SEC smoke test script.
- [x] Add first Nasdaq tech universe config.
- [x] Add batch SEC filing download script.
- [x] Download first tech universe 10-K HTML cache.
- [x] Add SEC filing manifest scanner and JSONL builder.
- [x] Add section-aware SEC filing parser.
- [x] Add SEC filing chunk builder script.
- [x] Upgrade SEC chunking to semantic block-aware chunks with part labels.
- [x] Add table-aware chunking to preserve HTML table boundaries.
- [x] Add SEC chunk to EvidenceObject conversion.
- [x] Add BM25 index and retriever.
- [x] Add dense index and retriever.
- [x] Add hybrid RRF retriever.
- [x] Add seed gold evidence query set.
- [x] Add retrieval evaluation script.
- [ ] Add an in-process retrieval runner/API to avoid reloading the dense model
      for every query.
- [ ] Promote seed gold set to reviewed gold set with human-checked labels.

## Phase 1 Smoke Tests

- [x] SEC 10-K download smoke test for JPM 2024.
- [x] EvidenceObject JSONL read/write smoke test.
- [x] SEC tech EvidenceObject build smoke test.
- [x] BM25 retrieval smoke test on MSFT/NVDA queries.
- [x] Dense retrieval smoke test on cloud GPU using MiniLM embeddings.
- [x] Seed retrieval evaluation for BM25, dense, and hybrid RRF.
