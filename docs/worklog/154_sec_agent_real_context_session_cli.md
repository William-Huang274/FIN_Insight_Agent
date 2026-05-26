# SEC Agent Real Context Session CLI

## Prompt
- User wants to manually enter prompts on the cloud node and test a real session, including model output and context/session management.
- Requirement is not a fixed replay/eval scenario: the entry point must accept arbitrary user prompts and keep the same session across follow-up turns.
- No cloud passwords or API keys are written to repo files.

## Reasoning And Decision
- Existing `graph-ask-deepseek` supports arbitrary prompts and real SEC DAG execution, but it is single-turn and does not retain conversation/session context.
- Existing `SecAgentContextRequestHandler` supports ContextManager snapshots and tool dispatch, but it assumed an existing session. A manual first turn needs a bootstrap path that can create a new session and then let follow-up turns use ContextManager snapshots.
- Implemented a small CLI wrapper instead of changing the core DAG: first normal prompt bootstraps `start_memo_analysis`; later prompts route through `ContextManager -> controller -> harness -> context update`.

## Work Completed
- Updated `src/sec_agent/context_api.py`
  - Added optional `allow_new_session`, `execute_tools`, and `graph_args` parameters.
  - Added new-session bootstrap for `no_sessions_for_user` / missing requested session.
  - Allows the request handler to execute selected DAG-capable tools by overriding route-only `execute=False` at dispatch time.
  - Keeps `reformat_answer` non-executing because current harness v0 only records reformat requests.
- Updated `src/sec_agent/context_manager.py`
  - Fixed planned/no-execute analyses with empty `state_path`; empty path no longer resolves to `.` and breaks snapshot building.
- Updated `src/sec_agent/tool_harness.py`
  - `resume_analysis(..., graph_args=...)` now preserves DeepSeek/BGE graph arguments during resume execution.
- Added `scripts/cloud/sec_agent_context_session_cli.py`
  - Interactive real-session CLI.
  - Supports `/state`, `/context`, `/answer`, `/help`, `/exit`.
  - Writes turn JSONL logs under `reports/quality/`.
  - Prints session id, active answer id, active scope, artifact state, run root, state path, and answer preview.
- Updated `scripts/cloud/sec_agent_interactive.sh`
  - Added `session-deepseek` / `session-api` command that calls the new CLI.

## Validation
### Syntax
```powershell
python -m py_compile src/sec_agent/context_manager.py src/sec_agent/context_api.py src/sec_agent/tool_harness.py scripts/cloud/sec_agent_context_session_cli.py
bash -n scripts/cloud/sec_agent_interactive.sh
```

Result: passed.

### Local No-Execute Session Dry Run
Command:
```powershell
python scripts/cloud/sec_agent_context_session_cli.py --controller-backend heuristic --no-execute --session-id local_dry_context_session_cli_v2 --session-root reports/quality/local_context_session_cli_dry_v2/session_harness --context-root reports/quality/local_context_session_cli_dry_v2/context_store --turn-log reports/quality/local_context_session_cli_dry_v2/turns.jsonl --prompt "请基于SEC 10-K分析NVDA 2024和2025的数据中心增长、毛利率和主要风险" --prompt "先看当前状态" --answer-preview-chars 0
```

Result:
- Turn 1 bootstrapped a new session and routed to `start_memo_analysis`.
- Turn 2 reused ContextManager state and routed to `get_session_state`.
- Active scope was preserved as `NVDA` / `[2023, 2024, 2025]`.
- Artifact state correctly showed all DAG artifacts missing because this was `--no-execute`.

### Regression
Commands:
```powershell
python scripts/evaluate_sec_agent_context_api_smoke.py --controller-backend heuristic --fixture-root reports/quality/local_context_api_smoke_fixture_runtime_after_session_cli --output-path reports/quality/local_context_api_smoke_after_session_cli_heuristic_v1.json --clean-fixtures
python scripts/evaluate_sec_agent_context_state_replay.py --output-path reports/quality/local_context_state_replay_after_session_cli_v1.json
```

Results:
- API smoke: `6/6`, `failure_count=0`.
- Context state replay: `7/7`, `failure_count=0`.

