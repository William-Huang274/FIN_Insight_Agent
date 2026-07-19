"""Freeze and verify the M2-A1 audit design package without running M2 runtime."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


CORPUS = "configs/engineering_handoff/point01_m2_a1_adversarial_input_corpus_v1_0.json"
ORACLE = "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_0.json"
MATRIX = "configs/engineering_handoff/point01_m2_a1_owner_authority_typed_stop_matrix_v1_0.json"
OUTPUT_PACKAGE = ROOT / "data/manifests/point01_m2_a1_adversarial_audit_package_manifest_v1_0.json"
OUTPUT_GATE = ROOT / "data/manifests/point01_m2_a1_design_package_freeze_gate_result_v1_0.json"

PACKAGE_INPUTS = (
    "configs/engineering_handoff/point01_m2_design_freeze_manifest_v1_0.json",
    "configs/engineering_handoff/point01_m2_cross_owner_design_review_v1_0.json",
    "configs/engineering_handoff/point01_m2_closeout_gate_manifest_v1_0.json",
    "configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_2_full_serializer_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_2_full_serializer_readiness_assessment_v1_0.json",
    "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_4_pack_selection_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_5_cell_composition_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_6_evidence_slot_policy_ontology_v1_0.json",
    "configs/engineering_handoff/point01_m2_7_legacy_semantic_mapping_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_8_model_admission_policy_v1_0.json",
    "configs/engineering_handoff/point01_m2_9_shadow_orchestration_policy_v1_0.json",
    CORPUS,
    ORACLE,
    MATRIX,
    "src/sec_agent/canonical_runtime/planning_service.py",
    "src/sec_agent/canonical_runtime/full_serializer.py",
    "src/sec_agent/canonical_runtime/pack_registry.py",
    "src/sec_agent/canonical_runtime/pack_selection.py",
    "src/sec_agent/canonical_runtime/cell_composition.py",
    "src/sec_agent/canonical_runtime/evidence_policy.py",
    "src/sec_agent/canonical_runtime/legacy_objective_adapter.py",
    "src/sec_agent/canonical_runtime/model_admission.py",
    "src/sec_agent/canonical_runtime/feature_flags.py",
    "src/sec_agent/canonical_runtime/shadow_compiler.py",
    "src/sec_agent/canonical_runtime/shadow_orchestration.py",
    "tests/contract/test_point01_m2_compiler_full_validation.py",
    "tests/contract/test_point01_m2_full_serializer.py",
    "tests/contract/test_point01_m2_pack_registry.py",
    "tests/contract/test_point01_m2_pack_selection.py",
    "tests/contract/test_point01_m2_cell_composition.py",
    "tests/contract/test_point01_m2_evidence_policy.py",
    "tests/contract/test_point01_m2_legacy_semantic_mapping.py",
    "tests/contract/test_point01_m2_model_admission.py",
    "tests/contract/test_point01_m2_shadow_orchestration.py",
    "scripts/engineering/run_point01_m2_a1_design_package_freeze.py",
)


def _staged_bytes(relative_path: str) -> bytes:
    result = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"m2_a1_package_input_not_staged:{relative_path}")
    return result.stdout


def _staged_json(relative_path: str) -> dict[str, Any]:
    return json.loads(_staged_bytes(relative_path).decode("utf-8"))


def _payload_digest(payload: dict[str, Any]) -> str:
    return canonical_digest(payload)


def build_package() -> dict[str, Any]:
    corpus, oracle, matrix = (_staged_json(path) for path in (CORPUS, ORACLE, MATRIX))
    payload = {
        "schema_version": "finsight_point01_m2_a1_adversarial_audit_package_manifest_v1_0",
        "scope": "M2_A1_design_and_package_freeze_only",
        "package_ref": "point01-m2-a1-independent-adversarial-audit-package-v1",
        "authority_boundary": "no_actual_compiler_or_shadow_fixture_no_model_network_tool_provider_fixed_production_business_or_legacy_write",
        "input_bytes_source": "git_index",
        "input_file_sha256": {path: hashlib.sha256(_staged_bytes(path)).hexdigest() for path in PACKAGE_INPUTS},
        "corpus_digest": canonical_digest(corpus),
        "oracle_digest": canonical_digest(oracle),
        "typed_stop_matrix_digest": canonical_digest(matrix),
        "external_package_admission_ref": matrix["future_actual_authority"]["external_package_admission_ref"],
        "external_package_admission_required_for_actual": True,
        "single_use_execution_receipt_required_for_actual": True,
        "actual_probes_currently_authorized": False,
    }
    return {**payload, "package_digest": _payload_digest(payload)}


def verify_package(package: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "scope", "package_ref", "authority_boundary", "input_bytes_source", "input_file_sha256",
        "corpus_digest", "oracle_digest", "typed_stop_matrix_digest", "external_package_admission_ref",
        "external_package_admission_required_for_actual", "single_use_execution_receipt_required_for_actual",
        "actual_probes_currently_authorized", "package_digest",
    }
    missing_or_extra = sorted(required.symmetric_difference(package))
    payload = {key: package[key] for key in required if key != "package_digest"} if not missing_or_extra else {}
    package_digest_valid = bool(payload) and package["package_digest"] == _payload_digest(payload)
    mismatches = []
    if package.get("input_bytes_source") != "git_index":
        mismatches.append("input_bytes_source_forbidden")
    for path, expected in sorted(package.get("input_file_sha256", {}).items()):
        if hashlib.sha256(_staged_bytes(path)).hexdigest() != expected:
            mismatches.append(f"staged_input_hash_mismatch:{path}")
    return {
        "status": "pass" if not missing_or_extra and package_digest_valid and not mismatches else "fail_closed",
        "missing_or_extra_fields": missing_or_extra,
        "package_digest_valid": package_digest_valid,
        "mismatches": mismatches,
    }


def design_checks(package: dict[str, Any]) -> dict[str, bool]:
    corpus, oracle, matrix = (_staged_json(path) for path in (CORPUS, ORACLE, MATRIX))
    forbidden_in_corpus = set(corpus["forbidden_fields"])
    corpus_case_keys = set().union(*(set(case) for case in corpus["cases"]))
    required_probe_ids = {"A0-M2-P01", "A0-M2-P02", "A0-M2-P03"}
    return {
        "four_independent_sector_inputs": len(corpus["cases"]) == 4 and {case["sector"] for case in corpus["cases"]} == {"ai_semis", "saas", "healthcare", "banks"},
        "expected_output_absent_from_actual_corpus": forbidden_in_corpus.isdisjoint(corpus_case_keys),
        "oracle_runtime_access_forbidden": oracle["runtime_input_forbidden"] is True and "must_not_import_read_hash_or_receive" in oracle["access_rule"],
        "typed_stop_matrix_complete": {probe["probe_id"] for probe in matrix["probes"]} == required_probe_ids,
        "design_execution_counts_zero": all(value == 0 for value in matrix["design_execution_counts"].values()),
        "future_actual_requires_external_admission_and_receipt": matrix["future_actual_authority"]["external_package_admission_required"] is True and matrix["future_actual_authority"]["single_use_execution_receipt_required"] is True and matrix["future_actual_authority"]["actual_probes_currently_authorized"] is False,
        "package_binds_required_domains": all(fragment in " ".join(package["input_file_sha256"]) for fragment in ("full_serializer", "pack_registry", "pack_selection", "legacy_objective_adapter", "model_admission", "shadow_orchestration")),
        "no_mutable_governance_docs_in_package": all(not path.startswith("docs/") for path in package["input_file_sha256"]),
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    package = build_package()
    verification = verify_package(package)
    checks = design_checks(package)
    failures = [name for name, passed in checks.items() if not passed]
    if verification["status"] != "pass":
        failures.append("package_verification_failed")
    gate_payload = {
        "result_version": "finsight_point01_m2_a1_design_package_freeze_gate_result_v1_0",
        "scope": "M2_A1_design_and_package_freeze_only",
        "status": "design_package_frozen_pending_independent_review" if not failures else "fail_closed",
        "package_digest": package["package_digest"],
        "package_verify": verification,
        "checks": checks,
        "failures": sorted(failures),
        "execution_counts": {"compiler_or_shadow_fixture_runs": 0, "model_calls": 0, "network_requests": 0, "external_tool_calls": 0, "provider_calls": 0, "store_writes": 0, "business_case_mutations": 0, "legacy_authority_mutations": 0},
        "next_step_requires_total_reviewer": "Review M2-A1 design/package only. Actual A0-M2-P01/P02/P03 requires a separate exact external admission and single-use execution receipt.",
        "boundary": "This runner reads staged files and emits a static package manifest only. It does not import or invoke compiler/shadow runtime, tests, model, network, tool, provider or store paths.",
    }
    gate = {**gate_payload, "gate_digest": canonical_digest(gate_payload)}
    _write(OUTPUT_PACKAGE, package)
    _write(OUTPUT_GATE, gate)
    print(json.dumps({"status": gate["status"], "package_digest": package["package_digest"], "output": str(OUTPUT_GATE)}, ensure_ascii=False))
    return 0 if gate["status"] == "design_package_frozen_pending_independent_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
