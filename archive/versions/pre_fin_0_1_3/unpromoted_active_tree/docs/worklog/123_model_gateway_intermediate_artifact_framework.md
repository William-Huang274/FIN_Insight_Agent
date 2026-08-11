# 123 - Model Gateway 与四个中间产物框架

## 摘要
- 日期：2026-05-21
- 目的：把自由命题 SEC 分析的下一版架构落成可评审框架，重点解决“证据可靠但 insight 不够”的问题。
- 状态：设计草案；本步骤未改代码、未跑实验。
- 范围：模型接入方式、角色路由、四个中间产物、claim-first synthesis、验证闭环、实现顺序。

## 背景问题
当前 interactive constrained chain 已经能把精确数值约束在 SEC evidence boundary 内，也能通过 deterministic gates。但它暴露出一个更本质的问题：

- 回答容易像 benchmark trace，安全但 insight 少；
- Judgment Plan 被压缩后，模型只能围绕少数 drivers 写，难展开产业判断；
- 模型有时会写出漂亮但无证据支撑的语义判断，例如“结构性调整与地缘政治风险”；
- 当前链路把“理解用户问题、规划证据、生成 insight”压进同一个 synthesis 调用，职责过重。

所以 vNext 不应该继续堆兜底规则。应该把自由 query 先变成可检索、可验证、可降级的任务协议，再让更强模型在可靠证据范围内做 insight synthesis。

## 目标链路

```text
User Prompt
  -> Query Rewrite / Task Decomposition
  -> Query Contract
  -> Retrieval Plan + SEC Retrieval + BGE-M3 Rerank
  -> Evidence Pack
  -> Exact-Value Ledger
  -> Judgment Plan
  -> Claim-First Synthesis
  -> Claim Verification
  -> User-Facing Answer Renderer
  -> Deterministic Gates + Trace
```

四个稳定中间产物是：

1. `Query Contract`
2. `Evidence Pack`
3. `Exact-Value Ledger`
4. `Judgment Plan`

最终答案不是事实来源。最终答案只是 verified claims 的用户可读渲染。

## 模型接入原则

模型接入层应该变成 `LLM Gateway + Role Router`，而不是在业务脚本里直接写 Qwen、DeepSeek 或某个 API 的调用细节。

核心原则：

- provider 可替换：`qwen_vllm`、`deepseek`、`openai_compatible`、未来本地 27B 都走同一内部接口。
- role 决定模型：不是“用哪个供应商”，而是“这个阶段需要哪种模型能力”。
- evidence 不交给模型自由编造：模型可以理解、规划、组织和表达，但不能独立创造事实。
- verifier 不能完全依赖同一个生成模型自证：claim 生成和 claim 验证要解耦。
- trace 必须可复现：记录模型、prompt hash、context hash、latency、tokens、cost、解析状态和失败原因。
- 密钥只读环境变量：日志、worklog、trace、config 都不能写入 API key、SSH 密码或临时凭证。

## LLM Gateway Contract

所有模型调用统一成一个内部请求结构：

```json
{
  "role": "rewriter | planner | synthesizer | verifier | renderer",
  "profile": "deepseek_v4_pro | qwen9b_vllm | openai_compatible | future_27b",
  "model": "provider model name",
  "base_url": "provider endpoint without secrets",
  "api_key_env": "environment variable name only",
  "messages": [],
  "response_schema": {},
  "temperature": 0.0,
  "max_tokens": 4000,
  "timeout_s": 180,
  "stream": false,
  "reasoning_mode": "disabled | enabled | provider_default",
  "trace_tags": {
    "run_id": "...",
    "artifact_id": "...",
    "prompt_hash": "...",
    "context_hash": "..."
  }
}
```

所有调用结果统一写出：

