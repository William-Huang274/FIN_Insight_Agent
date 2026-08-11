# 179 投研覆盖版 Full78 数据扩容计划

Date: 2026-05-28

## 目标

在现有 full30 科技/AI/云/半导体样本基础上，补充 48 家跨行业龙头，形成第一版更适合投研横向比较的 full78 覆盖范围。新增公司与 full30 使用同一数据标准：

- FY2023-FY2025 年报 10-K；
- 最新可用 10-Q，优先选择每家公司最新已接受 10-K 之后的 10-Q；
- 2026/2027 filing year 的 8-K earnings release / Exhibit 99.x，作为管理层解释和业绩新闻稿证据；
- 近三个月离线市场快照，保留价格、相对收益、回撤、波动、事件窗口和 FMP 估值字段；
- 所有输出继续标注来源层级、期间口径、filing 边界、market snapshot `snapshot_id` 和 `as_of_date`。

## 新增覆盖范围

新增 48 家公司：

```text
NFLX, DIS, TMUS,
TSLA, HD, LOW, MCD, BKNG,
COST, KO, PEP, PM,
COP, SLB, EOG,
BAC, MS, BLK, SPGI, PGR, AXP,
UNH, MRK, ABBV, TMO, ISRG,
HON, RTX, UPS, UNP, DE,
LIN, SHW, FCX, NEM, APD,
PLD, AMT, EQIX, WELL, SPG,
NEE, SO, DUK, AEP, CEG,
ORCL, CRM
```

合并原 full30 后，full78 用于覆盖信息技术、通信服务、可选消费、必需消费、能源、金融、医疗、工业、材料、房地产和公用事业。目标是让每个大行业至少有多家公司可以比较，而不是只展示单点案例。

## 配置

新增两个公开配置文件，只包含公司范围和 source contract，不包含数据和密钥：

- `configs/sec_investment_coverage_full78_fy2023_2027.yaml`
- `configs/sec_investment_coverage_8k_earnings_full78_2026_2027.yaml`

私有生成物仍写入：

- `data/raw_private/`
- `data/processed_private/`
- `data/indexes/`
- `eval/sec_cases/outputs/`
- `reports/quality/`

这些目录默认不进入 Git。

## 执行合同

### SEC 主披露

1. 下载 full78 的 10-K/10-Q 缓存。
2. 构建年度 10-K manifest 和 10-Q manifest。
3. 用 `build_sec_mixed_latest_manifest.py` 选择 FY2023-FY2025 10-K 加每家公司最新可用 10-Q。
4. 解析 chunks、structured objects、BM25、ObjectBM25。

要求：

- 不用日历年替代财年；
- 不把 10-Q 的 QTD/YTD/TTM/annual 口径混在一起；
- 如果某家公司缺少某个 filing，记录 source gap，不让模型补数字。

### 8-K earnings release

1. 用同一个 full78 公司清单下载 2026/2027 filing year 的 Item 2.02 / Ex-99.x。
2. 构建 8-K manifest、chunks、evidence。
3. 合并 10-K/10-Q/8-K manifest 和 evidence。
4. 合并 source gaps。

要求：

- 8-K 只作为公司发布、未经审计的管理层解释材料；
- 8-K 数值不能替代 10-K/10-Q 的 Exact-Value Ledger；
- 检索和 synthesis 中应主动使用 8-K 解释业绩驱动、guidance、需求、订单、capex/投资节奏和管理层口径。

### 市场快照

当前 accepted full-source 标准继续使用：

- Yahoo chart 离线 daily bars：价格、成交量、SPY/QQQ 相对收益；
- FMP free-key enrichment：market cap、enterprise value、P/E、EV/Sales、EV/EBITDA；
- SEC filing dates 生成 10-Q 与 8-K 事件窗口；
- DuckDB/parquet/jsonl 保存规范化快照、analytics 和 evidence pack。

本轮 provider probe 结果：

- FMP stable historical EOD 对普通股票和 SPY 可用；
- FMP 对 QQQ 返回 402，因此 full-source market snapshot 仍保留 Yahoo bars 作为价格/benchmark provider，FMP 只做估值 enrichment；
- FMP key 只通过环境变量使用，不写入文件。

## 预期产物

私有数据产物命名使用 `sec_investment_coverage_full78` 前缀：

- `data/processed_private/manifests/sec_investment_coverage_10k_manifest_fy2023_2025.jsonl`
- `data/processed_private/manifests/sec_investment_coverage_10q_manifest_fy2026_2027.jsonl`
- `data/processed_private/manifests/sec_investment_coverage_mixed_10k_latest_10q_manifest_fy2023_2027.jsonl`
- `data/processed_private/manifests/sec_investment_coverage_8k_earnings_manifest_2026_2027.jsonl`
- `data/processed_private/manifests/sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl`
- `data/processed_private/evidence_objects/sec_investment_coverage_mixed_with_8k_evidence_fy2023_2027.jsonl`
- `data/indexes/bm25/sec_investment_coverage_mixed_with_8k_fy2023_2027/`
- `data/indexes/bm25/sec_investment_coverage_mixed_with_8k_fy2023_2027_objects/`
- `data/processed_private/market/evidence_packs/<snapshot_id>_3m_market_evidence.jsonl`

## 验证标准

数据构建先过 contract checks，再进入 DeepSeek full-source smoke：

- YAML 配置解析通过，full78 数量为 78 且无重复；
- 10-K 覆盖目标：每家公司 FY2023-FY2025 最多 3 条，缺口有明确 reason；
- 10-Q 覆盖目标：每家公司最新可用 10-Q 1 条，FY2026/FY2027 混合但按 latest-after-10K 选择；
- 8-K 覆盖目标：2026 filing year 尽量覆盖，2027 缺口按当前日期记录为 expected gap；
- market snapshot 覆盖目标：78 家目标公司均有价格快照，FMP 估值缺口显式记录；
- main-chain smoke 至少覆盖一个跨行业宽范围问题和一个两轮 follow-up；
- gates 必须通过 source boundary、market as-of date、ledger grounding、claim support、semantic contract；
- 不因缺口加业务兜底，优先修下载、manifest、parser、retrieval 或 source contract 的实际问题。

## 初始执行记录

- 已创建 full78 主披露配置和 full78 8-K earnings 配置。
- 配置解析结果：78 家公司、无重复，新增 48 家。
- SEC 10-K/10-Q dry-run 可按新配置规划路径。
- SEC 8-K dry-run 可按新配置规划 Item 2.02/Ex-99.x 下载。
- FMP provider probe：
  - 普通股票与 SPY 短窗口 historical EOD 可用；
  - QQQ ETF 返回 provider 402，不作为本轮 FMP historical 依赖；
  - 继续采用 Yahoo bars + FMP valuation enrichment 的 full-source 标准。

## 下一步

1. 下载新增 48 家 FY2023-FY2025 10-K、FY2026/FY2027 10-Q、2026/2027 8-K earnings release。
2. 构建 full78 mixed manifest、chunks、evidence、structured objects 和 BM25/ObjectBM25。
3. 构建 full78 market snapshot：Yahoo bars、FMP valuation enrichment、event-window analytics、market evidence pack。
4. 跑 local contract smoke。
5. 跑 DeepSeek full-source 宽范围投研 smoke，并记录 coverage、timing、gates 和输出质量。

## 2026-05-28 检索与 BGE 重排诊断

### 现象

本地从 DeepSeek planner 产出的 full78 宽范围 case 继续跑 full-source 链路时，BGE rerank 在 RTX 4060 Laptop GPU 上超过 15 分钟仍未完成。`nvidia-smi` 显示 Python 进程实际占用 CUDA，GPU 利用率接近 100%，因此不是误走 CPU。