## Cloud Usage
On the cloud node:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
read -rsp "DeepSeek API key: " DEEPSEEK_API_KEY; echo
export DEEPSEEK_API_KEY
PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python \
BGE_DEVICE=cuda QUERY_PLANNER=llm \
bash scripts/cloud/sec_agent_interactive.sh session-deepseek
```

Then enter a normal SEC analysis prompt at `sec-session>`. Follow-up prompts reuse the same session. Use:
- `/state` for compact session state.
- `/context` for current ContextManager snapshot.
- `/answer` for the latest rendered answer preview.
- `/exit` to quit.

## Known Limits
- This local validation did not call DeepSeek and did not run the real SEC DAG/GPU path.
- Real-session cloud execution still uses JSON-backed session/context state with process-local locking, so it is suitable for manual smoke/demo only, not production concurrency.
- `reformat_answer` remains request-recording only in harness v0.
- If the controller routes an unsupported first-turn follow-up, bootstrap forces `start_memo_analysis` so a new session can be created deterministically.

## Follow-Up
- Run one manual cloud `session-deepseek` prompt and at least one follow-up turn to inspect `run_root`, `sec_agent_state.json`, `/context`, and `/answer`.
- After manual cloud validation, record the run path and whether ContextManager routed follow-ups as expected.

## Cloud Validation Update
### 2026-05-23 Real DeepSeek Session Smoke
- Environment: SeeTaCloud, repo `/root/autodl-tmp/FIN_Insight_Agent`, Python `/root/autodl-tmp/envs/sec-agent-cu128/bin/python`.
- API key was injected only as a process environment variable for the run; it was not written to repo files, logs, or worklogs.
- First prompt:
  - `请基于SEC 10-K分析NVDA 2025的数据中心增长、毛利率和主要风险，输出简洁投资备忘录。`
- Follow-up prompt:
  - `这个回答的证据覆盖完整吗？列出缺口。`
- Session id:
  - `remote_real_context_session_smoke_20260523`
- Turn log:
  - `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/remote_real_context_session_smoke_20260523_turns.jsonl`
- First-turn run root:
  - `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260523_185033_355f93afe9`
- State path:
  - `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260523_185033_355f93afe9/sec_agent_state.json`
- Result:
  - Turn 1: `start_memo_analysis`, `tool_status=completed`, real DAG executed.
  - Turn 1 artifact state: all 10 core artifacts complete.
  - Turn 2: `inspect_coverage`, `tool_status=completed`, same active session and answer id reused.
  - Turn 2 artifact state: all 10 core artifacts still complete; no rerun required for coverage inspection.
- Observed caveat:
  - The generated memo correctly surfaced a coverage caveat for missing `customer_concentration` metric-family evidence.
  - Active years resolved to `[2023, 2024, 2025]` because the current harness defaults to trend years unless a tighter year list is passed through the tool call.

### 2026-05-23 CLI Rendered Output Patch
- User observed that the manual session CLI preview displayed `qwen/input_output.md`, which is an audit page containing `Final Answer JSON`.
- Updated `scripts/cloud/sec_agent_interactive.py`:
  - New real DAG runs now write `qwen/rendered_answer.md`.
  - The `rendered_answer` artifact path now points to `qwen/rendered_answer.md` instead of the audit `qwen/input_output.md`.
  - The audit JSON page is still written for debugging.
- Updated `scripts/cloud/sec_agent_context_session_cli.py`:
  - `/answer` and automatic answer preview now prefer `qwen/rendered_answer.md`.
  - For old runs without `rendered_answer.md`, the CLI dynamically renders `qwen/agent_outputs.jsonl` into Markdown.
  - The fallback renderer hides long `INTERACTIVE_...` metric/evidence IDs and shows compact support counts instead.
- Cloud verification used the existing run root:
  - `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260523_185033_355f93afe9`
- Verification result:
  - Preview starts with rendered Markdown sections such as `Direct Answer`, `Investment Thesis`, and `What Changed`.
  - `Final Answer JSON` no longer appears in the CLI preview.
  - Long `INTERACTIVE_...` IDs no longer appear in the CLI preview.

### 2026-05-23 Broad AI Prompt Failure Fix
- User prompt reproduced on cloud:
  - `你觉得ai行业相关的这些公司这三年业绩表现如何`
- Failure observed before the fix:
  - The planner expanded the broad AI-industry wording to all 30 manifest companies across 2023-2025.
  - DeepSeek synthesis returned an HTTP 400 on the over-broad packed prompt.
  - The CLI reported `tool_error` with `answer_preview: not found`; the graph runner also displayed the repo root as `run_root` even though no valid `sec_agent_state.json` had been produced.
- Fixes:
  - Broad AI-industry prompts now scope to the manifest-derived AI focus set instead of all SEC companies.
  - `_run_graph_analysis()` only reports `run_root` / `state_path` when a real `sec_agent_state.json` exists.
  - The session CLI now prints execution stdout/stderr tails on `tool_error`, so graph failures are visible instead of looking like an empty answer.
  - The rendered-answer preview path from the previous patch remains the default, so successful runs show user-facing Markdown instead of audit JSON.
- Cloud validation:
  - Session id: `remote_render_fix_broad_ai_20260523`
  - Run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260523_193554_a11fbc345f`
  - State path: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260523_193554_a11fbc345f/sec_agent_state.json`
  - Active scope: `NVDA`, `AMD`, `AVGO`, `AMAT`, `MU`, `INTC`, `QCOM`, `MSFT`, `GOOGL`, `AMZN`, `META`, `ADBE`, `SNOW`; years `[2023, 2024, 2025]`.
  - Result: `status=completed`, all 10 core artifacts complete, rendered Markdown answer visible in the terminal.
  - Preview check: no `Final Answer JSON` block and no long `INTERACTIVE_...` metric/evidence ids in the user-facing preview.
- Caveat:
  - For this broad prompt, the model output still triggered the deterministic ledger fallback because the synthesis JSON was not parseable. The fallback answer is visible and evidence-count rendered, but free-form broad-industry memo quality still needs a separate quality pass before promotion.

### 2026-05-23 Truncated JSON Rendering Repair
- User observed the repaired broad-AI run still looked like a metric dump:
  - `deterministic ledger fallback` appeared in `decision_drivers`.
  - The answer showed internal `decision_drivers` / `key_points` gate fields instead of only user-facing memo sections.
- Root cause:
  - DeepSeek did generate a substantive memo, but the synthesis call used the old 4000-token output cap.
  - The gateway recorded `output_tokens=4001`, and the raw model output ended mid-`watch_items`, so JSON parsing failed and the pipeline used the ledger fallback.
- Fixes:
  - `session-deepseek` now separates controller tokens from downstream synthesis tokens.
  - Controller default remains compact, while graph synthesis defaults to `SYNTHESIS_MAX_TOKENS=8000`.
  - Added a truncated-JSON prefix repair path that can recover a complete memo prefix when the model output is cut off before final JSON closure.
  - Renderers now hide legacy `decision_drivers` and `key_points` when memo fields such as `direct_answer`, `investment_thesis`, `what_changed`, and `why_it_matters` are present.
  - Genericized fallback wording from `Qwen output` to `model output` because the same code path is used for DeepSeek API synthesis.
- Cloud validation:
  - Replayed the existing raw output from `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260523_193554_a11fbc345f/qwen/raw_model_outputs.jsonl`.
  - Parser status: `parsed_after_truncation_repair`.
  - Rewrote `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260523_193554_a11fbc345f/qwen/rendered_answer.md`.
  - Preview now starts with `直接回答`, `投资判断`, and `关键变化`; it no longer contains `Final Answer JSON`, `deterministic ledger fallback`, `## 决策驱动`, or `## 关键要点` in the rendered memo.