```json
{
  "status": "ok | timeout | parse_failed | provider_error | schema_failed",
  "raw_text_path": "...",
  "parsed_json_path": "...",
  "latency_ms": 0,
  "input_tokens": 0,
  "output_tokens": 0,
  "cost_estimate": null,
  "provider": "deepseek | qwen_vllm | openai_compatible",
  "model": "...",
  "failure_reason": ""
}
```

DeepSeek 当前默认应关闭 thinking。原因不是它不需要推理，而是本链路已经给了 evidence、ledger、plan 和 verifier；默认 thinking 会显著增加不可控等待时间，且不利于交互测试。需要高推理时再显式打开。

## 模型 Profile

| Profile | 当前用途 | 优点 | 风险 |
| --- | --- | --- | --- |
| `qwen9b_vllm` | 本地/云端 baseline、无 API 回归、成本对照 | 可控、可复现、常驻后边际成本低 | 宽问题 insight ceiling 明显，JSON 稳定性一般 |
| `deepseek_v4_pro` | planner 与高质量 synthesis 主线 | 更快达到可用 insight，适合验证生产力上限 | 外部 API 成本、延迟和服务行为变化 |
| `openai_compatible` | 后续其他 API 模型抽象 | 便于替换供应商 | 每家兼容细节要单独验 |
| `future_27b_local` | 后续更大显卡或量化部署测试 | 本地强模型候选 | 显存、上下文、吞吐、部署复杂度不确定 |

## Role Router

| Role | 职责 | 当前建议模型 | 验证归属 |
| --- | --- | --- | --- |
| `rewriter` | 将用户自由 prompt 改写为标准财经分析请求，识别歧义 | DeepSeek Pro 或 fast API model | Query Contract validator |
| `decomposer` | 拆出 growth、margin、capex、risk、comparability 等子任务 | DeepSeek Pro | scope/ontology validator |
| `planner` | 选择公司、年份、facets、metric families、required caveats、evidence needs | DeepSeek Pro；Qwen9B 只作 diagnostic fallback | planner contract validator |
| `retriever` | SEC chunk/object 检索与 rerank | BM25/ObjectBM25 + BGE-M3 | retrieval coverage report |
| `ledger_builder` | 构造精确数值账本与 allowed claim roles | deterministic scripts | ledger unit/source/role gates |
| `judgment_planner` | 把 evidence/ledger 转成可回答的 driver plan | deterministic first；后续可 model-assisted draft + deterministic validate | judgment-plan validator |
| `synthesizer` | 基于四个产物生成候选 claims 和解释 | DeepSeek Pro 主线；Qwen9B baseline；未来 27B 对照 | claim verifier + post-gates |
| `verifier` | 检查每条 claim 是否被 ledger/evidence 支撑，决定通过、降级或删除 | deterministic first；可加小模型 critic | deterministic gates 最终裁决 |
| `renderer` | 将 verified claims 渲染为用户可读中文答案 | deterministic renderer；可选轻量模型润色 | display sanitizer |

这意味着：Qwen9B、DeepSeek、未来 27B 不是互斥路线。它们应该在同一组中间产物上做 A/B，对比的是模型在相同证据边界内的 insight 能力。

## Artifact 1: Query Contract

`Query Contract` 是用户问题的任务协议，不是答案模板。

### 生产者
- `rewriter/decomposer/planner` 模型。
- deterministic normalizer 把 ticker/year/metric family clamp 到现有 SEC universe 和 ontology。

### 建议 schema

