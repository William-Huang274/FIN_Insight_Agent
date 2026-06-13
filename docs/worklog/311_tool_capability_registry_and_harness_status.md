# 311 - Tool Capability Registry and Harness Status

Date: 2026-06-14

## Prompt

The user asked to extend the next-stage framework with L8/L9 for tool capability registry and document/multimodal input parsing, then asked whether the existing project harness is still being updated or in use.

## Work Completed

- Updated `docs/architecture/agent_graph_vnext/09_lead_supervised_closed_loop_research_framework.zh-CN.md`.
  - Added `L8 Tool Capability Registry`.
  - Added `L9 Document & Multimodal Input Pipeline`.
  - Recorded permissions for Research Lead, Evidence Operators, Specialists, Memo Writer, and Verifier.
  - Recorded parsed input artifact types for PDF/DOCX/Excel/Markdown/PPT/image/video.
  - Added explicit current boundary that these capabilities are not implemented yet.
- Updated `docs/worklog/00_internal_master_checklist.md` with L8/L9 open items.

## Harness Status Finding

The existing `src/sec_agent/tool_harness.py` is still present and still referenced, but it is not the main internal vNext agent graph mechanism.

Current active references include:

- `scripts/cloud/sec_agent_tool_controller.py`
- `scripts/cloud/sec_agent_context_session_cli.py`
- `scripts/cloud/sec_agent_tool_harness.py`
- `scripts/eval_context/evaluate_sec_agent_tool_harness_dispatch_fixtures.py`
- `scripts/eval_context/evaluate_sec_agent_context_api_smoke.py`
- `scripts/eval_context/evaluate_sec_agent_context_managed_tool_controller.py`
- `tests/test_sec_agent_context_source_policy.py`
- `tests/test_sec_agent_8k_earnings_source.py`

The harness currently exposes high-level session/controller tools such as:

- `start_memo_analysis`
- `revise_memo_scope`
- `explain_evidence`
- `inspect_coverage`
- `reformat_answer`
- `resume_analysis`
- `get_session_state`

It remains useful as a session-aware controller facade and context/evidence replay surface. However, recent G11 / Workbench / vNext full-chain work mainly runs through Workbench backend and graph/runtime artifacts, not through the harness as the primary orchestration path. It should be treated as a legacy-but-still-useful facade that needs alignment with the new L1-L9 contracts before being promoted as the enterprise tool layer.

## Verification

- No code tests were run because this task only updated planning/worklog Markdown and performed source-reference inspection.

## Follow-up

- Decide whether to evolve `SecAgentToolHarness` into the new Tool Orchestration Facade or keep it as a compatibility shell while building a new tool capability registry.
- If retained, update harness tool specs to expose L1-L9 capabilities without granting Memo Writer retrieval / DB / web permissions.
