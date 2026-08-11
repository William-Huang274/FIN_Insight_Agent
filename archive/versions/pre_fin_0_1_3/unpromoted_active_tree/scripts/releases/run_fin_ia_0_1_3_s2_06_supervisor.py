from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (SRC, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fin_ia_0_1_3_s2_06_supervisor_execution_support import (  # noqa: E402
    SHARED_LEDGER,
    SUPERVISOR_ROOT,
    load_case_material,
    load_json,
    validate_admission_governance,
    validate_repository,
)
from sec_agent.llm_gateway import chat_completion  # noqa: E402
from sec_agent.s2_same_evidence_supervisor_runtime import (  # noqa: E402
    execute_corrected_candidate,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


AUTHORITY_ROOT = SUPERVISOR_ROOT / "authorities" / "DELL"
RUN_ROOT = SUPERVISOR_ROOT / "runs"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one FIN 0.1.3 S2-06 case-isolated Supervisor candidate"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--case", choices=("DELL",), default="DELL")
    parser.add_argument("--admission", type=Path)
    args = parser.parse_args()

    head = validate_repository()
    material = load_case_material(args.case)
    credential_env = str(material["policy"]["provider"]["api_key_env"])
    credential_present = bool(os.environ.get(credential_env, "").strip())
    if not credential_present:
        raise RuntimeError("s2_06_dell_supervisor_credential_absent")
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "status": "zero_call_supervisor_preflight_pass_admission_not_required",
                    "case_key": args.case,
                    "execution_git_commit": head,
                    "raw_run_id": material["spec"]["raw_binding"]["run_id"],
                    "evaluation_digest": material["evaluation_digest"],
                    "boundary_digest": material["boundary_digest"],
                    "expected_provider_calls": material["capacity"]["provider_calls"],
                    "provider_call_ceiling": material["capacity"]["provider_call_ceiling"],
                    "supervisor_request_characters": material["observed_capacity"]["supervisor_request_characters"],
                    "retry_count": 0,
                    "fallback_count": 0,
                    "provider_calls": 0,
                    "network_calls": 0,
                    "credential_present": True,
                    "credential_value_read": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.admission is None:
        parser.error("--execute requires --admission")
    admission_path = args.admission.resolve()
    if admission_path.parent != AUTHORITY_ROOT.resolve():
        raise RuntimeError("s2_06_dell_supervisor_admission_path_invalid")
    admission = load_json(admission_path)
    if admission.get("case_key") != args.case:
        raise RuntimeError("s2_06_dell_supervisor_case_binding_invalid")
    validate_admission_governance(
        admission,
        material=material,
        execution_git_commit=head,
    )
    corrected_run_id = str(admission["corrected_run_id"])
    corrected_attempt_id = str(admission["corrected_attempt_id"])
    runtime_root = RUN_ROOT / corrected_run_id
    if runtime_root.exists():
        raise RuntimeError("s2_06_dell_supervisor_runtime_root_already_exists")
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    result = execute_corrected_candidate(
        admission=admission,
        boundary=material["boundary"],
        case_input=material["case_input"],
        raw_outputs=material["raw_outputs"],
        policy=material["policy"],
        corrected_run_id=corrected_run_id,
        corrected_attempt_id=corrected_attempt_id,
        runtime_root=runtime_root,
        shared_ledger=SharedAdmissionConsumptionLedger(SHARED_LEDGER),
        provider_call=chat_completion,
        observed_at=observed_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "terminal_completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
