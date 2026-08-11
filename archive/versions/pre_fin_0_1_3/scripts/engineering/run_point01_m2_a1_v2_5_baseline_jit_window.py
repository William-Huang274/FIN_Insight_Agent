"""Frozen v2.5 JIT orchestration contract; intentionally not invokable here.

It is an input of the v2.5 execution package so a later, separately approved
JIT window cannot rely on an unreviewed package-external orchestration script.
This Phase-B0.2 version refuses issuance, registration, or execution.
"""

from __future__ import annotations

import json


JIT_CONTRACT = {
    "sequence": ["issue", "verify", "register", "preflight", "consume", "reverify", "grant_verify", "materialize", "clean_child_execute"],
    "future_admission_ttl_minutes": 30,
    "future_receipt_ttl_minutes": 15,
    "one_scenario_only": "p01-baseline-separated-input",
    "retry_or_replay": "forbidden",
    "phase_b0_2_status": "do_not_invoke_pending_independent_review",
}


def main() -> int:
    print(json.dumps({"status": "m2_a1_v2_5_jit_window_not_authorized", "contract": JIT_CONTRACT, "authority_or_runtime_created": 0}, ensure_ascii=False, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
