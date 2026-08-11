# 132 - SEC Agent Graph State Boundary

## Summary
- Date: 2026-05-22
- Branch: `codex/api-model-call-architecture`
- Purpose: 在不立即引入 LangGraph/LangChain 运行时依赖的前提下，先把 SEC Agent 链路抽象成可落盘、可恢复、可审计的 graph-style 状态与节点边界。
- Status: internal state and node contracts added; existing interactive chain behavior is unchanged.
- Secret policy: no API key, SSH password, or temporary credential is stored.

## Decision
Do not migrate the whole chain to LangChain or LangGraph yet.

The current project value is concentrated in auditable intermediate artifacts:

```text
Query Contract
Retrieved Context / BGE rerank
Runtime Exact-Value Ledger
Evidence Coverage Matrix
Judgment Plan
Memo Answer
Claim Verification
Deterministic Gates
Rendered Answer
```

Moving these directly into a generic agent loop would risk hiding the exact boundaries that make the project reliable. The safer path is:

1. Define an internal graph state and node contract now.
2. Keep the current scripts and deterministic gates as the source of truth.
3. Convert `api_memo_v1` synthesis to the graph-style boundary.
4. Add a minimal LangGraph wrapper later only for orchestration, checkpointing, resume, and human-in-the-loop review.

## Added Code
- `src/sec_agent/graph_state.py`
  - `SecAgentState`
  - `ArtifactRef`
  - `StageRecord`
  - artifact keys:
    - `query_contract`
    - `retrieved_context`
    - `runtime_exact_value_ledger`
    - `evidence_coverage_matrix`
    - `judgment_plan`
    - `memo_answer`
    - `claim_verification`
    - `deterministic_gates`
    - `rendered_answer`
  - JSON write/read support via `sec_agent_state.json`.
  - file digest support for artifact refs.
- `src/sec_agent/graph_nodes.py`
  - canonical node order:
    1. `plan_query`
    2. `validate_query_contract`
    3. `retrieve_context`
    4. `rerank_context`
    5. `build_runtime_ledger`
    6. `build_coverage_matrix`
    7. `build_judgment_plan`
    8. `synthesize_memo`
    9. `verify_claims`
    10. `run_deterministic_gates`
    11. `render_answer`
  - node output contracts.
  - node dependency checks.
  - `run_node()` wrapper for future graph-style execution.
- `src/sec_agent/__init__.py`
  - exports `SecAgentState`, `ArtifactRef`, and `StageRecord`.

## Validation
- Compile:

```powershell
python -m py_compile src\sec_agent\graph_state.py src\sec_agent\graph_nodes.py src\sec_agent\__init__.py
```

- State round-trip smoke:
  - `state_roundtrip=true`
  - `node_count=11`
  - `artifact_count=9`
  - `missing_for_retrieve=[]` after `query_contract` is present.
  - `missing_for_synthesis=["runtime_exact_value_ledger","evidence_coverage_matrix","judgment_plan"]`, as expected.

## Why This Is Not LangGraph Yet
- The current blocker is not graph runtime; it is the quality contract for `api_memo_v1`.
- Introducing LangGraph before the memo schema stabilizes would add orchestration complexity before the node contracts are stable.
- The current scaffold keeps the future migration cheap: LangGraph nodes can later call the same node functions and persist the same `SecAgentState` artifacts.

## Next Steps
- Wire the next `api_memo_v1` implementation to emit `memo_answer`.
- Add `claim_verification` as a first-class graph artifact instead of treating it as internal sanitizer state.
- Teach the interactive runner to optionally write `sec_agent_state.json` per run.
- After the 5-case memo eval passes, add a minimal LangGraph POC that only orchestrates existing node functions.