```json
{
  "schema_version": "query_contract_v1",
  "contract_id": "interactive_20260521_<hash>",
  "original_prompt": "...",
  "rewritten_question_zh": "...",
  "task_type": "ai_industry_financial_trend | company_comparison | metric_table | risk_summary | open_analysis",
  "scope": {
    "universe_tickers": ["ALL or manifest tickers"],
    "focus_tickers": ["NVDA", "AMZN"],
    "years": [2023, 2024, 2025],
    "sec_sections": ["Item 1", "Item 1A", "Item 7", "Item 8"]
  },
  "decomposed_tasks": [
    {
      "task_id": "growth_quality",
      "question_zh": "AI需求是否反映在云、数据中心和半导体收入增长中？",
      "priority": "primary",
      "required_metric_families": ["cloud_revenue", "data_center_revenue", "semiconductor_revenue"]
    }
  ],
  "analysis_axes": ["growth", "profitability", "capital_intensity", "segment_mix", "risk", "comparability"],
  "required_caveats": [
    "SEC-only evidence boundary",
    "segment labels are not directly comparable across companies"
  ],
  "forbidden_claims": [
    "macroeconomic claim without SEC evidence",
    "geopolitical risk claim without retrieved risk-factor support"
  ],
  "planner_confidence": "high | medium | low"
}
```

### Gate
- ticker/year 必须存在于 manifest；
- metric family 必须存在于 ontology；
- 宽问题必须拆出至少两个 explicit subquestions；
- forbidden claims 和 required caveats 必须传到后续阶段；
- 这里不能出现精确数字、metric IDs 或最终结论。

## Artifact 2: Evidence Pack

`Evidence Pack` 是检索与 rerank 后的 SEC 支撑集合。它不应只有数字表格，还要包含能支撑定性判断的文本证据、风险因素、披露边界和缺口。

### 生产者
- BM25/ObjectBM25 candidate generation。
- BGE-M3 rerank。
- 可选 coverage balancer，按 task/ticker/year 做覆盖均衡。

### 建议 schema

```json
{
  "schema_version": "evidence_pack_v1",
  "contract_id": "...",
  "retrieval_profile": {
    "bm25_top_k": 120,
    "object_top_k": 120,
    "bge_model": "BAAI/bge-reranker-v2-m3",
    "bge_device": "cuda",
    "reranker_top_k": 120
  },
  "coverage_matrix": [
    {
      "task_id": "growth_quality",
      "ticker": "NVDA",
      "year": 2025,
      "coverage": "direct | partial | missing",
      "evidence_ids": ["..."]
    }
  ],
  "evidence_items": [
    {
      "evidence_id": "NVDA_2025_10K_ITEM7_BLOCK_0001",
      "ticker": "NVDA",
      "year": 2025,
      "section": "Item 7",
      "support_type": "numeric | qualitative | risk | caveat | background",
      "task_ids": ["growth_quality"],
      "metric_family_candidates": ["data_center_revenue"],
      "bge_score": 0.0,
      "source_text": "bounded excerpt or pointer"
    }
  ],
  "evidence_gaps": [
    {
      "task_id": "risk_comparability",
      "ticker": "AMAT",
      "gap": "no retrieved risk-factor support for geopolitical claim"
    }
  ]
}
```

### Gate
- 每个 evidence item 必须映射到 manifest-backed source；
- final answer 不能引用 pack 外证据；
- 宽问题必须报告 task/ticker/year coverage；
- qualitative evidence 缺失时要降级语义 claim，而不是用泛化兜底话术补上。

## Artifact 3: Exact-Value Ledger

`Exact-Value Ledger` 是精确数值唯一来源。

### 生产者
- deterministic structured object parser + ledger builder。
- 模型最多辅助命名或建议标签，不能绕过 deterministic source grounding 提升数值。

### 建议 schema

```json
{
  "schema_version": "exact_value_ledger_v1",
  "contract_id": "...",
  "rows": [
    {
      "metric_id": "INTERACTIVE_<run>::NVDA::2025::data_center_revenue::total_value",
      "ticker": "NVDA",
      "year": 2025,
      "metric_family": "data_center_revenue",
      "metric_label_zh": "NVIDIA 计算与网络分部收入",
      "metric_role": "total_value | period_change | percentage_rate | derived_proxy",
      "display_value_zh": "116,193（百万美元）",
      "raw_value_text": "116,193",
      "unit": "usd_millions",
      "source_evidence_id": "NVDA_2025_10K_ITEM7_BLOCK_...",
      "allowed_claim_roles": ["state_value", "compare_trend"],
      "disallowed_claim_roles": ["gross_margin", "cash_flow"]
    }
  ]
}
```