### 诊断证据

- case: `eval/sec_cases/outputs/sec_investment_coverage_full78_deepseek_full_source_baseline/20260528_113032_4fecae1b37/case.jsonl`
- 范围：78 家公司、FY2025/FY2026、5 个 decomposed tasks、11 个 numeric checks、12 个 metric families。
- 关闭 BGE 后的 context-only 诊断输出：`eval/sec_cases/outputs/sec_investment_coverage_full78_deepseek_bge_candidate_diagnostic/trace_logs.jsonl`
- `candidate_row_count_pre_rerank=5151`
- `candidate_generation=57125ms`
- 候选构成：
  - evidence_object: 4177
  - structured_object: 974
  - pipeline_bm25: 619
  - pipeline_bm25_requirement: 3558
  - pipeline_object_bm25: 974

### 判断

当前召回规模对 full78 宽范围研究问题不算离谱，平均约 33 行 / ticker-year；问题在于默认把所有候选都送入 CrossEncoder。BGE reranker 是 pairwise cross-encoder，成本近似随候选数、输入长度和 batch 成线性增长。5151 个候选、最长 6000 字符、max_length 2048 的配置在 5090 上需要 2-3 分钟，在本机 4060 上跑到 15 分钟级别是资源与默认预算共同造成的，不应作为交互默认路径。

这不是模型输出质量问题，也不是应该放松 coverage/gate 的问题。更准确的拆分是：

- 召回策略：宽召回可以保留，但 requirement BM25 对所有 ticker-year 全量展开会放大候选，后续应按 task / sector / required_tickers 约束。
- 重排策略：全量 CrossEncoder 精排不适合作默认交互链路；应对前 N 个候选做 BGE rerank，同时保留尾部候选作为后续 coverage/ledger 的可用池。
- 资源限制：本机 4060 与云端 5090 都会受 pairwise rerank 成本影响，只是云端能承受更大的候选预算。生产/演示需要按硬件 profile 设置默认预算。

### 当前代码调整

已把默认 BGE 预算从“全量候选”改为有界预算：

- `RERANKER_CANDIDATE_LIMIT=800`
- `RERANKER_BATCH_SIZE=16`
- `RERANKER_MAX_LENGTH=1024`
- `RERANKER_DOC_MAX_CHARS=3000`

同样调整了 `scripts/run_sec_benchmark_eval.py` 的默认 context reranker 参数。该调整不是降低检索质量的兜底，而是把 cross-encoder rerank 从全量二阶段排序改成受预算约束的二阶段排序。是否作为最终默认值，还需要跑 bounded BGE smoke 比较 coverage matrix、ledger row 分布和回答质量。

### 下一步验证

1. 用同一 DeepSeek planner case 跑 bounded BGE context-only，记录 `candidate_row_count_pre_rerank`、`context_rerank_ms`、最终 context rows。
2. 跑 bounded BGE full-source deterministic smoke，确认 `coverage_complete=true`、`primary_task_support_complete=true`、market snapshot 仍完整。
3. 跑 DeepSeek synthesis smoke，抽查输出是否仍覆盖行业横向比较、8-K 管理层解释、市场快照 as-of date 和估值分歧。
4. 后续优化 retrieval strategy：按 decomposed task 的 required_tickers/source tiers/metric families 约束 requirement BM25，减少无关 ticker-year 的候选膨胀。

## 2026-05-28 检索与二次检索主线升级计划

### 问题定义

full78 暴露的核心问题不是单台机器性能不足，而是当前检索链路仍偏早期形态：先按公司、年份、来源和 query 全局展开候选，再把扁平候选池交给 BGE CrossEncoder 统一重排。随着公司数、filing 类型、8-K、market snapshot、后续新闻或行业数据继续增加，候选规模会按 `公司 × 年份 × 来源 × query 数 × topK` 放大。

临时限制 `RERANKER_CANDIDATE_LIMIT` 可以控制交互耗时，但不能作为长期主线。长期主线应改成：

1. planner 输出可执行的 `RetrievalPlan`，而不是只输出宽泛 decomposed tasks。
2. retrieval executor 按任务和来源分路召回，结构化事实优先，文本解释再进入 BGE。
3. BGE 只做 route-local 二阶段精排，不再承担全局筛选。
4. evidence pack 先满足 coverage reservation，再让分数竞争剩余预算。
5. 宽范围问题按行业、任务或来源做 map-reduce，而不是一次塞入全局 synthesis。
6. Evidence Coverage Matrix 对证据强度做判断；如果缺口在当前库存内可查，系统自动触发 scoped second-pass retrieval。

### RetrievalPlan 合同

下一步 planner 需要把每个分析任务补全为可执行检索计划。建议新增或派生字段：

```text
task_id
question_zh
analysis_intent
tickers
sector
years
filing_types
source_tiers
metric_families
period_roles
retrieval_route
candidate_budget
rerank_budget
coverage_requirements
second_pass_policy
```

`retrieval_route` 先支持以下枚举：

- `ledger_first`: 财务数值、capex、现金流、R&D、margin、收入、资产质量等结构化事实。
- `filing_text`: 10-K/10-Q 中的 MD&A、风险、业务描述和分部解释。
- `8k_commentary`: 8-K earnings release / Exhibit 99.x 中的管理层解释、guidance、需求、订单、margin/capex commentary。
- `market_snapshot`: 离线市场快照、估值、相对收益、回撤、事件窗口。
- `risk_text`: 风险因素、客户集中、监管、周期性等文本证据。

planner 可以由 API 大模型在受约束 schema 下生成，但必须通过 deterministic validator：

- task 数量、字段长度、route 枚举、公司范围、年份范围、filing 类型和 source tier 必须校验；
- 不允许 planner 输出最终答案、精确财务值或 evidence id；
- 如果 planner 要求当前 source inventory 不存在的数据，只能进入 source gap；
- 如果 planner 识别出需要 10-Q/8-K/market snapshot 且这些来源在当前 inventory 存在，应进入 retrieval route，而不是交给最终答案写“建议补查”。

### Route Executor 设计

`ledger_first`:

- 从 structured objects、runtime ledger 或后续 DuckDB 表按 `ticker + fiscal_year + form_type + period_role + metric_family` 精确查数。
- 不走 BGE。
- 输出 ledger rows、metric ids、source evidence ids 和 period-role 元数据。

`filing_text`:

- 用 BM25 做粗召回。
- 先按 ticker、year、filing type、source tier、section、metric family、period role、ledger-linked evidence 做轻量过滤。
- 每个 task 只保留小候选池进入 BGE，例如 50-150 行，具体预算由 `rerank_budget` 和运行 profile 控制。

`8k_commentary`:

- 只查 company-authored unaudited 8-K earnings release / Exhibit 99.x。
- 优先召回 management commentary、guidance、demand、orders/backlog、margin、capex/investment cadence。
- 输出时必须保留 unaudited source boundary；不能覆盖 10-K/10-Q ledger 财务事实。

`market_snapshot`:

- 直接从 market analytics / evidence pack / DuckDB 取结构化视图。
- 不走 BGE。
- 必须保留 `snapshot_id`、`as_of_date`、provider、字段缺口和事件窗口定义。

`risk_text`:

- 走 section-aware BM25 + route-local BGE。
- 只支持已有 filing / 8-K 文本内的风险和反证，不引入外部新闻或模型记忆。

### Coverage Reservation

宽范围问题的 evidence pack 不能只按 BGE 分数堆叠。进入 synthesis 前需要先做 coverage reservation：

