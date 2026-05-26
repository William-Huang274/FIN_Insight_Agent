# SEC Agent Multi-Turn Tool Harness Eval Case Generation Prompt

Use this document as a copy-paste prompt for GPT-5.5 or another strong model to generate evaluation cases for the DeepSeek tool-call controller and session-aware harness.

## Why The Existing Full30 Is Not Enough

The current `sec_free_query_memo_quality_eval_full30_candidate_v1.jsonl` is useful as a single-turn memo content coverage set. It tests:

- ticker / sector coverage;
- memo quality;
- source-boundary handling;
- peer/entity bleed;
- Judgment Plan and deterministic gates;
- SEC-only financial evidence grounding.

It does not test the new enterprise-agent scenario:

- multi-turn conversation state;
- follow-up scope revision;
- non-contiguous sessions;
- user/session isolation;
- tool selection;
- artifact reuse;
- artifact invalidation;
- no-rerun evidence inspection;
- synthesis-only reformatting;
- resume behavior after interrupted runs.

The next eval should therefore be a small multi-turn harness/tool-call eval, not another single-turn full30 memo set.

## Current Project State

We are building a SEC-only investment memo agent in `FIN_Insight_Agent`.

The stable single-run memo DAG is:

```text
user query
-> Query Contract planner
-> SEC retrieval / BM25 / ObjectBM25 / BGE rerank
-> Runtime Exact-Value Ledger
-> Evidence Coverage Matrix
-> Judgment Plan
-> DeepSeek api_memo_v1 synthesis
-> claim-first verification
-> deterministic gates
-> render answer
-> sec_agent_state.json / artifact refs
```

The latest 5-case DeepSeek memo eval passed:

- `5/5` all-gates green
- `12/12` gates per case
- `mean_memo_quality=0.88312`

We have also added a session-aware tool harness v0:

- `src/sec_agent/tool_harness.py`
- `scripts/cloud/sec_agent_tool_harness.py`

Available high-level tools:

```text
start_memo_analysis
revise_memo_scope
explain_evidence
inspect_coverage
reformat_answer
resume_analysis
get_session_state
```

Important boundary:

- DeepSeek should choose tools and arguments.
- The harness executes tools, owns session state, validates source policy, tracks artifact refs, applies invalidation rules, and runs deterministic gates.
- DeepSeek must not bypass retrieval, ledger, Judgment Plan, or gates by writing unsupported final prose.

## Evaluation Goal

Generate 3-5 multi-turn evaluation scenarios that test whether the controller + harness can manage enterprise-agent context, not just produce a good single memo.

The eval should test:

- correct tool choice per user turn;
- correct session continuity;
- correct behavior for non-contiguous sessions;
- correct scope revision and artifact invalidation;
- correct no-rerun behavior for evidence/coverage questions;
- correct reformat behavior without rerunning retrieval/ledger/Judgment Plan;
- correct resume behavior after a simulated interruption;
- correct refusal or source-boundary handling when the user asks for stock price, current-quarter, market-share, or news-based facts;
- protection against cross-session state leakage.

## Allowed Data Universe

Use only these tickers and fiscal years `2023`, `2024`, and `2025`.

```text
MSFT, AAPL, NVDA, GOOGL, META, AMZN,
AVGO, CSCO, INTC, AMD, QCOM, TXN, AMAT, MU,
INTU, ADP, ADBE, PANW, CRWD, SNOW,
JPM, V,
JNJ, LLY,
CAT, GE,
WMT, PG,
XOM, CVX
```

Allowed source policy: `SEC_ONLY_10K`.

Do not require:

- stock prices;
- valuation multiples;
- analyst consensus;
- earnings calls;
- news;
- 10-Q;
- 8-K;
- current-quarter data;
- 2026 data;
- external market-share data.

When the user asks for those, the expected behavior should be a source-boundary response or a conservative SEC-only analysis, not external retrieval.

## Tool Semantics To Test

### `start_memo_analysis`

Use for a new investment memo request.

Expected effect:

- starts or registers a new analysis;
- uses `SEC_ONLY_10K`;
- for `execute=true`, runs the existing fixed DAG;
- for `execute=false`, creates a planned analysis only.

### `revise_memo_scope`

Use when a follow-up modifies company/year/source scope.

Examples:

- "把 AMD 加进来"
- "只看 2024-2025"
- "不要同行，只看公司本身"

Expected invalidation:

```text
query_contract
retrieved_context
runtime_exact_value_ledger
evidence_coverage_matrix
judgment_plan
evidence_pack
memo_answer
claim_verification
deterministic_gates
rendered_answer
```

### `explain_evidence`

Use when the user asks where a prior claim/driver/number came from.

Expected behavior:

