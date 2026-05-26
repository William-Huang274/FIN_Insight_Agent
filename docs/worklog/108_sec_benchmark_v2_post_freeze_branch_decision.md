# SEC Benchmark v2 Post-Freeze Branch Decision

## Summary

Date: 2026-05-20 Asia/Shanghai

This entry records the branch decision after the plus8 MVP diagnostic freeze
handoff. The next step should be quality hardening of the frozen plus8 pack, not
case-count expansion.

## Decision

Selected branch: accept `v2_plus8_mvp_diagnostic_freeze` and harden validation
coverage before designing plus9 or the 40-case full v2 route.

Do next:

1. Expand abstract-judgment rubric coverage beyond the current 3 checked cases.
2. Run separate gold-context and pipeline-context outputs for plus8 so the
   gold-vs-pipeline parity gate can be active instead of skipped.

Do not do next:

- Do not add plus9 cases yet.
- Do not claim full v2 benchmark readiness.
- Do not change the frozen plus8 manifest while reproducing freeze results.

## Reasoning

plus8 already passed the active route gates, so adding more cases immediately
would improve apparent breadth but blur the freeze boundary. The stronger next
evidence is to close the known review gaps:

- Abstract judgment currently checks only 3 cases.
- Gold-vs-pipeline was skipped by design in the plus8 pipeline-only scored run.
- Several semantic/Judgment Plan warnings are non-blocking but still useful for
  organizing future validation.

## Required Follow-Up

- Create or extend the abstract rubric artifact for the plus8 case families that
  can be judged deterministically.
- Re-run plus8 in separate gold-context and pipeline-context modes under the
  same frozen route contract, then activate the gold-vs-pipeline gate.
- Keep BGE-M3 as the final context selector and preserve the current Qwen9B RTX
  5090 route contract unless the run is explicitly labeled as a new variant.

## Safety Notes

- No password, private token, or temporary credential is written here.
- This is a decision log only; no model inference was run in this step.
