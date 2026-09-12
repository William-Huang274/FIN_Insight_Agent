# AI memory research qualification

Canonical modules for case 211. These scripts require archived local inputs;
they are not production services or unattended benchmarks.

| Module | Purpose |
| --- | --- |
| `context_probe` | Bounded baseline/work-index agent comparison |
| `final_evidence_probe` | Fixed final-input source restoration comparison |
| `phase_checkpoint_probe` | Explicit consolidation, checkpoint and review pilot |
| `model_comparison` | Fixed public evidence and erroneous-draft comparison across models |

Run help with `python -m scripts.qualification.ai_memory.<module> --help`.
The previous `scripts.qualification.ai_memory_<module>` names remain thin
compatibility entry points; imports resolve to the canonical module, including
monkeypatches. New code should use this package.

The move changes source hashes. Existing paid attempts remain bound to their
original frozen code and inputs; use those snapshots for historical replay.
Do not reuse a preparation manifest from before the move for a new execution.
Every paid execution still requires its own task-specific TokenBudgetBasis and
an authorized bounded scope. Unknown calls must not be resent automatically.

Results: [case 211 worklog](../../../docs/worklog/fin_0_1_3_s3/211_ai_memory_investment_case.md).
