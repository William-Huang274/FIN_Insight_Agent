# 409 R42 RD2 Parser / Chunk / Table / Metric Ledger

## Problem

R42 数据底座规划中，RD0 已冻结 raw / RAG / DB inventory，RD1 已建立 raw source provenance。下一步需要把 parser、chunk、table、metric candidate、claim candidate 与 rejection reason 统一成机器可读 Silver ledger，避免后续 full-chain 出问题时只能猜是检索、reranker、writer，还是上游 parser/chunk/table 质量问题。

## Decision

本轮不重新解析原始披露，而是先把已有 parser summary、chunk summary、structured object summary、runtime row summary 和 rejection summary 纳入统一账本。GB 级 JSONL rowset 不为 ledger 重扫全量文件，优先使用 summary 声明的 row count；需要逐行审计时再另起 targeted audit。

RD2 只记录 parser 质量和 rejection taxonomy，不把 rejection/closeout/boundary rows 升级成 accepted evidence，也不把 source-route / coverage-gate / download-smoke summary 混入 parser run 结论。

## Work Completed

- 新增 `src/sec_agent/parser_quality_ledger.py`。
- 新增 `scripts/data_expansion/build_parser_quality_ledger.py`。
- 新增 `tests/test_parser_quality_ledger.py`。
- 物化：
  - `data/manifests/parser_run_ledger_v0_1.jsonl`
  - `data/manifests/parser_output_artifact_ledger_v0_1.jsonl`
  - `data/manifests/parser_rejection_taxonomy_v0_1.jsonl`
  - `data/manifests/parser_quality_summary_v0_1.json`
  - `docs/internal/vnext_20260610/rd2_parser_chunk_table_metric_ledger.zh-CN.md`
- 更新 `docs/architecture/agent_graph_vnext/24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md`。
- 更新 `docs/worklog/00_internal_master_checklist.md` 与 `docs/worklog/README.md`。

## Result

最新真实构建结果：

- status: `pass_with_recorded_rejections`
- parser runs: `52`
- parser output artifacts: `217`
- parser rejection taxonomy rows: `38`
- missing declared outputs: `0`
- declared chunks: `161,455`
- declared tables: `374,536`
- declared metric candidates: `7,974,456`
- declared claim candidates: `2,459,906`
- declared runtime rows: `19,715`
- declared context rows: `6,556`
- recorded rejections: `30,557`

本轮真实构建先暴露了两个实现问题：

- 历史 download / smoke / source-plan summary 被误纳入 parser ledger，导致 RD2 错把 source-route 或下载失败当成 parser failure。已通过 summary 过滤修复。
- `sec_tech_10k_structured_summary.json` 内旧云端绝对路径 `/root/autodl-tmp/FIN_Insight_Agent/...` 在 Windows 本地不能直接存在性校验。已新增 repo-relative relocation，重定位到当前 `D:\FIN_Insight_Agent` 下的真实 structured object 文件。

修复后 missing declared output 从 `5` 降为 `0`，RD2 自身 summary 也被排除，避免自引用污染下一轮 parser status。

## Verification

- `python -m pytest tests/test_parser_quality_ledger.py -q` -> `4 passed`
- `python -m py_compile src/sec_agent/parser_quality_ledger.py scripts/data_expansion/build_parser_quality_ledger.py` -> pass
- `python scripts/data_expansion/build_parser_quality_ledger.py` -> `pass_with_recorded_rejections`

## Boundary And Follow-up

- `pass_with_recorded_rejections` 表示 accepted parser outputs 完整、rejection taxonomy 已入账；rejection rows 仍只能用于质量审计和缺口定位。
- RD2 尚未把 parser ledger 写入长期 SQL/Gold Mart；这是 RD3/RD7 要接的数据库/eval 工作。
- 13 个大型 artifact 未逐行 line-count，是有意避免为 ledger 重扫 GB 级文件；需要局部质量核验时应基于 parser_run_id / artifact_id 发起 targeted audit。
