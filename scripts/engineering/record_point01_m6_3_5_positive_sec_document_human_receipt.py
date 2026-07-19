"""Register a package-external human-reviewed M6.3/M6.5 one-shot receipt.

No default or checked-in receipt is executable.  The reviewer must provide all
runtime values explicitly, including a new nonce and UTC expiry.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.m6_pilot_global_approval import M6GlobalOneShotApprovalReceipt, M6GlobalOneShotApprovalService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_3_5_positive_sec_document_pilot.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_3_5_positive_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def main() -> int:
    parser = argparse.ArgumentParser(description="Register the separately approved M6.3/M6.5 positive SEC document one-shot receipt.")
    parser.add_argument("--approval-nonce", required=True)
    parser.add_argument("--expires-at-utc", required=True)
    parser.add_argument("--confirm-process-local-user-agent-scope", required=True, choices=("confirmed_for_new_receipt",))
    args = parser.parse_args()
    freeze = RUNNER.build_result()
    authority = RUNNER._authority_policy()
    store = SQLiteCanonicalStore(RUNNER._authority_store_root() / "canonical.sqlite")
    expires_at = datetime.fromisoformat(args.expires_at_utc.replace("Z", "+00:00"))
    receipt = M6GlobalOneShotApprovalReceipt.create(
        tenant_id="global", project_id="point01", case_id=None,
        actor_snapshot_ref="human-total-reviewer-william-003", permission_snapshot_ref="human-review-snapshot-point01-m6-3-5",
        policy_config_refs=(authority["policy_ref"],), correlation_id="point01-m6-3-5-positive-sec-document-human-approval",
        current_status="active", approval_id=str(authority["approval_id"]), approval_version=1, state_version=1, approval_state="active",
        approval_nonce=args.approval_nonce, scope_digest=str(freeze["scope_digest"]), package_ref=str(freeze["approval_package"]["package_ref"]), package_digest=str(freeze["approval_package"]["package_digest"]), package_manifest_digest=str(freeze["approval_package"]["manifest_digest"]), reviewer_name="william", reviewer_employee_id="003", reviewer_role="total_reviewer", expires_at=expires_at, authority_store_identity=store.store_identity(),
    )
    reviewer = authority["required_reviewer"]
    recorded = M6GlobalOneShotApprovalService(
        store=store,
        required_reviewer_name=str(reviewer["name"]),
        required_reviewer_employee_id=str(reviewer["employee_id"]),
        required_reviewer_role=str(reviewer["role"]),
    ).register_authoritative_receipt(receipt)
    print({"status": "recorded", "approval_id": recorded.approval_id, "approval_store_identity": store.store_identity(), "scope_digest": recorded.scope_digest})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