### Gate
- unit 与 display value 必须匹配 source；
- metric role 必须匹配表格/文本上下文；
- derived value 必须带公式和来源 rows；
- final numeric prose 必须逐字使用 ledger display value；
- ledger 外精确数字直接拒绝、降级或删除。

## Artifact 4: Judgment Plan

`Judgment Plan` 决定最终答案允许论证什么。它不是固定 insight 规则库，而是 evidence 到 answerable claims 的 ranked map。

### 生产者
- v1 优先 deterministic builder：从 Query Contract、Evidence Pack、Exact-Value Ledger 生成。
- 后续可让模型先 draft plan，再由 deterministic validator 过滤和降级。

### 建议 schema

```json
{
  "schema_version": "judgment_plan_v1",
  "contract_id": "...",
  "answer_intent": "explain AI industry financial trend from 2023 to 2025 under SEC-only evidence",
  "drivers": [
    {
      "driver_id": "cloud_and_data_center_growth",
      "rank": 1,
      "claim_to_test_zh": "云和数据中心需求是AI财务扩张的主要可见载体。",
      "support_strength": "strong | medium | weak",
      "required_metric_ids": ["..."],
      "required_evidence_ids": ["..."],
      "allowed_scope": {
        "tickers": ["AMZN", "MSFT", "GOOGL", "NVDA"],
        "years": [2023, 2024, 2025]
      },
      "downgrade_rules": [
        "If only one company has direct support, render as company-level observation, not industry conclusion."
      ],
      "forbidden_extensions": [
        "Do not mention geopolitical risk unless risk-factor evidence is attached."
      ]
    }
  ],
  "required_limitations": [
    "SEC-only evidence boundary",
    "segment labels differ by company"
  ],
  "answer_budget": {
    "max_core_claims": 6,
    "max_supporting_points": 10,
    "target_style": "investor memo, not benchmark trace"
  }
}
```

### Gate
- 每个 driver 必须有 evidence support 或 downgrade rule；
- support strength 不能高于 evidence coverage；
- final claim 必须映射到 plan driver，否则标记为 unsupported 并删除；
- caveat 要绑定真实比较限制，不能是泛泛免责声明。

## Claim-First Synthesis

最终模型不应该直接写完整答案，而是先输出结构化 claims：

```json
{
  "schema_version": "claim_synthesis_v1",
  "claims": [
    {
      "claim_id": "c1",
      "driver_id": "cloud_and_data_center_growth",
      "claim_zh": "云和数据中心收入增长是2023-2025年AI需求最清晰的财务映射。",
      "support_type": "ledger_and_text",
      "metric_ids": ["..."],
      "evidence_ids": ["..."],
      "scope": {"tickers": ["AMZN", "NVDA"], "years": [2023, 2024, 2025]},
      "confidence": "high | medium | low",
      "limitations": ["segment labels differ across companies"]
    }
  ],
  "answer_draft_zh": "optional draft prose"
}
```

然后 verifier 对每条 claim 做三种处理：

- `promote`: 证据充分，进入最终答案；
- `downgrade`: 证据部分支持，只能写成弱判断或公司级观察；
- `reject`: 无支撑，不能渲染。

这能直接解决“模型写出无证据的漂亮话”的问题。比如“地缘政治风险”只有在 Evidence Pack 里有 risk-factor evidence，且 Judgment Plan 有对应 risk driver 时，才允许进入最终答案。

## 执行模式

| Mode | 目的 | 模型路线 |
| --- | --- | --- |
| `local_baseline` | 无 API、可复现回归 | BGE-M3 + Qwen9B |
| `api_quality` | 同一证据产物下验证高质量输出 | BGE-M3 + DeepSeek Pro |
| `model_ablation` | 对比 Qwen9B、DeepSeek、未来 27B | 固定四个中间产物，只替换 synthesizer |
| `interactive_prod_like` | 用户自由命题体验 | cached retrieval/ledger + role router + user-facing renderer |