- 每个 primary task 至少保留若干 ledger rows 或 source rows；
- 每个 source tier 至少保留代表性证据：10-K/10-Q、8-K、market snapshot；
- 每个关键 metric family 至少保留代表性 metric ids；
- 每个 period role 不能混用，QTD/YTD/TTM/annual 分开保留；
- 跨行业问题按 sector 或行业组保留最小证据；
- market evidence 必须保留 `as_of_date` 和估值/收益字段引用。

剩余预算再交给 route-local 分数竞争。最终 evidence pack 需要记录 reservation policy、每类保留数量、被裁剪原因和未满足的 coverage requirement。

### 二次检索闭环

二次检索不是业务兜底，而是 evidence adequacy loop。触发条件来自 Coverage Matrix 和 Judgment Plan，而不是最终答案自由发挥。

第一次 retrieval 后，系统需要把缺口分为三类：

- `searchable_in_current_inventory`: 当前 inventory 已有对应 10-Q、8-K、10-K 或 market snapshot，但首次 evidence pack 未覆盖。
- `external_or_not_in_inventory`: 当前 source policy 或 manifest 没有该来源，例如 consensus、forward estimates、新闻或缺失 filing。
- `not_required_for_answer`: 该缺口不影响当前问题的 primary judgment，只需在边界里弱化。

只有 `searchable_in_current_inventory` 可以自动触发 second-pass retrieval。second-pass request 必须是 scoped 的：

```text
trigger_task_id
missing_reason
tickers
years
filing_types
source_tiers
metric_families
period_roles
section_hints
retrieval_route
candidate_budget
rerank_budget
```

执行方式：

1. 对缺口对应 route 追加检索，不重跑无关 routes。
2. 新旧 context rows 去重合并。
3. 重建 runtime ledger。
4. 重建 Evidence Coverage Matrix。
5. 重建 Judgment Plan。
6. 进入 synthesis。

默认只允许一次 second pass；如果扩大检索后仍不足，最终答案仍应说明当前证据能支持的观点、不能强推的观点，以及哪些缺口属于当前库存外或来源缺失。不能因为二次检索失败就跳过回答。

### 最终输出呈现

最终答案不要单独列出“二次检索证据区”，否则投研 memo 会被执行日志切断。正确做法是：

- 在正文的判断、反证或证据边界里自然说明扩大检索后的证据状态；
- 只暴露简短的可审计理由摘要，例如“由于初次证据缺少 8-K 管理层解释，系统扩大到 8-K earnings release 后，结论从强判断降为有条件判断”；
- 不输出内部逐步推理链、原始检索 query 列表或完整候选明细；
- 完整 second-pass trigger、request、candidate counts、coverage delta、gates 和耗时写入后台 artifact。

### Observability 指标

新增或强化以下 telemetry：

```text
retrieval_plan_task_count
route_count
candidate_pre_filter
candidate_after_filter
candidate_sent_to_bge
bge_ms_by_route
ledger_first_row_count
coverage_reserved_row_count
coverage_reservation_miss_count
second_pass_triggered
second_pass_reason
second_pass_candidate_count
second_pass_coverage_delta
target_source_coverage
ledger_family_coverage
sector_coverage
source_tier_coverage
primary_task_support_complete
```

判断标准不是候选越少越好，而是：

- 进入 BGE 的候选显著下降；
- coverage 不下降；
- ledger 关键指标不丢；
- 8-K 管理层解释和 market snapshot 仍能进入答案；
- full78 宽范围问题能稳定收敛，后续 full200 或新增 source 时候选增长可控。

### 执行步骤

1. 定义 `RetrievalPlan` schema 和 validator。
   - 从现有 Query Contract / decomposed tasks 派生初版 plan，先不依赖模型输出新字段。
   - 后续再让 API planner 直接输出 route 字段，并用 validator fail closed。

2. 改造 retrieval executor 为 route-based。
   - 先实现 `ledger_first` 和 `market_snapshot` 不走 BGE。
   - 再拆 `filing_text`、`8k_commentary`、`risk_text` 的 route-local BM25 + BGE。

3. 引入 pre-filter 和 route-local budget。
   - 按 ticker/year/source/section/metric family/period role/ledger link 过滤。
   - 记录每个 route 的候选数量和进入 BGE 的数量。

4. 实现 coverage reservation。
   - 按 task、sector、source tier、metric family、period role 和 market as-of date 保留最小证据。
   - evidence pack 写入 reservation policy 和未满足项。

5. 实现 evidence adequacy loop。
   - Coverage Matrix 输出缺口分类。
   - 对 `searchable_in_current_inventory` 生成 second-pass retrieval request。
   - 只重跑相关 route，并重建 ledger、coverage、Judgment Plan。

6. 调整 synthesis prompt 和 renderer。
   - prompt 要求模型基于 expanded evidence 写投研 memo，不把 second-pass 当成单独章节。
   - renderer 只展示自然融入答案的证据状态和来源边界。
   - 后台 artifact 保留 second-pass trace。

7. 验证 full78。
   - 固定同一宽范围 case，对比旧链路、bounded BGE、route-based 链路。
   - 记录 latency、BGE 候选数、coverage、ledger row 分布、gates 和输出质量。

8. 扩展到多轮 session。
   - follow-up 优先复用上一轮 `RetrievalPlan`、coverage state 和 evidence pack。
   - 当用户缩小范围时只重查受影响 route；当用户新增来源或行业时触发 scoped second pass 或新 route。

## 2026-05-28 RetrievalPlan Step 1 实施记录

### 目标

落实主线升级计划第一步：先定义 `RetrievalPlan` schema 和 validator，从当前 Query Contract / decomposed tasks 派生初版 plan，不立即替换现有 retrieval executor。

### 已完成

- 新增 `src/sec_agent/retrieval_plan.py`：
  - `build_retrieval_plan(query_contract, case=...)`
  - `validate_retrieval_plan(plan, query_contract=..., case=...)`
  - route 枚举：`ledger_first`、`filing_text`、`8k_commentary`、`market_snapshot`、`risk_text`
  - 每条 route 记录 task、tickers、years、filing_types、source_tiers、metric_families、period_roles、section_hints、candidate_budget、rerank_budget、coverage_requirements 和 second_pass_policy。
- `ledger_first` 与 `market_snapshot` 默认 `rerank_budget=0`，明确结构化事实和市场快照不进入 BGE。
- `filing_text`、`8k_commentary`、`risk_text` 只设置 route-local BGE budget，为下一步 executor 改造准备。
- validator 会校验 route 枚举，并把 tickers、years、filing_types、source_tiers 限制在 Query Contract 范围内。
- interactive 入口现在在每次 run 中写出：
  - `retrieval_plan.json`
  - `case.jsonl` 内嵌 `retrieval_plan`
  - `sec_agent_state.json` 记录可选 artifact `retrieval_plan`
- resume 时如果老 run 缺少 `retrieval_plan.json`，会从已有 Query Contract 派生并补写，不影响旧 artifact 恢复。
- `/plan` / `--plan-only` 预览会打印 retrieval plan 摘要，包括 task count、route count、route counts 和 BGE rerank budget。

### 验证

- `python -m py_compile src\sec_agent\retrieval_plan.py src\sec_agent\graph_state.py scripts\cloud\sec_agent_interactive.py`
- `python -m pytest tests\test_sec_agent_retrieval_plan.py -q` -> `3 passed`
- `python -m pytest tests\test_resume_closeout_readiness.py tests\test_sec_agent_p0_observability.py tests\test_market_snapshot_fixture.py::test_interactive_market_context_loader_and_renderer_boundary tests\test_sec_agent_8k_earnings_source.py::test_context_session_forwards_source_gap_path_to_graph_args -q` -> `18 passed`
- `python -m pytest tests\test_sec_agent_10q_source_contract.py::test_coverage_matrix_counts_matching_10q_source_scope tests\test_sec_agent_10q_source_contract.py::test_runtime_ledger_and_renderer_surface_period_role tests\test_sec_agent_8k_earnings_source.py::test_renderer_labels_8k_and_primary_sec_source_boundaries -q` -> `3 passed`
- plan-only smoke：
  - manifest: `data/processed_private/manifests/sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl`
  - prompt: `结合10-K、最新10-Q、8-K和市场快照，比较NVDA、AMD、MSFT的AI基本面、管理层解释和市场反应`
  - result: `validation=pass tasks=4 routes=17 bge_budget=456 routes_by_type=8k_commentary=4,filing_text=4,ledger_first=4,market_snapshot=4,risk_text=1`

