"""Record an already-approved M6 global one-shot human receipt at its fixed path.

This script does not send a request.  It rejects the pending template and
checks exact package/scope digests before an append-only active receipt is
recorded.  The live runner never calls this script.
"""

from __future__ import annotations

from datetime import datetime
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.m6_pilot_global_approval import M6GlobalOneShotApprovalReceipt, M6GlobalOneShotApprovalService


PRELIGHT_PATH = ROOT / "scripts/engineering/run_point01_m6_2_global_one_shot_preflight.py"
RECEIPT_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_global_one_shot_human_receipt_v1_0.json"
SPEC = importlib.util.spec_from_file_location("point01_m6_2_global_preflight_for_record", PRELIGHT_PATH)
assert SPEC and SPEC.loader
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


def main() -> int:
    raw = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    preflight = PREFLIGHT.build_result()
    if raw.get("approval_state") != "approved":
        raise SystemExit("human_receipt_not_approved")
    if raw.get("reviewer") != preflight["required_reviewer"]:
        raise SystemExit("human_receipt_reviewer_identity_mismatch")
    package = preflight["approval_package"]
    if raw.get("approval_id") != preflight["approval_id"] or raw.get("package_ref") != package["package_ref"]:
        raise SystemExit("human_receipt_identity_or_package_ref_mismatch")
    if (raw.get("package_digest"), raw.get("package_manifest_digest"), raw.get("scope_digest")) != (package["package_digest"], package["manifest_digest"], preflight["scope_digest"]):
        raise SystemExit("human_receipt_exact_digest_mismatch")
    if str(raw.get("approval_nonce") or "").lower().startswith("pending"):
        raise SystemExit("human_receipt_one_shot_nonce_required")
    runner = PREFLIGHT.RUNNER
    store = runner.SQLiteCanonicalStore(runner._global_approval_store_root() / "canonical.sqlite")
    receipt = M6GlobalOneShotApprovalReceipt.create(
        tenant_id="tenant-point01-global-approval",
        project_id="project-point01-global-approval",
        actor_snapshot_ref=f"human:{raw['reviewer']['name']}:{raw['reviewer']['employee_id']}",
        permission_snapshot_ref="human-review:point01-m6-2-global-one-shot",
        policy_config_refs=("point01-m6-2-global-one-shot-authority-policy-v1",),
        correlation_id="correlation-point01-m6-2-global-one-shot",
        current_status="active",
        approval_id=str(raw["approval_id"]),
        approval_version=1,
        state_version=1,
        approval_state="active",
        approval_nonce=str(raw["approval_nonce"]),
        scope_digest=str(raw["scope_digest"]),
        package_ref=str(raw["package_ref"]),
        package_digest=str(raw["package_digest"]),
        package_manifest_digest=str(raw["package_manifest_digest"]),
        reviewer_name=str(raw["reviewer"]["name"]),
        reviewer_employee_id=str(raw["reviewer"]["employee_id"]),
        reviewer_role=str(raw["reviewer"]["role"]),
        expires_at=datetime.fromisoformat(str(raw["expires_at"]).replace("Z", "+00:00")),
        authority_store_identity=store.store_identity(),
    )
    M6GlobalOneShotApprovalService(store=store).register_authoritative_receipt(receipt)
    print(json.dumps({"status": "recorded", "approval_id": receipt.approval_id, "approval_store_identity": store.store_identity()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
