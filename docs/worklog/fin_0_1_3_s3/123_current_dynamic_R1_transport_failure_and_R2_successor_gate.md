# FIN 0.1.3 S3 — current dynamic R1 transport failure and R2 successor gate

Date: 2026-08-23

## R1 result

The exact-once R1 stopped on its first request-planning transport call. DeepSeek
returned HTTP 400 with the exact message `Thinking mode does not support this
tool_choice`. No model output, S1/S2 request, retrieval round, reflection,
workpaper, candidate promotion or external-source network call occurred. The
public terminal result and the complete capture-first private failure are
preserved and may not be relabelled as a research result.

## Root cause

This is a project integration regression, not a DeepSeek research-capability
failure. The new current-dynamic runner directly used the legacy Chat executor and
forced a named `tool_choice`. The repository already had a qualified
provider-neutral transport profile and dispatch that removes this unsupported
field in DeepSeek thinking mode while retaining local exact-one-tool validation.
The new runner failed to reuse that mainline component.

## Bounded repair

- Route the current runner through `execute_agent_tool_step_exact_once`.
- Load the existing v1.1 agent transport profile with
  `thinking_tool_choice_supported=false`.
- Keep the forced expected tool as a provider-neutral local intent; the dispatch
  omits only the unsupported wire field, and the runner still rejects any missing,
  extra or wrong tool call.
- Preserve the R1 result and bind it into a new v1.1 decision and authority.
- Keep the DELL question, current Pack, S1/S2 loop, model, four-call ceiling and
  all zero-retry/no-promotion boundaries unchanged.

## Verification and next gate

Targeted Project OS, current-runner and transport tests pass (`10 passed`). A
legacy profile mutation fails closed. Full repository regression passes (`1079
passed`, with only the two existing SWIG warnings), as do `compileall`, the active
baseline (`205 / 8 / 5 / 28 / 0`), 882 config JSON parses, diff check and a
7,695-file secret scan. The successor still requires clean commit/push,
repository-aware Project OS preflight and a fresh exact-once R2 authority before
any paid call.
