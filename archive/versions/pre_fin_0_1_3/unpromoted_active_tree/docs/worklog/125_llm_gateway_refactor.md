# 125 - LLM Gateway Refactor

## Summary
- Date: 2026-05-21
- Purpose: implement the second vNext step from `123_model_gateway_intermediate_artifact_framework.md`: route model calls through a provider-neutral gateway.
- Status: local implementation and syntax checks complete; no cloud inference or API spend in this step.

## Work Completed
- Added `src/sec_agent/llm_gateway.py`.
  - Provides `chat_completion()` with structured metadata:
    - provider/backend;
    - model;
    - role;
    - profile;
    - latency;
    - token usage when returned by provider;
    - status and failure reason;
    - trace tags.
  - Provides `chat_completion_content()` for current call sites that need plain content.
  - Handles:
    - local `qwen_vllm`;
    - `deepseek`;
    - generic `openai_compatible`.
  - Keeps provider keys in environment variables only.
  - Sends DeepSeek `thinking: disabled` by default unless explicitly enabled.
- Updated `scripts/cloud/sec_agent_interactive.py`.
  - Query Contract planner now calls the gateway with `role=planner`.
  - SEC answer synthesis now calls the gateway with `role=synthesizer`.
  - Synthesis debug output now includes sanitized gateway metadata, not secrets.
  - Run summary now includes sanitized gateway metadata for latency/token comparison.
  - Removed duplicated chat-completion request logic from the interactive script.

## Validation
- `python -m py_compile scripts/cloud/sec_agent_interactive.py src/sec_agent/project_inventory.py src/sec_agent/llm_gateway.py` passed.
- Local `--print-config` still works.
- Local `--llm-backend deepseek --query-planner llm --plan-only ...` without `DEEPSEEK_API_KEY` fails through the gateway and falls back explicitly, preserving the inventory-aware heuristic contract.

## Decision
Model access is now routed through a small gateway while preserving the existing interactive chain. This keeps the project on the documented path without prematurely rewriting retrieval, ledger, Judgment Plan, or answer gates.

Next work should extract Query Contract validation into a dedicated validator, then add claim-first synthesis.