### 结论

Step 1 已完成。当前链路仍按旧 retrieval executor 执行，但 run artifact 已具备 route-based executor 所需的计划合同。下一步应进入 Step 2：让 retrieval executor 读取 `RetrievalPlan`，优先实现 `ledger_first` 与 `market_snapshot` 不走 BGE，再拆 `filing_text` / `8k_commentary` / `risk_text` 的 route-local BM25 + BGE。

## 2026-05-28 Route Executor Step 2 初始实施记录

### 目标

开始让 context executor 消费 `RetrievalPlan`。本阶段只实现向后兼容的初始 route-based candidate generation，不改 synthesis、不改 coverage gate、不改变没有 `retrieval_plan` 的旧 case 行为。

### 已完成

- `scripts/run_sec_benchmark_eval.py` 在 `case["retrieval_plan"]` 存在且 validation pass 时启用 route-based context rows。
- `ledger_first` route：
  - 使用 ObjectBM25 / structured objects 按 route 的 ticker/year/form/source/metric_family 取结构化对象；
  - 写入 `retrieval_route=ledger_first`、`selection_route_id`、`rerank_eligible=false`；
  - 不进入 BGE rerank。
- `filing_text` / `8k_commentary` / `risk_text` route：
  - 使用 BM25 按 route scope 召回文本证据；
  - 写入 `retrieval_route`、`selection_route_id`、`rerank_eligible=true`；
  - 仍进入 BGE，但只作为 route-local 候选池。
- `market_snapshot` route：
  - 不走 BM25/BGE；
  - 保留到 interactive 后续 `attach_market_snapshot_context` 阶段注入。
- `_rerank_context_rows` 支持 route-scoped rows：
  - `rerank_eligible=false` 的结构化行直接保留；
  - BGE 只接收 `rerank_eligible=true` 的文本候选；
  - route-scoped merge 保留 pinned structured rows 和 reranked text rows。
- `context_policy` 新增：
  - `retrieval_plan_enabled`
  - `retrieval_plan_summary`
  - `route_candidate_stats`
  - `candidate_sent_to_bge`

### 验证

- `python -m py_compile scripts\run_sec_benchmark_eval.py src\sec_agent\retrieval_plan.py scripts\cloud\sec_agent_interactive.py src\sec_agent\graph_state.py`
- `python -m pytest tests\test_sec_agent_retrieval_plan.py -q` -> `4 passed`
- `python -m pytest tests\test_bm25_retriever.py tests\test_sec_benchmark_eval_mixed_context.py tests\test_resume_closeout_readiness.py -q` -> `14 passed`
- `python -m pytest tests\test_sec_agent_p0_observability.py tests\test_market_snapshot_fixture.py::test_interactive_market_context_loader_and_renderer_boundary tests\test_sec_agent_8k_earnings_source.py::test_context_session_forwards_source_gap_path_to_graph_args -q` -> `11 passed`

新增单测覆盖：

- route executor 能同时生成 `ledger_first` 和 `filing_text` rows；
- `ledger_first` 结构化行 `rerank_eligible=false`；
- fake reranker 只收到文本行，未收到结构化 ledger-first 行。

### 真实索引 smoke 结果

尝试用 full78 actual BM25/ObjectBM25 index 做一个不调模型、不跑 BGE 的 in-memory route smoke，180 秒超时。该命令没有进入 BGE；因此这次暴露的是本地 full78 BM25/ObjectBM25 index 加载或 filtered search 的 I/O/反序列化成本问题，不应归因于 CrossEncoder。

当前判断：

- Step 2 代码级 route executor 已具备基本合同和单元验证；
- 真实 full78 索引 smoke 仍需要单独性能诊断；
- 下一步不应为了通过本地 smoke 加业务兜底，而应检查 index 加载缓存、records 体积、filtered search 路径和常驻 in-process runner 是否被正确复用。

### 下一步

1. 跑一个受控的 index-load-only profile，分开记录 BM25 index load、ObjectBM25 index load、单次 filtered search 时间。
2. 如果 load 是主耗时，优先走常驻 in-process runner / session cache，而不是每轮重载。
3. 如果 filtered search 是主耗时，继续优化 route pre-filter 和 index metadata，而不是扩大 BGE 预算。
4. 完成 route executor 的真实 full78 context-only smoke 后，再进入 coverage reservation。

## 2026-05-28 本地 full78 索引加载诊断与修复

### 诊断目标

确认本地 full78 宽问题变慢到底发生在：

- BM25 index load；
- ObjectBM25 index load；
- filtered search；
- BGE CrossEncoder；
- runtime ledger 重复加载。

这一步不调整业务结论、不放松 coverage，不加入兜底，只拆分链路耗时。

### 受控 profiling 结果

full78 索引文件体积：

- BM25: `bm25.pkl=82.6MB`, `records.jsonl=171.4MB`, records=`30,554`。
- ObjectBM25: `bm25.pkl=511.0MB`, `records.jsonl=2.03GB`, records=`1,118,234`。

修复前：

- `BM25Retriever` 初始化约 `3.68s`，过滤查询约 `0.005s`。
- `ObjectBM25Retriever` 初始化约 `151.02s`，过滤查询约 `0.141s`。

拆分 ObjectBM25 初始化后：

- `pickle.load(bm25.pkl)` 约 `7.86s`。
- `records.jsonl` 解析约 `32.81s`。
- filter index 构建约 `6.53s`。

结论：

- 真正慢点不是 filtered search，也不是当前这轮 BGE；
- full78 的 ObjectBM25 大对象记录加载是主要固定成本；
- 前端 `exit code 9` 出现在 ledger 阶段，是因为检索阶段已持有 ObjectBM25 记录，ledger 又重复读取同一个 2GB `records.jsonl`，本机内存峰值过高。

### 已完成修复

1. `src/retrieval/bm25_retriever.py`
   - `records.jsonl` 从 `read_text().splitlines()` 改为流式读取，减少大文件加载峰值。

2. `src/retrieval/object_bm25_retriever.py`
   - 同样改为流式读取 ObjectBM25 records。

3. `scripts/cloud/sec_agent_interactive.py`
   - in-process context runtime 加载 `ObjectBM25Retriever` 后，将已加载对象记录注册到 runtime cache。
   - runtime ledger 优先复用该 cache，不再重复读 2GB object records。

4. `scripts/run_sec_benchmark_eval.py`
   - route-scoped merge 改为 `len(pinned structured rows) + top_k text rows`，避免 full78 下结构化 ledger-first rows 把 BGE 选出的 8-K/filing text rows 挤掉。
   - BGE 前候选选择开始执行 route-local `rerank_budget`，而不是只依赖全局 `context_reranker_candidate_limit`。

修复后 profiling：

- `BM25Retriever` 初始化约 `2.25s`，过滤查询约 `0.006s`。
- `ObjectBM25Retriever` 初始化约 `41.16s`，过滤查询约 `0.163s`。
- 复用 ObjectBM25 records 后，runtime ledger 构建约 `2.97s`，生成 ledger rows=`48`。

新增验证：

