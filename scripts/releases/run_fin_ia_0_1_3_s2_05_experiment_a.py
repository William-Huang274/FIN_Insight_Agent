from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.llm_gateway import chat_completion  # noqa: E402
from sec_agent.s2_same_evidence_experiment_runtime import (  # noqa: E402
    POLICY_REF,
    execute_case,
    load_frozen_blind_inputs,
    load_runtime_policy,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


RUNNER = ROOT / "src" / "sec_agent" / "s2_same_evidence_experiment_runtime.py"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FIN 0.1.3 S2-05 blinded same-evidence raw-candidate runner"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--case", choices=("DELL", "MU", "NVDA"))
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--observed-at")
    args = parser.parse_args()

    policy = load_runtime_policy(ROOT)
    blind = load_frozen_blind_inputs(ROOT, policy)
    runner_sha = _sha256(RUNNER)
    policy_path = ROOT / POLICY_REF
    policy_sha = _sha256(policy_path)
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "status": "zero_call_preflight_ready_admission_not_issued",
                    "cases": [row["case_key"] for row in blind["cases"]],
                    "runner_ref": RUNNER.relative_to(ROOT).as_posix(),
                    "runner_sha256": runner_sha,
                    "policy_ref": POLICY_REF,
                    "policy_sha256": policy_sha,
                    "frozen_blind_input_digest": blind["blind_input_digest"],
                    "provider_calls": 0,
                    "network_calls": 0,
                    "admission_issued": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    missing = [
        name
        for name, value in (
            ("--case", args.case),
            ("--admission", args.admission),
            ("--runtime-root", args.runtime_root),
            ("--ledger", args.ledger),
            ("--observed-at", args.observed_at),
        )
        if value is None
    ]
    if missing:
        parser.error("--execute requires " + ", ".join(missing))
    admission = _read_json(args.admission.resolve())
    case_input = next(row for row in blind["cases"] if row["case_key"] == args.case)
    result = execute_case(
        admission=admission,
        case_input=case_input,
        policy=policy,
        execution_git_commit=_git_head(),
        runner_sha256=runner_sha,
        policy_sha256=policy_sha,
        runtime_root=args.runtime_root,
        shared_ledger=SharedAdmissionConsumptionLedger(args.ledger),
        provider_call=chat_completion,
        observed_at=args.observed_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "terminal_succeeded_raw_candidate" else 2


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("admission_must_be_json_object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


if __name__ == "__main__":
    raise SystemExit(main())