- no retrieval rerun;
- no synthesis rerun;
- read prior `memo_answer`, `runtime_exact_value_ledger`, `judgment_plan`, and `evidence_pack`;
- return metric/evidence IDs and compact source explanation.

### `inspect_coverage`

Use when the user asks whether evidence coverage is complete or what is missing.

Expected behavior:

- no retrieval rerun;
- read prior Evidence Coverage Matrix;
- return covered/missing tickers, years, peer tickers, metric families, and source limitations.

### `reformat_answer`

Use when the user only changes output style.

Examples:

- "改成给 PM 的 5 bullet"
- "压缩成投资委员会 memo"
- "保留证据，语气更保守"

Expected invalidation:

```text
rendered_answer
```

If a future implementation performs synthesis-only execution, it should not rerun retrieval, ledger, coverage, or Judgment Plan.

### `resume_analysis`

Use when a run is incomplete or has missing artifacts.

Expected behavior:

- inspect `sec_agent_state.json`;
- identify `next_ready_node`;
- resume from the first missing or invalid artifact;
- preserve provider/model route from state.

### `get_session_state`

Use before deciding a follow-up tool when the user references prior analysis:

- "刚才那个"
- "继续上次"
- "第二条证据"
- "换成 5 bullet"

Expected behavior:

- return compact session state;
- no graph rerun.

## Desired Scenario Count

Generate exactly 5 scenarios.

Each scenario should contain 3-5 turns.

Required distribution:

1. **Continuous scope revision scenario**
   - Start with a new memo.
   - Follow up by adding/removing a ticker or changing years.
   - Then inspect coverage or explain evidence.

2. **No-rerun artifact inspection scenario**
   - Start from a completed analysis precondition.
   - Ask where a claim or number came from.
   - Ask whether evidence coverage is complete.
   - Expected tools should be `explain_evidence` and `inspect_coverage`, not `start_memo_analysis`.

3. **Reformat-only scenario**
   - Start from a completed memo.
   - Ask to convert the answer to PM bullets or IC memo format.
   - Expected tool: `reformat_answer`.
   - Expected rerun policy: no retrieval/ledger/coverage/Judgment Plan rerun.

4. **Non-contiguous session isolation scenario**
   - Include two sessions or two users.
   - User returns to an older session after an unrelated session happened.
   - Expected behavior: correct `session_id` and no cross-session artifact leakage.

5. **Interrupted/resume scenario**
   - Start from a simulated partial run where memo/gates or coverage artifacts are missing.
   - User says "继续刚才没跑完的".
   - Expected tool: `resume_analysis`.
   - Expected resume node should be specified, such as `synthesize_memo` or `build_coverage_matrix`.

At least one scenario should include a source-boundary request, such as:

- "现在值得买吗"
- "最新需求怎么样"
- "市占率是多少"
- "最近安全事件导致流失了吗"

Expected behavior: stay inside `SEC_ONLY_10K` and call the correct tool; do not request external/news tools.

## Output Schema

Return one JSON object per scenario using this shape:

```json
{
  "scenario_id": "multiturn_tool_<short_topic>_001",
  "category": "continuous_scope_revision | no_rerun_artifact_inspection | reformat_only | session_isolation | interrupted_resume",
  "purpose": "What this scenario is testing.",
  "initial_state": {
    "session_id": "s_tool_001",
    "user_id": "u_research_001",
    "tenant_id": "tenant_demo",
    "precondition": "new_session | completed_analysis | partial_analysis | two_sessions",
    "active_answer_id": "",
    "available_artifacts": [],
    "missing_artifacts": []
  },
  "turns": [
    {
      "turn_id": "t1",
      "user_message": "Natural Chinese user message.",
      "expected_intent": "new_analysis | revise_scope | explain_evidence | inspect_coverage | reformat | resume | source_boundary",
      "expected_tool": "start_memo_analysis | revise_memo_scope | explain_evidence | inspect_coverage | reformat_answer | resume_analysis | get_session_state",
      "expected_arguments": {
        "source_policy": "SEC_ONLY_10K"
      },
      "expected_rerun_policy": {
        "should_rerun_retrieval": false,
        "should_rerun_ledger": false,
        "should_rerun_coverage": false,
        "should_rerun_judgment_plan": false,
        "should_rerun_synthesis": false,
        "should_run_gates": false
      },
      "expected_preserved_artifacts": [],
      "expected_invalidated_artifacts": [],
      "success_criteria": [
        "Observable condition for this turn."
      ]
    }
  ],
  "scenario_success_criteria": [
    "Overall condition for passing the scenario."
  ],
  "failure_modes_to_catch": [
    "Examples of bad behavior this scenario should catch."
  ]
}
```

## Field Guidance

### `expected_arguments`

Include only stable expectations. Do not over-constrain natural language.

Good:

```json
{
  "session_id": "s_tool_001",
  "add_tickers": ["AMD"],
  "years": [2024, 2025],
  "source_policy": "SEC_ONLY_10K"
}
```