模型对比必须固定四个中间产物。否则输出差异可能来自检索、ledger 或 plan 差异，而不是模型能力差异。

## 质量指标

下一版 benchmark 不能只看 deterministic gates 是否全绿，还要看“有用 insight”。

建议指标：

- `query_contract_pass`: schema、scope、ontology、decomposition 是否通过；
- `retrieval_coverage_rate`: required task/ticker/year cells 是否有 direct/partial evidence；
- `ledger_exactness_pass`: 数值 source、unit、role、display value 是否正确；
- `claim_support_rate`: verified claims / generated claims；
- `unsupported_claim_rate`: 无证据 claims 比例；
- `insight_density`: 每 1000 中文字符中 verified non-trivial claims 数；
- `comparability_caveat_quality`: caveat 是否绑定真实 metric/segment 差异；
- `answer_readability`: 终端输出是否像分析师回答，而不是内部 trace；
- `latency_s`: 端到端和分阶段耗时；
- `cost_per_answer`: API token 成本或本地 GPU wall-time proxy。

当前项目最应该联合看两个指标：`claim_support_rate` 与 `insight_density`。安全但空洞、丰富但无支撑，都不应通过。

## 实现顺序

### Step 1: 冻结四个 artifact schema
- 增加 JSON schema 或轻量 validator。
- 保持当前 interactive artifacts 兼容，先不要大改数据路径。

### Step 2: 抽出 `LLM Gateway`
- 把 DeepSeek/Qwen/OpenAI-compatible 请求逻辑从 `scripts/cloud/sec_agent_interactive.py` 移出。
- 统一 timeout、thinking、stream、tokens、parse、trace。
- 所有 provider 只通过环境变量读 key。

### Step 3: 增加 `Role Router`
- 用 config 映射 role 到 model profile。
- 默认：
  - `rewriter/planner/synthesizer`: DeepSeek Pro in `api_quality` mode；
  - `retriever/ledger/judgment_plan`: deterministic + BGE-M3；
  - `verifier`: deterministic first；
  - `baseline`: Qwen9B 跑同一 artifact inputs。

### Step 4: 替换 heuristic free-query planner
- 当前 `plan/preview` 先保留，但要升级成真实 `Query Contract` planner。
- deterministic clamps 保证模型不能选不存在的 tickers、years、metric families。

### Step 5: 加 claim-first synthesis
- synthesizer 先输出 `claims[]`。
- verifier 根据 Judgment Plan、Evidence Pack、Exact-Value Ledger 对每条 claim promote/downgrade/reject。
- renderer 只渲染 verified/downgraded claims。

### Step 6: 做 A/B 评估
- 固定同一批 full30/free-query artifacts。
- 对比 Qwen9B 与 DeepSeek Pro。
- 报告 support rate、insight density、readability、latency、cost。

## 非目标
- 不继续把“AI、银行、医药、能源”等行业 insight 固化成大量 if/else。
- 不用强模型绕过证据 gates。
- 不让 deterministic gates 把所有答案压成 benchmark 报告风格。
- 不在任何文件里保存 API key 或 SSH 凭证。
- 不把 model-generated planner 当可信事实，必须通过 deterministic validator。

## 当前决策建议
采用 role-routed 模型架构，让四个中间产物成为稳定协议。这样 DeepSeek、Qwen9B、未来本地 27B 或其他 OpenAI-compatible API 都只是模型 profile 的替换，不改变检索、ledger、judgment plan 和 gate 语义。

下一步实现优先级应该是：

1. `LLM Gateway`
2. validated `Query Contract` planner
3. claim-first synthesis + claim verifier

这三步最直接对应当前目标：在可靠 SEC 证据边界内，提高模型输出的 insight 质量，而不是继续靠兜底规则把答案修到能过 gate。
