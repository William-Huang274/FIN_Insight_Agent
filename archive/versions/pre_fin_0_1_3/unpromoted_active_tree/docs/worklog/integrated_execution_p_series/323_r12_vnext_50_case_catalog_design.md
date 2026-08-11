# 323 R12 vNext 50-Case Catalog Design

日期：2026-06-14

## Prompt

用户要求先一起设计最终可能用于 50 个 case 的测试集，并明确这些 case 最好同时能用于后端和压测。随后确认“按这个思路来设计第一版 50 case catalog 和 case”。

## Decision

- 采用 catalog-first，而不是继续新增零散 JSONL fixture。
- 50 个 case 不一次性全跑；先固化 case schema、分层、release subset、backend profile 和 eval gates。
- 旧 2-case diagnostic probe 不删除；它后续映射到 catalog 的 #23/#24，保留为 diagnostic-only 快速探针。
- 后端压测不再单独写一套玩具样本，而是从 catalog 的 `load_mix_15` 和 L6 stress cases 派生。

## Work Completed

- 新增 `tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json`。
- Catalog 包含：
  - `case_defaults`
  - `case_families`
  - `release_subsets`
  - 50 个 case
  - 每个 case 的 industry schema、prompt、focus/search tickers、metric families、expected gap types、eval focus、backend profile。
- Case 分布：
  - L1 basic focused: 10
  - L2 standard memo: 12
  - L3 deep research: 12
  - L4 gap boundary: 8
  - L5 non-US supply chain: 4
  - L6 backend runtime stress: 4
- Release subset：
  - `r12_successor_12`: 12 个 L3 deep research case。
  - `broader_release_20`: 12 个 L3 + 8 个 L4。
  - `load_mix_15`: 10 个 L1 + 1 个 L3 AI infra + 4 个 L6 stress。
- 新增 `tests/test_vnext_50_case_catalog.py`，校验：
  - schema version
  - case 数量与 ordinal
  - case id 唯一性
  - family count
  - required fields
  - focus tickers 必须在 search scope 内
  - backend profile 基础合法性
  - release subset 引用完整性
  - L6 stress case 的 load scenario。
- 新增 `docs/architecture/agent_graph_vnext/14_vnext_50_case_eval_catalog.zh-CN.md`，说明 catalog 设计原则、分层、release subset、50-case 清单、评测维度、后端/压测复用和下一步 runner 门控。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md` 和 `docs/worklog/00_internal_master_checklist.md`。

## Verification

- `python -m pytest tests/test_vnext_50_case_catalog.py -q`：`4 passed`

## Results

- R12 现在有第一版可机器读取的 50-case catalog。
- 12-case successor / 20-case broader gate / load-mix 不再是口头规划，而是 catalog 中的显式 subset。
- 这轮没有跑 full-chain，也没有消耗 DeepSeek token。

## Follow-up

- 给 R12 runner 增加 catalog loader 和 subset selector。
- 把 #23/#24 映射到当前 diagnostic probe，保留旧 fixture 作为 quick diagnostic。
- 先跑 `r12_successor_12` 的 artifact-reuse / node replay gate，再挑 2-3 个新增 case 跑 full-chain live。
- 后续把 failure/gold lifecycle 与 catalog case id 绑定，避免 case 结果散落在一次性 run artifact 里。

## Safety Notes

- 未写入任何 API key、云端密码或私有路径凭据。
- 新增的是 fixture、测试和文档；没有改动 runtime 执行逻辑。