Bad:

```json
{
  "query": "must match this exact long rewritten query"
}
```

### `expected_rerun_policy`

For a new analysis:

```json
{
  "should_rerun_retrieval": true,
  "should_rerun_ledger": true,
  "should_rerun_coverage": true,
  "should_rerun_judgment_plan": true,
  "should_rerun_synthesis": true,
  "should_run_gates": true
}
```

For `explain_evidence`:

```json
{
  "should_rerun_retrieval": false,
  "should_rerun_ledger": false,
  "should_rerun_coverage": false,
  "should_rerun_judgment_plan": false,
  "should_rerun_synthesis": false,
  "should_run_gates": false
}
```

For `reformat_answer`:

```json
{
  "should_rerun_retrieval": false,
  "should_rerun_ledger": false,
  "should_rerun_coverage": false,
  "should_rerun_judgment_plan": false,
  "should_rerun_synthesis": true,
  "should_run_gates": true
}
```

If the current v0 only records a reformat request, write success criteria that accept a planned reformat request but still specify the future intended rerun policy.

### `expected_invalidated_artifacts`

For scope revision, include:

```text
query_contract
retrieved_context
runtime_exact_value_ledger
evidence_coverage_matrix
judgment_plan
evidence_pack
memo_answer
claim_verification
deterministic_gates
rendered_answer
```

For reformat-only, include:

```text
rendered_answer
```

For evidence/coverage inspection, include an empty list.

## Case Quality Rules

Good scenarios:

- model realistic enterprise analyst behavior;
- include pronouns or references like "刚才", "第二条", "继续上次";
- force the controller to choose between starting a new analysis and using existing session state;
- include one source-boundary question;
- test no-rerun artifact tools;
- specify expected tools clearly but do not require exact prose.

Bad scenarios:

- only contain unrelated single-turn memo questions;
- require external facts;
- require current market data;
- over-constrain the final memo wording;
- make every turn a new `start_memo_analysis`;
- ignore `session_id` / `user_id`.

## Required Final Output

Return two sections:

1. A compact scenario table:
   - `scenario_id`
   - category
   - turn count
   - expected tool sequence
   - state behavior tested

2. A fenced `json` block containing an array of exactly 5 scenario objects.

Before finalizing, self-check:

- exactly 5 scenarios;
- each scenario has 3-5 turns;
- every turn has `expected_tool`;
- at least one scenario uses `revise_memo_scope`;
- at least one scenario uses `explain_evidence`;
- at least one scenario uses `inspect_coverage`;
- at least one scenario uses `reformat_answer`;
- at least one scenario uses `resume_analysis`;
- at least one scenario uses `get_session_state`;
- at least one scenario tests source-boundary behavior;
- at least one scenario tests non-contiguous session isolation;
- no scenario requires external sources;
- no scenario expects DeepSeek to bypass harness/gates.

## Prompt To Use

Copy everything below into GPT-5.5.