### 2026-05-23 Follow-Up Tool Routing and CLI Payload Rendering
- User follow-up:
  - `你再具体讲一下NVDA和AMD的对比`
- Observed behavior:
  - The DeepSeek tool controller routed the turn to `explain_evidence`.
  - The tool completed, but the manual CLI only printed turn metadata, so it looked like the follow-up produced no substantive output.
- Decision:
  - Do not add a deterministic semantic override that replaces model tool-calling.
  - Keep the model controller responsible for choosing tools; deterministic logic should remain limited to safety/default filling and display behavior.
- Fixes:
  - Clarified the controller system prompt: if the user asks to focus, drill down, or compare a subset of companies from the active memo, use `revise_memo_scope`, not `explain_evidence`.
  - Extended `revise_memo_scope` with `set_tickers`, so the model can replace the current broad scope with exactly `NVDA, AMD` instead of only adding/removing tickers.
  - Added CLI rendering for non-rerun tool payloads:
    - `explain_evidence` now prints target claim, ledger rows, Judgment Plan matches, and support counts.
    - `inspect_coverage` now prints coverage summary and compact task gaps.
    - `revise_memo_scope` now prints revised ticker/year scope before the answer preview.
- Validation:
  - Local `py_compile` passed for `src/sec_agent/tool_harness.py`, `src/sec_agent/tool_controller.py`, and `scripts/cloud/sec_agent_context_session_cli.py`.
  - Cloud sync and cloud `py_compile` passed on the same files.
