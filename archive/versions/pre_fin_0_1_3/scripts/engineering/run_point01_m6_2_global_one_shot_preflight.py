"""Compute the exact package and scope a human must approve for the M6 SEC pilot.

This is read-only: it does not create an approval store, local pilot store,
grant, reservation, receipt or network request.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.m6_pilot_global_approval import build_m6_pilot_scope
from sec_agent.canonical_runtime.m6_pilot_package import compute_m6_pilot_package


RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_2_real_bounded_sec_metadata_pilot.py"
AUTHORITY_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_global_one_shot_authority_policy_v1_0.json"
PACKAGE_MANIFEST_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_global_one_shot_package_manifest_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_2_global_one_shot_preflight_result_v1_0.json"

SPEC = importlib.util.spec_from_file_location("point01_m6_2_runner_for_global_preflight", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def build_result() -> dict[str, object]:
    policy = RUNNER._policy()
    authority = json.loads(AUTHORITY_POLICY_PATH.read_text(encoding="utf-8"))
    command = RUNNER._command(
        "EXECUTE_M6_2_REAL_BOUNDED_SEC_METADATA",
        {"work_unit_id": "wu-point01-m6-sec-pilot", "attempt_id": "attempt-point01-m6-sec-pilot-1", "worker_ref": "worker-point01-m6-sec-pilot", "lease_fencing_token": 1},
        idem="execute",
        expected=1,
    )
    request = RUNNER._request()
    plan = RUNNER._registry_plan(request)
    scope = build_m6_pilot_scope(
        command=command,
        request=request,
        plan=plan,
        approval_ref=policy.approval_ref,
        approved_execution_scope=policy.approved_execution_scope,
        tool_id=policy.tool_id,
        route_id=policy.route_id,
        network_host=policy.allowed_network_host,
        target_cik=policy.allowed_cik,
    )
    package = compute_m6_pilot_package(root=ROOT, manifest_path=PACKAGE_MANIFEST_PATH)
    return {
        "status": "pending_human_receipt",
        "scope": "exact_nvda_sec_metadata_global_one_shot_approval_preflight_only",
        "approval_id": authority["approval_id"],
        "required_reviewer": authority["required_reviewer"],
        "approval_package": package.model_dump(mode="json"),
        "approval_scope": scope.model_dump(mode="json"),
        "scope_digest": scope.scope_digest,
        "authority_store_path": str(RUNNER._global_approval_store_root()),
        "external_call_count": 0,
        "store_write_count": 0,
        "next_action": "A human reviewer must copy exact package_digest, manifest_digest and scope_digest into the pending receipt, set a unique nonce and UTC expiry, then separately register the approved receipt. This preflight cannot grant authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the no-write M6 global one-shot human-approval package.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