```text
You are designing evaluation scenarios for a SEC-only investment memo agent with a DeepSeek tool-call controller and a session-aware Python harness.

Project state:
- The stable memo DAG is: Query Contract planner -> SEC retrieval/BM25/ObjectBM25/BGE rerank -> Runtime Exact-Value Ledger -> Evidence Coverage Matrix -> Judgment Plan -> DeepSeek api_memo_v1 synthesis -> claim-first verification -> deterministic gates -> rendered answer -> sec_agent_state/artifact refs.
- The latest reviewed 5-case memo eval passed 5/5 all-gates green, 12/12 gates per case, mean memo quality 0.88312.
- A v0 tool harness now exists with high-level tools: start_memo_analysis, revise_memo_scope, explain_evidence, inspect_coverage, reformat_answer, resume_analysis, get_session_state.
- DeepSeek should choose high-level tool calls. The harness executes tools, owns session state, applies source policy, tracks artifacts, invalidates stale nodes, and runs deterministic gates.
- We need a small multi-turn eval to test controller/harness behavior, not another single-turn memo-quality full30.

Allowed tickers:
MSFT, AAPL, NVDA, GOOGL, META, AMZN,
AVGO, CSCO, INTC, AMD, QCOM, TXN, AMAT, MU,
INTU, ADP, ADBE, PANW, CRWD, SNOW,
JPM, V,
JNJ, LLY,
CAT, GE,
WMT, PG,
XOM, CVX

Allowed years: 2023, 2024, 2025.
Allowed source policy: SEC_ONLY_10K.
Disallowed dependencies: stock prices, valuation multiples, analyst consensus, earnings calls, news, 10-Q, 8-K, current-quarter data, 2026 data, external market-share data.

Generate exactly 5 multi-turn evaluation scenarios. Each scenario must have 3-5 turns.

Required scenario distribution:
1. Continuous scope revision: start a memo, revise ticker/year scope, then inspect coverage or explain evidence.
2. No-rerun artifact inspection: from a completed analysis, ask where a claim/number came from and whether coverage is complete.
3. Reformat-only: from a completed memo, ask for PM bullets or investment committee memo format without rerunning retrieval/ledger/coverage/Judgment Plan.
4. Non-contiguous session isolation: include two sessions or two users; ensure the controller uses the right session and does not leak artifacts.
5. Interrupted/resume: simulated partial run with missing artifacts; user asks to continue; expected tool is resume_analysis.

At least one scenario must include a source-boundary request such as "现在值得买吗", "最新需求怎么样", "市占率是多少", or "最近安全事件导致流失了吗". Expected behavior must stay inside SEC_ONLY_10K and must not request external/news tools.

Use this JSON object shape for each scenario:
{
  "scenario_id": "multiturn_tool_<short_topic>_001",
  "category": "continuous_scope_revision | no_rerun_artifact_inspection | reformat_only | session_isolation | interrupted_resume",
  "purpose": "What this scenario is testing.",
  "initial_state": {
    "session_id": "s_tool_001",
    "user_id": "u_research_001",
    "tenant_id": "tenant_demo",
    "precondition": "new_session | completed_analysis | partial_analysis | two_sessions",
    "active_answer_id": "",
    "available_artifacts": [],
    "missing_artifacts": []
  },
  "turns": [
    {
      "turn_id": "t1",
      "user_message": "Natural Chinese user message.",
      "expected_intent": "new_analysis | revise_scope | explain_evidence | inspect_coverage | reformat | resume | source_boundary",
      "expected_tool": "start_memo_analysis | revise_memo_scope | explain_evidence | inspect_coverage | reformat_answer | resume_analysis | get_session_state",
      "expected_arguments": {
        "source_policy": "SEC_ONLY_10K"
      },
      "expected_rerun_policy": {
        "should_rerun_retrieval": false,
        "should_rerun_ledger": false,
        "should_rerun_coverage": false,
        "should_rerun_judgment_plan": false,
        "should_rerun_synthesis": false,
        "should_run_gates": false
      },
      "expected_preserved_artifacts": [],
      "expected_invalidated_artifacts": [],
      "success_criteria": [
        "Observable condition for this turn."
      ]
    }
  ],
  "scenario_success_criteria": [
    "Overall condition for passing the scenario."
  ],
  "failure_modes_to_catch": [
    "Examples of bad behavior this scenario should catch."
  ]
}

Important expectations:
- For a new analysis, expected tool is start_memo_analysis and the rerun policy should run retrieval, ledger, coverage, Judgment Plan, synthesis, and gates.
- For scope changes, expected tool is revise_memo_scope and the invalidated artifacts should include query_contract, retrieved_context, runtime_exact_value_ledger, evidence_coverage_matrix, judgment_plan, evidence_pack, memo_answer, claim_verification, deterministic_gates, rendered_answer.
- For evidence questions, expected tool is explain_evidence and no graph stages should rerun.
- For coverage questions, expected tool is inspect_coverage and no graph stages should rerun.
- For reformat-only requests, expected tool is reformat_answer; do not rerun retrieval, ledger, coverage, or Judgment Plan.
- For interrupted runs, expected tool is resume_analysis and the expected resume node should be specified in success criteria.
- Use get_session_state when the user references prior context ambiguously, such as "刚才", "继续上次", or "第二条".
- Never expect DeepSeek to manually bypass the harness, invent external facts, or self-certify gates.

Return two sections:
1. A compact scenario table with scenario_id, category, turn count, expected tool sequence, and state behavior tested.
2. A fenced json block containing an array of exactly 5 scenario objects.

Self-check:
- exactly 5 scenarios;
- each scenario has 3-5 turns;
- every turn has expected_tool;
- at least one scenario uses revise_memo_scope;
- at least one scenario uses explain_evidence;
- at least one scenario uses inspect_coverage;
- at least one scenario uses reformat_answer;
- at least one scenario uses resume_analysis;
- at least one scenario uses get_session_state;
- at least one scenario tests source-boundary behavior;
- at least one scenario tests non-contiguous session isolation;
- no scenario requires external sources;
- no scenario expects DeepSeek to bypass harness/gates.
```

## After GPT-5.5 Returns Scenarios

Recommended review flow:

1. Save the JSON array as a candidate file, for example `eval_sets/sec_agent_multiturn_tool_harness_eval_candidate_v1.json`.
2. Verify every scenario and turn has the required fields.
3. Check expected tool sequences against the v0 harness tool list.
4. Check rerun policy and invalidation expectations.
5. Manually review whether any scenario accidentally requires external sources.
6. Only then promote it to a harness/controller eval set.