- `python -m py_compile scripts\run_sec_benchmark_eval.py scripts\cloud\sec_agent_interactive.py src\retrieval\bm25_retriever.py src\retrieval\object_bm25_retriever.py`
- `pytest tests\test_sec_agent_retrieval_plan.py tests\test_bm25_retriever.py -q` -> `8 passed`
- `pytest tests\test_bm25_retriever.py tests\test_sec_benchmark_eval_mixed_context.py tests\test_sec_agent_p0_observability.py -q` -> `16 passed`

### route context-only smoke

用 full78 DeepSeek planner 产出的真实 query contract 生成 RetrievalPlan：

- tasks=`5`
- routes=`20`
- `candidate_budget_total=1488`
- `rerank_budget_total=520`
- `second_pass_enabled=True`

本地 context-only smoke：

- case: `eval/sec_cases/outputs/sec_investment_coverage_full78_route_profile/20260528_local_route_context_only/case.jsonl`
- output: `eval/sec_cases/outputs/sec_investment_coverage_full78_route_profile/20260528_local_route_context_only/context_only`
- reranker: `none`，只测试路由检索和候选生成。
- wall time: `89.65s`
- status: `context_prepared`
- candidate generation: `16.28s`
- context rows: `568`
- structured rows: `408`
- text rows: `160`
- rows that would enter BGE: `160`

与旧路径的关键差异：

- 旧路径 full78 宽问题候选约 `5151` 行，默认全部进入全局 BGE。
- route executor 后结构化 rows 不进入 BGE，文本候选收敛到 `160` 行。
- 当前本地耗时主要仍是 ObjectBM25 启动固定成本；候选生成本身已经收敛。

### 当前判断

这轮修复解决了两个实际链路问题：

- 大 JSONL 加载方式导致的峰值内存和启动时间问题；
- runtime ledger 重复读取 ObjectBM25 records 导致的内存杀进程问题。

### 2026-05-28 存储路径改造

目标不是为本机 4060 做特殊降级，而是把大规模数据下不应该进交互热路径的全量 JSONL 解析拆出去：

- runtime ledger 不再依赖 ObjectBM25 `records.jsonl`；
- ObjectBM25 不再为每次 session 冷启动加载 110 万条完整结构化对象 dict；
- route executor 仍保持原有检索/coverage 合同，不通过放松 coverage 或加业务兜底来提速。

已落地：

1. Lightweight Ledger Store
   - 新增 `src/sec_agent/ledger_store.py`。
   - 新增 `scripts/ledger/10_build_lightweight_ledger_store.py`。
   - 主链路新增 `--ledger-store-path` / `LEDGER_STORE_PATH`，存在 DuckDB store 时 runtime ledger 优先按 `object_id/ticker/year/form_type/source_tier/metric_family` 精确查询。
   - 已生成 full78 过滤版：
     - `data/processed_private/ledger/sec_investment_coverage_mixed_with_8k_fy2023_2027_core_ledger.duckdb`
     - source records scanned=`903,431`
     - ledger facts=`131,773`
   - runtime ledger store profile：约 `1.49s`，ledger rows=`48`。

2. ObjectBM25 Record Store
   - 新增 `scripts/ledger/20_build_object_bm25_slim_records.py`，可从完整 `records.jsonl` 生成 `records.slim.pkl`。
   - 新增 `scripts/indexing/20_build_object_bm25_record_store.py`，从 `records.slim.pkl` 构建 `records.duckdb`。
   - `src/retrieval/object_bm25_retriever.py` 优先使用 `records.duckdb`；只有 metadata 完整且 row count 与 BM25 文档数一致才启用，避免半成品库污染运行。
   - SQL store 只保存检索/过滤/展示必要字段，不再重复保存完整表格/cell payload。
   - 查询连接复用，topK 记录批量读取。
   - SQL 路径补上 filter cache，避免同一 `ticker/year/form/source_tier/object_type` 过滤条件在 route 内重复查询 DuckDB。

3. 构建性能
   - 一次中断暴露出旧构建脚本会留下半成品 DB；已改为 `.tmp` 原子写入，写完 metadata 后才替换正式文件。
   - 新构建入口支持 `--duckdb-threads`。
   - full78 ObjectBM25 record-store 构建命令：

```powershell
python scripts\indexing\20_build_object_bm25_record_store.py `
  --index-dir data\indexes\bm25\sec_investment_coverage_mixed_with_8k_fy2023_2027_objects `
  --batch-size 50000 `
  --duckdb-threads 12
```

构建结果：

- source: `records.slim.pkl`
- output: `records.duckdb`
- records=`1,118,234`
- output size=`133,443,584` bytes
- elapsed=`40.54s`

4. ObjectBM25 profile
   - 旧完整 JSONL/stream path：初始化约 `41.16s`。
   - slim pickle path：初始化约 `29.58s`。
   - DuckDB record-store path：初始化约 `7.77-8.56s`，不加载 records list。
   - SQL store 首次 filtered search 约 `1.33s`，连接复用后同进程查询约 `0.07-0.09s`。

5. full78 context-only smoke
   - case: `eval/sec_cases/outputs/sec_investment_coverage_full78_route_profile/20260528_local_route_context_only/case.jsonl`
   - output: `eval/sec_cases/outputs/sec_investment_coverage_full78_route_profile/20260528_local_route_context_only/context_only_sql_record_store`
   - status=`context_prepared`
   - wall time=`37.1s`
   - context rows=`568`
   - structured rows=`408`
   - text rows=`160`
   - coverage reservation: `reserved_count=82`, `slot_count=82`
- candidate_generation=`21,179ms`

补上 SQL filter cache 后复测：

- output: `eval/sec_cases/outputs/sec_investment_coverage_full78_route_profile/20260528_local_route_context_only/context_only_sql_record_store_filter_cache`
- status=`context_prepared`
- context rows=`568`
- structured rows=`408`
- text rows=`160`
- coverage reservation: `reserved_count=82`, `slot_count=82`
- candidate_generation=`16,881ms`

验证：

- `python -m py_compile src\retrieval\object_bm25_retriever.py scripts\indexing\20_build_object_bm25_record_store.py`
- `pytest tests\test_bm25_retriever.py tests\test_sec_agent_retrieval_plan.py tests\test_sec_agent_ledger_store.py -q` -> `15 passed`

### 当前判断

这一步已经把最大风险从“每轮解析/持有 2GB ObjectBM25 records + ledger 重复读 2GB”改成：

- ObjectBM25 冷启动主要是 `bm25.pkl` 加载，约 6-8 秒；
- route-local SQL metadata 查询在同进程内可复用连接；
- runtime ledger 走 DuckDB facts，不再扫描 ObjectBM25 records；
- full78 context-only 已能在本地稳定进入 `context_prepared`。

仍未完成的核心优化：

- candidate_generation 已回到约 `16.9s`，下一步应减少 route executor 对 ObjectBM25 的重复 BM25 scoring 次数，按 route 级合并 query 或批量裁剪候选；
- BM25 text index 仍是 pickle + JSONL，当前体积可接受，但 full200 之后也需要同样的 record-store 设计；
- second-pass retrieval 还未落地：coverage 不足时应由 coverage gap 触发二次检索，最终答案自然说明补查后的证据边界，后台记录触发原因和补查结果。

### 下一步

1. 将 workbench / demo profile 的默认环境补上 `LEDGER_STORE_PATH`，确保前端 smoke 走 SQL ledger store。
2. 优化 route executor 的 ObjectBM25 调用次数：从每个 query/ticker/year 单独查，改成 route 级批量候选与本地 topK 裁剪。
3. 设计 second-pass retrieval contract：coverage matrix 输出缺口 -> retrieval plan 扩大 route scope -> synthesis 使用补查后的统一 evidence pack。

## 2026-05-28 EvidenceRequirementPlan 主线调整

### 方向修正

上一版 route 优化仍有一个风险：如果 route 完全由代码按关键词或固定规则决定，确实会接近推荐系统式的手写召回策略，容易漏掉用户问题真正需要的证据。新的主线改为：

1. API planner 先输出 `Query Contract`，同时输出 `EvidenceRequirementPlan`。
2. `EvidenceRequirementPlan` 用业务语言列出“这个问题需要哪些证据”，例如哪些公司、年份、财报类型、来源层级、指标族、期间口径和证据路线。
3. 编译器只负责把 evidence requirement 转成物理 `RetrievalPlan`，并做范围校验、预算裁剪、同候选合并和可观测记录。
4. BM25/ObjectBM25/BGE 不再决定业务路线，只在每条证据需求限定的候选空间内做检索和排序。
5. 如果 Coverage Matrix 判断证据不足且缺口在当前 inventory 内可查，系统触发 scoped second-pass retrieval，而不是让最终答案只写“建议补查”。

这个设计保留模型对投研问题的理解能力，同时让程序负责证据边界、索引查询、预算和校验。模型不能直接指定 evidence id、不能写精确财务值、不能越过 source inventory；但它可以明确说明“我需要 10-Q 的 YTD cash flow、8-K 的管理层 capex 解释、market snapshot 的 3M 相对收益”等证据需求。

### 新合同层次

`Query Contract` 仍负责全局任务边界：

```text
task_type
focus_tickers / search_scope_tickers
years
filing_types
source_tiers
metric_families
market_snapshot
decomposed_tasks
source gaps / caveats / forbidden claims
```

新增 `EvidenceRequirementPlan` 负责证据需求：

```text
requirement_id
task_id
question_zh
analysis_intent
tickers
years
filing_types
source_tiers
metric_families
period_roles
evidence_routes
section_hints
market_fields
candidate_budget
rerank_budget
second_pass_policy
```

`evidence_routes` 是业务证据路线，不是硬编码行业规则：

- `ledger_first`: 财务数值、capex、cash flow、margin、RPO、银行资产质量等结构化事实。
- `filing_text`: 10-K/10-Q 中的业务描述、MD&A、分部解释和管理层讨论。
- `8k_commentary`: 8-K earnings release / Exhibit 99.x 中的管理层解释、guidance、需求、订单、margin/capex commentary。
- `market_snapshot`: 非实时市场快照、估值、相对收益、回撤和事件窗口。
- `risk_text`: 风险因素、客户集中、监管、周期性和反证。

物理 `RetrievalPlan` 由编译器生成：

```text
EvidenceRequirementPlan
  -> scope validator
  -> route compiler
  -> route-level candidate budget
  -> duplicate route/query merge
  -> retrieval executor
