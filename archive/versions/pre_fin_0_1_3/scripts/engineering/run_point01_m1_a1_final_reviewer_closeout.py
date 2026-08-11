"""Validate the reviewer-approved M1-A1 governance closeout without rerunning M1."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


PATHS = {
    "package": ROOT / "data/manifests/point01_m1_a1_adversarial_audit_package_manifest_v1_1.json",
    "admission": ROOT / "data/manifests/point01_m1_a1_exact_external_package_admission_v1_0.json",
    "execution_receipt": ROOT / "data/manifests/point01_m1_a1_exact_admitted_execution_receipt_projection_v1_0.json",
    "actual_gate": ROOT / "data/manifests/point01_m1_a1_exact_admitted_audit_gate_result_v1_1.json",
    "execution_closeout": ROOT / "data/manifests/point01_m1_a1_exact_admitted_audit_execution_closeout_v1_0.json",
    "reviewer_receipt": ROOT / "data/manifests/point01_m1_a1_total_reviewer_acceptance_receipt_v1_0.json",
}
OUTPUT = ROOT / "data/manifests/point01_m1_a1_final_reviewer_closeout_gate_result_v1_0.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_result() -> dict[str, Any]:
    package, admission, execution_receipt, actual_gate, execution_closeout, reviewer_receipt = (
        _load(PATHS[name])
        for name in ("package", "admission", "execution_receipt", "actual_gate", "execution_closeout", "reviewer_receipt")
    )
    recomputed = {
        "package_digest": package["package_digest"],
        "admission_digest": canonical_digest(admission),
        "execution_receipt_digest": canonical_digest({key: value for key, value in execution_receipt.items() if key != "receipt_digest"}),
        "actual_gate_digest": canonical_digest(actual_gate),
        "execution_closeout_digest": canonical_digest({key: value for key, value in execution_closeout.items() if key != "closeout_digest"}),
    }
    bound = all(reviewer_receipt[key] == value for key, value in recomputed.items())
    probe_oracles = {probe["probe_id"]: probe["oracle_status"] for probe in actual_gate["probes"]}
    checks = {
        "reviewer_identity_trusted": reviewer_receipt["reviewer_identity"] == "william/003/total_reviewer",
        "approval_decision_exact": reviewer_receipt["decision"] == "approve_and_retain_historical_m1_without_authority_expansion",
        "all_digest_bindings_exact": bound,
        "single_execution_receipt_consumed": execution_receipt["single_use_consumed"] is True and execution_receipt["terminal_status"] == "completed",
        "actual_gate_pass": actual_gate["gate_status"] == "pass" and set(probe_oracles) == {"A0-M1-P01", "A0-M1-P02", "A0-M1-P03", "A0-M1-P04"} and all(status == "pass" for status in probe_oracles.values()),
        "scoped_regression_pass": actual_gate["scoped_m1_regression"]["returncode"] == 0 and actual_gate["scoped_m1_regression"]["passed_count"] == 35,
        "execution_closeout_pass": execution_closeout["status"] == "completed_pending_independent_review" and execution_closeout["gate_status"] == "pass",
        "authority_not_expanded": reviewer_receipt["authority_expansion_authorized"] is False and reviewer_receipt["second_execution_authorized"] is False and reviewer_receipt["retained_authority_boundary"] == "legacy_taskrun_authoritative_no_compiler_or_cutover",
        "external_counts_zero": all(value == 0 for value in actual_gate["external_execution_counts"].values()),
    }
    failures = sorted(name for name, passed in checks.items() if not passed)
    payload = {
        "result_version": "finsight_point01_m1_a1_final_reviewer_closeout_gate_result_v1_0",
        "scope": "M1_A1_reviewer_governance_closeout_only",
        "m1_a1_status": "complete_historical_claim_retained_without_authority_expansion" if not failures else "fail_closed",
        "historical_m1_claim": "retained_limited_scope" if not failures else "not_changed",
        "retained_maturity_boundary": reviewer_receipt["retained_maturity_boundary"],
        "retained_authority_boundary": reviewer_receipt["retained_authority_boundary"],
        "reviewer_receipt_digest": canonical_digest(reviewer_receipt),
        "recomputed_digests": recomputed,
        "checks": checks,
        "failures": failures,
        "gate_status": "pass" if not failures else "fail_closed",
        "next_authorized_scope": reviewer_receipt["next_authorized_scope"] if not failures else "none",
        "boundary": "Static governance validation only: it does not reopen the consumed receipt, rerun M1, mutate any store, or authorize M2-A1 actual probes, M6/R3, model, network, tool, provider, cutover, Evidence or Writer.",
    }
    return {**payload, "result_digest": canonical_digest(payload)}


def main() -> int:
    result = build_result()
    _write(OUTPUT, result)
    print(json.dumps({"gate_status": result["gate_status"], "m1_a1_status": result["m1_a1_status"], "output": str(OUTPUT)}, ensure_ascii=False))
    return 0 if result["gate_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
