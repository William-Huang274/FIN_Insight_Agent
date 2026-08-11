"""Read-only receipt preflight for the frozen Point01 M6.3/M6.5 package.

This audit utility never reads a SEC User-Agent or starts a live executor.
Its importable function requires an explicitly injected authority store; only
the explicit CLI entrypoint may resolve the fixed production authority path.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.m6_pilot_global_approval import (
    M6GlobalOneShotApprovalError,
    M6GlobalOneShotApprovalService,
)
from sec_agent.canonical_runtime.models import utc_now
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_3_5_positive_sec_document_pilot.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_3_5_positive_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_3_5_positive_sec_document_receipt_preflight_result_v1_0.json"
def _freeze() -> dict[str, Any]:
    return RUNNER.build_result()


def _scope() -> tuple[Any, dict[str, Any]]:
    policy = RUNNER._policy()
    request = RUNNER._request()
    plan = RUNNER._plan(request, policy)
    command = RUNNER._command(
        "PACKAGE_FREEZE_M6_3_5_POSITIVE_SEC_DOCUMENT",
        {
            "work_unit_id": "wu-point01-m6-positive-sec-document",
            "attempt_id": "attempt-point01-m6-positive-sec-document-1",
            "worker_ref": "worker-point01-m6-positive-sec-document",
            "lease_fencing_token": 1,
        },
        idem="package-freeze",
        expected=1,
    )
    return RUNNER._approval_scope(command, request, plan, policy), RUNNER._authority_policy()


def _digest_view(freeze: dict[str, Any]) -> dict[str, str]:
    package = freeze["approval_package"]
    return {
        "package_ref": str(package["package_ref"]),
        "package_digest": str(package["package_digest"]),
        "manifest_digest": str(package["manifest_digest"]),
        "scope_digest": str(freeze["scope_digest"]),
    }


def build_result(*, store: SQLiteCanonicalStore) -> dict[str, Any]:
    """Verify the exact active receipt without a send, executor, or mutation."""
    before = _freeze()
    before_digests = _digest_view(before)
    scope, authority = _scope()
    reviewer = authority["required_reviewer"]
    service = M6GlobalOneShotApprovalService(
        store=store,
        required_reviewer_name=str(reviewer["name"]),
        required_reviewer_employee_id=str(reviewer["employee_id"]),
        required_reviewer_role=str(reviewer["role"]),
    )
    base = {
        "result_version": "finsight_point01_m6_3_5_positive_sec_document_receipt_preflight_result_v1_0",
        "generated_at": utc_now().isoformat(),
        "execution_state": "receipt_registered_preflight_only_live_send_separately_pending",
        "expected_package": before_digests,
        "before_digests": before_digests,
        "external_call_count": 0,
        "network_request_count": 0,
        "tool_invocation_count": 0,
        "store_write_count": 0,
        "user_agent_plaintext_persisted": False,
        "live_send_performed": False,
        "fixed_approval_store_identity": store.store_identity(),
    }
    try:
        receipt = service.verify_active_exact_receipt(
            scope=scope,
            package_ref=before_digests["package_ref"],
            package_digest=before_digests["package_digest"],
            package_manifest_digest=before_digests["manifest_digest"],
            approval_id=str(authority["approval_id"]),
        )
    except M6GlobalOneShotApprovalError as exc:
        return {**base, "status": "fail_closed", "reason": str(exc)}
    after = _freeze()
    after_digests = _digest_view(after)
    digest_stability = before_digests == after_digests
    unconsumed = (
        receipt.approval_state == "active"
        and receipt.consumed_at is None
        and receipt.consumed_by_invocation_id is None
        and receipt.consumed_local_store_identity is None
    )
    receipt_view = {
        "receipt_identity": f"{receipt.approval_id}:v{receipt.approval_version}",
        "approval_id": receipt.approval_id,
        "approval_state": receipt.approval_state,
        # Receipt persistence is intentionally digest-only.  A raw nonce is a
        # one-shot authorization secret and is never available to preflight or
        # other human-facing audit projections.
        "nonce_sha256": receipt.approval_nonce_sha256,
        "expires_at_utc": receipt.expires_at.isoformat(),
        "reviewer": {
            "name": receipt.reviewer_name,
            "employee_id": receipt.reviewer_employee_id,
            "role": receipt.reviewer_role,
        },
        "scope_digest": receipt.scope_digest,
        "package_ref": receipt.package_ref,
        "package_digest": receipt.package_digest,
        "manifest_digest": receipt.package_manifest_digest,
    }
    return {
        **base,
        "status": "pass" if digest_stability and unconsumed else "fail_closed",
        "reason": "active_exact_unconsumed_receipt_preflight_passed" if digest_stability and unconsumed else "receipt_or_digest_stability_check_failed",
        "after_digests": after_digests,
        "digest_stability": digest_stability,
        "scope_exact": receipt.scope_digest == before_digests["scope_digest"],
        "one_shot_unconsumed": unconsumed,
        "receipt": receipt_view,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only preflight for the exact M6.3/M6.5 one-shot receipt.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    database_path = RUNNER._authority_store_root() / "canonical.sqlite"
    if not database_path.is_file():
        raise M6GlobalOneShotApprovalError("global_approval_fixed_store_missing")
    result = build_result(store=SQLiteCanonicalStore(database_path))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "external_call_count": result["external_call_count"], "output": str(output)}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