```

### 二次检索原则

最终答案不单独列出“二次检索结果区”。如果二次检索被触发，答案只在正文和证据边界中自然说明：哪些结论来自初始证据，哪些因为补查 10-Q/8-K/market snapshot 后得到加强或降级。

后台 artifact 需要保留：

```text
second_pass_trigger
missing_requirement
searchable_in_current_inventory
expanded_route_scope
candidate_count_delta
coverage_delta
ledger_delta
stage_timing
```

如果二次检索后仍不足，最终答案仍要输出当前证据能够支持的观点和不能强推的观点；只有当前库存外的资料才写成外部缺口。

### 执行步骤

1. 在 `src/sec_agent/retrieval_plan.py` 增加 `build_evidence_requirement_plan()`：
   - 优先读取 planner 输出的 `evidence_requirements` / `evidence_requirement_plan.requirements`；
   - 如果旧合同没有该字段，从 `decomposed_tasks` 派生兼容版，并标记 `source=query_contract_derived_evidence_requirements`；
   - 校验 route 枚举、ticker、year、filing type、source tier、period role 和预算。

2. 修改 `build_retrieval_plan()`：
   - 从 `EvidenceRequirementPlan` 编译物理 route；
   - 只有当 requirement 没有 route 时才派生 route；
   - route 上保留 `evidence_requirement_id`，便于 coverage、second pass 和日志追踪。

3. 修改 API planner prompt：
   - 要求输出短小的 `evidence_requirements`；
   - 不允许输出 evidence id、精确数值或最终答案；
   - 如果 10-Q/8-K/market snapshot 在当前 inventory 中可用，必须进入 requirement，而不是写“建议补查”。

4. 验证当前兼容链路：
   - 旧 case 没有 evidence requirements 时，仍能派生 RetrievalPlan；
   - planner 显式要求 `8k_commentary` 时，物理 route 必须尊重该需求；
   - `ledger_first` 和 `market_snapshot` 仍不进入 BGE。

5. 下一阶段实现 second-pass retrieval：
   - Coverage Matrix 输出 `searchable_in_current_inventory` 缺口；
   - 编译为 scoped evidence requirement；
   - 只重跑相关 route，合并 context rows，重建 ledger、coverage 和 judgment plan。

### 本轮已完成

- `src/sec_agent/retrieval_plan.py`
  - 新增 `EvidenceRequirementPlan` schema 和 normalizer。
  - `build_retrieval_plan()` 改为先构建 evidence requirement，再编译物理 route。
  - 显式 planner requirement 会优先决定 `evidence_routes`；旧合同仍保留派生兼容路径。
  - route 和 task 写入 `evidence_requirement_id` / `evidence_requirement_source`。
- `scripts/cloud/sec_agent_interactive.py`
  - planner system prompt 增加 `evidence_requirements` 合同。
  - LLM planner 输出归一化时保留并裁剪 evidence requirements。
  - planner trace summary 增加 `evidence_requirement_count`。
- `tests/test_sec_agent_retrieval_plan.py`
  - 增加显式 planner evidence requirements 驱动物理 route 的单测。

### 执行器去重补充

在 `scripts/run_sec_benchmark_eval.py` 的 route executor 内增加请求级 search cache：

- cache key: `searcher namespace + normalized query + top_k + normalized filters`。
- 同一轮 context preparation 内，如果多个 evidence requirement 编译出相同的 BM25/ObjectBM25 查询，不再重复调用底层 search。
- `context_policy` 新增 `route_search_cache_entries`，用于观察命中空间。
- 该优化不改变业务 route、不扩大或缩小 source scope，只去掉完全相同物理查询的重复计算。

新增验证：

- `tests/test_sec_agent_retrieval_plan.py::test_route_executor_reuses_identical_route_searches`
  - 两条不同 route id 但相同 query/filter 的 `filing_text` route 只触发一次 BM25 search。
- `python scripts\cloud\sec_agent_interactive.py --plan-only --query-planner heuristic --tickers NVDA,AMD --years 2026 --manifest-path data\processed_private\manifests\sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl --prompt "..."`
  - `query_contract_validation=pass`
  - `retrieval_plan validation=pass`
  - `routes_by_type=8k_commentary=4,filing_text=4,ledger_first=4,risk_text=1`

## 2026-05-28 Second-pass Retrieval v1 实施记录

本轮落实 coverage 驱动的二次检索最小闭环。目标不是给答案加“建议补查”兜底，而是在模型综合前把当前库存内还能查到的 10-K/10-Q/8-K 证据自动补进统一 evidence pack。

### 已实现

- `scripts/cloud/sec_agent_interactive.py`
  - 在 `build_coverage_matrix` 之后、`build_judgment_plan` 之前增加 `second_pass_retrieval` 阶段。
  - 从 Coverage Matrix 中筛选 `support_level=partial|insufficient` 的任务。
  - 只把当前 query contract / inventory 范围内可查的缺口编译成 scoped evidence requirement。
  - 如果缺口已经由 `source_coverage_gaps` 标明为库存缺失，不触发二次检索。
  - 二次检索使用现有 `RetrievalPlan` + route executor，不新增业务兜底规则。
  - 二次检索结果合并到主 `context_rows` 后，重建 runtime ledger 和 Coverage Matrix，再进入 Judgment Plan / synthesis。
  - 后台写入 `second_pass_retrieval_trace.json` 和 `second_pass_retrieval/trace/*`，主回答不单独输出二次检索证据区。

- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - Coverage Matrix prompt compact 增加 `second_pass_retrieval` 摘要。
  - synthesis 约束补充：如果触发二次检索，可以在答案边界中自然说明证据已经按覆盖检查追加检索，但不要输出单独的二次检索章节或内部日志。

- `tests/test_sec_agent_retrieval_plan.py`
  - 增加 coverage 缺口编译为 second-pass requirement 的单测。
  - 增加 source gap 已声明为库存缺失时不触发二次检索的单测。

### 当前边界

- second pass 默认只允许一轮，由 coverage 缺口触发。
- market snapshot 字段缺失不通过 SEC/BGE 二次检索补齐；市场快照缺口仍应由 market evidence 数据产品解决。
- 二次检索只处理当前 source policy 和 query contract 已允许的公司、年份、披露类型、来源层级和指标族。
- 如果二次检索后仍不足，最终答案仍要输出当前证据能支持的观点，同时在 `not_found` / `limitations` / `source_limitations` 中说明证据边界。

### 验证

- `python -m py_compile scripts\cloud\sec_agent_interactive.py scripts\run_sec_eval_synthesis_qwen9b_backend.py`
- `pytest tests\test_sec_agent_retrieval_plan.py -q`
- `pytest tests\test_bm25_retriever.py tests\test_sec_agent_retrieval_plan.py tests\test_sec_agent_ledger_store.py -q`
- `pytest tests\test_market_snapshot_fixture.py::test_interactive_market_context_loader_and_renderer_boundary tests\test_sec_agent_8k_earnings_source.py::test_context_session_forwards_source_gap_path_to_graph_args tests\test_sec_agent_p0_observability.py -q`
- plan-only smoke:
  - `query_contract_validation=pass`
  - `retrieval_plan validation=pass`
  - `routes_by_type=8k_commentary=4,filing_text=4,ledger_first=4,market_snapshot=4,risk_text=1`

下一步应进入 route 级 query 合并/物化与轻量 ledger store 联动：让 EvidenceRequirementPlan 编译后的相同物理 scope 进一步合并，减少 full78/full200 宽问题下的重复 BM25/ObjectBM25 查询，同时保持 coverage reservation 不降级。

## 2026-05-28 Route-level Search Merge + Ledger Store v1 实施记录

本轮开始把 retrieval executor 从“逐 route 直接查索引”改为“EvidenceRequirementPlan 编译 route 后，先合并物理查询，再执行检索”。这一步解决的是候选增长的核心结构问题，不是为本地机器做特化降级。

### 已实现

- `scripts/run_sec_benchmark_eval.py`
  - `pipeline_context` 增加 `--ledger-store-path`，默认读取 `LEDGER_STORE_PATH`。
  - `ledger_first` route 在提供 DuckDB lightweight ledger store 时直接按 ticker / fiscal year / filing type / source tier / metric family / period role 查结构化事实。
  - `ledger_first` 从 ledger store 返回的行标记为 `rerank_eligible=False`，不进入 BGE CrossEncoder。
  - BM25 / ObjectBM25 route 不再逐 route 立即调用 search，而是先编译为 logical search ops。
  - 相同 `namespace + query + filters` 的 logical op 合并为一个 physical search op，`top_k` 取同组最大值，结果再分发回各 route。
  - `context_policy.route_search_merge` 记录：
    - `logical_search_ops`
    - `physical_search_ops`
    - `merged_duplicate_ops`
  - `context_policy.ledger_store_path` 记录本轮是否实际使用 ledger store。

- `src/sec_agent/ledger_store.py`
  - `query_ledger_facts()` 增加 `period_roles` 过滤，支持 `qtd / ytd / ttm / annual` 等口径在 SQL 层筛选。

- local workbench profiles
  - `data/workbench_private/profiles/full_source_wsl.env` 增加 `LEDGER_STORE_PATH`。
  - `data/workbench_private/profiles/mixed_10q_market_wsl.env` 增加 `LEDGER_STORE_PATH`。
  - 这两个 profile 是本机忽略文件，不进入公开仓库；公开文档只说明可配置项，不提交私有路径和数据。

- `tests/test_sec_agent_retrieval_plan.py`
  - 增加 `test_route_executor_uses_ledger_store_for_ledger_first`：
    - 提供 ledger store 后 `ledger_first` 不调用 ObjectBM25。
    - `period_roles=["qtd"]` 只返回 QTD 事实。
  - 保留 `test_route_executor_reuses_identical_route_searches`：
    - 两条相同 physical BM25 查询只触发一次底层 search。

### 当前边界

- 这一步只合并完全相同的物理查询，不改变 planner 给出的业务证据路线和 source scope。
- `ledger_first` 在 ledger store 可用时走结构化事实；如果没有提供 store，仍走既有 ObjectBM25 结构化对象路径。
- 本轮尚未做 route 间 shared evidence attribution，也就是同一条证据命中多条 route 时，当前仍按已有 context row 去重策略处理。后续如果 coverage 需要一条证据显式服务多条 route，应在 row 上增加 `selection_route_ids`，而不是复制证据文本。

### 验证

- `python -m py_compile scripts\run_sec_benchmark_eval.py src\sec_agent\ledger_store.py`
- `pytest tests\test_sec_agent_retrieval_plan.py tests\test_sec_agent_ledger_store.py -q`
- `pytest tests\test_bm25_retriever.py tests\test_sec_agent_retrieval_plan.py tests\test_sec_agent_ledger_store.py -q`
- `python scripts\cloud\sec_agent_interactive.py --plan-only --query-planner heuristic --tickers NVDA,AMD --years 2026 --manifest-path data\processed_private\manifests\sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl --prompt "比较 NVDA 和 AMD 的 AI 基本面、管理层解释和市场反应"`

### Local full78 context-only smoke

命令使用 full78 saved case，显式关闭 BGE 作为 context-only ablation，只验证 candidate generation、route merge、ledger store 和 coverage reservation：

```powershell
python scripts\run_sec_benchmark_eval.py `
  --cases-path eval/sec_cases/outputs/sec_investment_coverage_full78_route_profile/20260528_local_route_context_only/case.jsonl `
  --mode pipeline_context `
  --manifest-path data/processed_private/manifests/sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl `
  --bm25-index-dir data/indexes/bm25/sec_investment_coverage_mixed_with_8k_fy2023_2027 `
  --object-bm25-index-dir data/indexes/bm25/sec_investment_coverage_mixed_with_8k_fy2023_2027_objects `
  --ledger-store-path data/processed_private/ledger/sec_investment_coverage_mixed_with_8k_fy2023_2027_core_ledger.duckdb `
  --context-reranker none `
  --allow-bm25-only-pipeline `
  --output-dir eval/sec_cases/outputs/sec_investment_coverage_full78_route_profile/20260528_local_route_context_after_query_merge
```

结果：

- `status=context_prepared`
- `candidate_generation=1964ms`
- `context_rows=334`
- `source_kind_counts=evidence_object:160, structured_object:174`
- `ledger_methods={'route_ledger_first_ledger_store'}`
- `route_search_merge={logical_search_ops:132, physical_search_ops:132, merged_duplicate_ops:0}`
- `coverage_reservation={enabled:true, reserved_count:75, slot_count:75}`

这次 case 没有完全相同 physical query，所以 `merged_duplicate_ops=0` 是正常结果；单测覆盖了重复 query 合并。核心变化是 ledger-first 不再从 ObjectBM25 冷路径取完整对象 payload，而是直接从 DuckDB facts 取结构化事实。

### Local full78 context-only smoke with BGE

在同一 saved case 上打开 BGE CrossEncoder，验证 route-local candidate budget 是否能避免本机 4060 上的长时间卡顿：

```powershell
python scripts\run_sec_benchmark_eval.py `
  --cases-path eval/sec_cases/outputs/sec_investment_coverage_full78_route_profile/20260528_local_route_context_only/case.jsonl `
  --mode pipeline_context `
  --manifest-path data/processed_private/manifests/sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl `
  --bm25-index-dir data/indexes/bm25/sec_investment_coverage_mixed_with_8k_fy2023_2027 `
  --object-bm25-index-dir data/indexes/bm25/sec_investment_coverage_mixed_with_8k_fy2023_2027_objects `
  --ledger-store-path data/processed_private/ledger/sec_investment_coverage_mixed_with_8k_fy2023_2027_core_ledger.duckdb `
  --context-reranker bge `
  --context-reranker-model D:\hf_cache\hub\models--BAAI--bge-reranker-v2-m3\snapshots\953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e `
  --context-reranker-device cuda `
  --context-reranker-candidate-limit 800 `
  --context-reranker-top-k 120 `
  --output-dir eval/sec_cases/outputs/sec_investment_coverage_full78_route_profile/20260528_local_route_context_after_query_merge_bge
```

结果：

- run wall time: `49.5s`
- `status=context_prepared`
- `candidate_generation=917ms`
- `context_rerank=17544ms`
- `candidate_row_count_pre_rerank=334`
- `candidate_sent_to_bge=160`
- final `context_rows=294`
- `source_kind_counts=structured_object:174, evidence_object:120`
- `route_counts=ledger_first:174, filing_text:92, 8k_commentary:28`
- `coverage_reservation={enabled:true, reserved_count:75, slot_count:75}`
- `route_search_merge={logical_search_ops:132, physical_search_ops:132, merged_duplicate_ops:0}`

结论：

- full78 宽问题在本机 CUDA 上已经不再是 10-20 分钟级别的 BGE 卡顿。
- 当前耗时主要是 BGE 模型冷启动和 160 条文本候选重排；ledger-first 的 174 条结构化事实没有进入 BGE。
- route-level executor 证明了方向正确：先由 EvidenceRequirementPlan 决定业务证据需求，再把结构化数值交给 DuckDB ledger store，文本解释才交给 BGE 精排。
- 后续继续优化应聚焦常驻 runner / reranker 复用和 shared evidence attribution，而不是继续盲目压低 `candidate_limit`。

## 2026-05-28 Shared Evidence Attribution v1 实施记录

route-level executor 进一步补上 shared evidence attribution：同一条 structured object / evidence object 如果被多条 route 命中，不再复制证据文本，而是在同一个 context row 上记录它服务过的 route、task、query 和 method。

### 已实现

- `scripts/run_sec_benchmark_eval.py`
  - context row 增加：
    - `selection_routes`
    - `selection_route_ids`
    - `selection_task_ids`
    - `retrieval_routes`
    - `selection_methods`
    - `selection_queries`
  - BM25 / ObjectBM25 / ledger store duplicate hit 会追加 route attribution，而不是重复追加 row。
  - route stats、route budget、coverage reservation 改为识别 `selection_route_ids` / `selection_routes`。
  - `context_policy.route_search_merge.shared_route_attributions` 记录本轮共享归因次数。

- `tests/test_sec_agent_retrieval_plan.py`
  - 扩展 route executor cache 单测：两条相同 physical BM25 查询只查一次，且同一 evidence row 同时记录两个 `selection_route_ids`。

### 验证

- `python -m py_compile scripts\run_sec_benchmark_eval.py`
- `pytest tests\test_sec_agent_retrieval_plan.py -q`
- `pytest tests\test_bm25_retriever.py tests\test_sec_agent_retrieval_plan.py tests\test_sec_agent_ledger_store.py -q`

### Local full78 context-only smoke after shared attribution

BM25-only ablation：

- `status=context_prepared`
- `candidate_generation=2064ms`
- `context_rows=334`
- `source_kind_counts=structured_object:174, evidence_object:160`
- `multi_route_rows=216`
- `candidate_sent_to_bge=0`
- `route_search_merge={logical_search_ops:132, physical_search_ops:132, merged_duplicate_ops:0, shared_route_attributions:236}`
- `coverage_reservation={enabled:true, reserved_count:80, slot_count:80}`

BGE run：

- run wall time: `50.1s`
- `status=context_prepared`
- `candidate_generation=891ms`
- `context_rerank=17573ms`
- `candidate_row_count_pre_rerank=334`
- `candidate_sent_to_bge=160`
- final `context_rows=294`
- `source_kind_counts=structured_object:174, evidence_object:120`
- `multi_route_rows=203`
- `route_search_merge={logical_search_ops:132, physical_search_ops:132, merged_duplicate_ops:0, shared_route_attributions:236}`
- `coverage_reservation={enabled:true, reserved_count:80, slot_count:80}`

结论：

- 共享归因没有放大 BGE 候选数，仍然只重排 160 条文本候选。
- coverage reservation 的 slot 数从 75 提升到 80，说明同一条证据现在可以被多个 route / task 识别为有效支撑。
- 这一步解决的是 evidence attribution 和 coverage 解释问题，不是简单压缩候选；后续多轮复用时也可以直接复用同一 evidence row 的 route 归因。

下一步应继续做常驻 runner / reranker 复用，以及多轮 session 中复用上一轮 RetrievalPlan、coverage state 和 evidence pack 的 scoped follow-up 检索。

## 2026-05-28 Main-chain Ledger Store Propagation 修复

在 route executor 的直接 smoke 中已经使用了 `--ledger-store-path`，但 interactive 主链路的 context runner 还没有把该参数继续传给 `run_sec_benchmark_eval.py`。这会造成脚本直测走 DuckDB ledger store，而网页 / session 主链路仍可能回到 ObjectBM25 冷路径。

### 已修复

- `scripts/cloud/sec_agent_interactive.py`
  - `_benchmark_context_args()` 增加 `ledger_store_path`，in-process context runner 可以使用 DuckDB ledger store。
  - `_run_context_subprocess()` 在有 `ledger_store_path` 时转发 `--ledger-store-path`。
  - `run_data_fingerprint.json` 记录 `inputs.ledger_store`，后续可以回答“这次 run 使用了哪个 ledger store”。

- `tests/test_sec_agent_retrieval_plan.py`
  - 增加 interactive context args 转发 `ledger_store_path` 的单测。

### 验证

- `python -m py_compile scripts\cloud\sec_agent_interactive.py scripts\run_sec_benchmark_eval.py`
- `pytest tests\test_sec_agent_retrieval_plan.py -q`
- `pytest tests\test_bm25_retriever.py tests\test_sec_agent_retrieval_plan.py tests\test_sec_agent_ledger_store.py tests\test_market_snapshot_fixture.py::test_interactive_market_context_loader_and_renderer_boundary tests\test_sec_agent_8k_earnings_source.py::test_context_session_forwards_source_gap_path_to_graph_args tests\test_sec_agent_p0_observability.py -q`

结论：后续 workbench / session 只要 profile 或环境变量配置了 `LEDGER_STORE_PATH`，主链路的 context retrieval 和 runtime ledger 都会使用同一份 lightweight ledger store。
