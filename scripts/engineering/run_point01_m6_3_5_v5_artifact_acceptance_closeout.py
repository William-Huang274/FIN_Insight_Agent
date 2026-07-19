"""Validate the package-external, read-only acceptance of the M6.3/M6.5 v5 repair.

This closeout has no execution authority.  It only binds the total-reviewer
acceptance to immutable v5 package values and confirms that the new receipt is
not itself a package input, a secret-bearing export, or a live-send authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from sec_agent.canonical_runtime.m6_pilot_package import compute_m6_pilot_package

from run_point01_m6_3_5_artifact_secret_scan import (
    DEFAULT_EXPORTABLE_ARTIFACTS,
    RESTRICTED_SOURCE,
    build_result as build_secret_scan_result,
)


MANIFEST_PATH = ROOT / "configs/engineering_handoff/point01_m6_3_5_positive_sec_document_package_manifest_v1_0.json"
REFREEZE_PATH = ROOT / "data/manifests/point01_m6_3_5_v5_artifact_contract_refreeze_result_v1_0.json"
RECEIPT_PATH = ROOT / "data/manifests/point01_m6_3_5_v5_artifact_contract_total_reviewer_acceptance_receipt_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_3_5_v5_artifact_contract_acceptance_closeout_result_v1_0.json"

EXPECTED = {
    "package_ref": "point01-m6-3-5-nvda-10k-positive-retrieval-parser-package-v5-artifact-contract-remediation-refreeze",
    "package_digest": "a8210e702e2a7147513537916c505baec92dc0ff7526139c7eb557f19cdfbd23",
    "manifest_digest": "272eb312f635e88da37254b6853b15709a18cdb8ec9cade66541b6fc269b3faa",
    "scope_digest": "bcec5108da71785c7b21c52ea8d671ef8f18e330c962324bc3f44f0935545236",
    "sanitized_projection_sha256": "27e4b30b086ded648c26b6fbf20ca0c1e811297755c0328fa4f7338d72d7dbbe",
}


class AcceptanceCloseoutError(RuntimeError):
    """The v5 acceptance can only be recorded for the exact audited package."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceCloseoutError(f"json_unreadable:{path.name}") from exc
    if not isinstance(value, dict):
        raise AcceptanceCloseoutError(f"json_object_required:{path.name}")
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        if {"approval_nonce", "global_approval_nonce", "user_agent", "raw_html"} & set(value):
            return True
        return any(_contains_forbidden_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def build_result() -> dict[str, Any]:
    package_before = compute_m6_pilot_package(root=ROOT, manifest_path=MANIFEST_PATH)
    manifest = _read_json(MANIFEST_PATH)
    receipt = _read_json(RECEIPT_PATH)
    refreeze = _read_json(REFREEZE_PATH)
    artifacts = receipt.get("accepted_artifacts")
    boundary = receipt.get("approval_boundary")
    decision = receipt.get("decision")
    if not isinstance(artifacts, dict) or not isinstance(boundary, dict) or not isinstance(decision, dict):
        raise AcceptanceCloseoutError("receipt_shape_invalid")

    exact_values = {
        "package_ref": package_before.package_ref,
        "package_digest": package_before.package_digest,
        "manifest_digest": package_before.manifest_digest,
        "scope_digest": str(refreeze.get("scope_digest") or ""),
        "sanitized_projection_sha256": str(artifacts.get("sanitized_projection_sha256") or ""),
    }
    checks: dict[str, bool] = {
        "package_values_match_audited_v5": exact_values == EXPECTED,
        "receipt_binds_exact_audited_values": all(str(artifacts.get(key) or "") == value for key, value in EXPECTED.items()),
        "receipt_is_package_external": str(RECEIPT_PATH.relative_to(ROOT)).replace("\\", "/") not in manifest.get("included_paths", []),
        "receipt_is_read_only_not_execution_authority": (
            receipt.get("receipt_type") == "package_external_total_reviewer_read_only_acceptance_not_execution_authority"
            and boundary.get("reviewer_acceptance_read_only") is True
            and all(
                boundary.get(key) is False
                for key in (
                    "execution_or_live_receipt_created",
                    "live_send_authorized",
                    "new_sec_get_authorized",
                    "evidence_promotion_authorized",
                    "context_or_writer_authorized",
                    "sourcehunter_m6_4_authorized",
                    "model_or_full_chain_authorized",
                    "business_case_mutation_authorized",
                    "m6_complete",
                )
            )
        ),
        "reviewer_identity_exact": receipt.get("reviewer") == {"name": "william", "employee_id": "003", "role": "total_reviewer"},
        "decision_digest_exact": hashlib.sha256(str(decision.get("decision_text") or "").encode("utf-8")).hexdigest()
        == str(decision.get("decision_text_sha256") or ""),
        "receipt_contains_no_secret_keys": not _contains_forbidden_key(receipt),
        "restricted_original_still_separate": RESTRICTED_SOURCE.is_file() and RESTRICTED_SOURCE != RECEIPT_PATH,
    }
    secret_scan = build_secret_scan_result(
        exportable_artifacts=(*DEFAULT_EXPORTABLE_ARTIFACTS, RECEIPT_PATH),
    )
    package_after = compute_m6_pilot_package(root=ROOT, manifest_path=MANIFEST_PATH)
    checks["package_stable_before_after_receipt_validation"] = package_before == package_after
    checks["secret_scan_pass"] = secret_scan.get("status") == "pass"
    status = "pass" if all(checks.values()) else "fail_closed"
    return {
        "result_version": "finsight_point01_m6_3_5_v5_artifact_contract_acceptance_closeout_result_v1_0",
        "status": status,
        "execution_state": "remediated_v5_artifact_contract_independently_accepted_no_downstream_authority" if status == "pass" else "fail_closed",
        "reviewer_acceptance_receipt": {
            "path": str(RECEIPT_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": hashlib.sha256(RECEIPT_PATH.read_bytes()).hexdigest(),
            "receipt_type": receipt.get("receipt_type"),
        },
        "package_stability": {
            "before": package_before.model_dump(mode="json"),
            "after": package_after.model_dump(mode="json"),
            "receipt_excluded_from_manifest": checks["receipt_is_package_external"],
        },
        "checks": checks,
        "secret_scan": secret_scan,
        "canonical_store_write_count": 0,
        "external_call_count": 0,
        "network_request_count": 0,
        "tool_invocation_count": 0,
        "model_call_count": 0,
        "restricted_original_status": "preserved_quarantined_not_exported_not_downstream_input",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Close v5 artifact-contract repair with a read-only total-reviewer receipt.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "receipt_sha256": result["reviewer_acceptance_receipt"]["sha256"], "external_call_count": 0}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
