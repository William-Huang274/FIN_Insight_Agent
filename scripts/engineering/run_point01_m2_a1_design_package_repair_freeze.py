"""Freeze the M2-A1 design package without importing or running M2 runtime.

This runner is deliberately standard-library-only.  It reads only Git-index
bytes, validates synthetic future-input/oracle/scenario contracts, and writes
static review artifacts.  It never imports the M2 compiler, shadow compiler,
adapter, pack registry, serializer, model/provider or store modules.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CORPUS = "configs/engineering_handoff/point01_m2_a1_adversarial_input_corpus_v1_1.json"
ORACLE = "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json"
MATRIX = "configs/engineering_handoff/point01_m2_a1_owner_authority_typed_stop_matrix_v1_1.json"
A0_DESIGN = "configs/engineering_handoff/point01_m1_m5_adversarial_retro_audit_design_freeze_v1_0.json"
OUTPUT_PACKAGE = ROOT / "data/manifests/point01_m2_a1_adversarial_audit_package_manifest_v1_1.json"
OUTPUT_GATE = ROOT / "data/manifests/point01_m2_a1_design_package_repair_freeze_gate_result_v1_1.json"

SCHEMA_VERSION = "finsight_point01_m2_a1_adversarial_audit_package_manifest_v1_1"
PACKAGE_REF = "point01-m2-a1-independent-adversarial-audit-package-v2-full-contract"
SCOPE = "M2_A1_design_and_package_repair_only"
AUTHORITY_BOUNDARY = (
    "no_actual_compiler_or_shadow_fixture_no_model_network_tool_provider_fixed_production_business_or_legacy_store_open_or_write"
)
EXTERNAL_ADMISSION_REF = "point01-m2-a1-total-reviewer-package-admission:v2"
EXPECTED_A0_DESIGN_DIGEST = "75a76e24a3a730b82942b9861b9d203a5ec0e735a936dbc229d1c68681ff250d"
FIXED_APPROVAL_PATH = ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"
FIXED_APPROVAL_SHA256 = "ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PACKAGE_INPUTS = (
    A0_DESIGN,
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
    "scripts/engineering/run_point01_m2_a1_design_package_repair_freeze.py",
    "tests/contract/test_point01_m2_a1_design_package_static.py",
)

PACKAGE_PAYLOAD_FIELDS = (
    "schema_version",
    "scope",
    "package_ref",
    "authority_boundary",
    "input_bytes_source",
    "a0_design_digest",
    "input_file_sha256",
    "fixed_store_fingerprints",
    "corpus_digest",
    "oracle_digest",
    "scenario_matrix_digest",
    "package_admission_ref",
    "package_admission_required",
    "single_use_execution_receipt_required",
    "actual_probes_currently_authorized",
    "future_actual_executable_package_refreeze_required",
)
PACKAGE_FIELDS = frozenset((*PACKAGE_PAYLOAD_FIELDS, "package_digest"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _staged_bytes(relative_path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"m2_a1_repair_package_input_not_staged:{relative_path}")
    return completed.stdout


def _staged_json(relative_path: str) -> dict[str, Any]:
    return json.loads(_staged_bytes(relative_path).decode("utf-8"))


def _package_payload(package: dict[str, Any]) -> dict[str, Any]:
    return {field: package[field] for field in PACKAGE_PAYLOAD_FIELDS}


def package_payload_digest(package: dict[str, Any]) -> str:
    return canonical_digest(_package_payload(package))


def _fixed_store_fingerprints() -> dict[str, Any]:
    return {
        "fixed_approval_store": {
            "path": FIXED_APPROVAL_PATH,
            "sha256": FIXED_APPROVAL_SHA256,
            "access": "future_actual_canary_must_reject_open_read_or_write",
        },
        "canonical_or_business_store_absence_manifest": {
            "status": "explicit_absence_no_M2_A1_fixed_canonical_or_business_store_registered",
            "registered_paths": [],
            "enforcement": "future_actual_canary_must_reject_every_nonallowlisted_store_path_or_ambient_resolution",
        },
    }


def build_package() -> dict[str, Any]:
    corpus, oracle, matrix, a0_design = (_staged_json(path) for path in (CORPUS, ORACLE, MATRIX, A0_DESIGN))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "package_ref": PACKAGE_REF,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_bytes_source": "git_index",
        "a0_design_digest": str(a0_design.get("design_digest", "")),
        "input_file_sha256": {path: hashlib.sha256(_staged_bytes(path)).hexdigest() for path in PACKAGE_INPUTS},
        "fixed_store_fingerprints": _fixed_store_fingerprints(),
        "corpus_digest": canonical_digest(corpus),
        "oracle_digest": canonical_digest(oracle),
        "scenario_matrix_digest": canonical_digest(matrix),
        "package_admission_ref": EXTERNAL_ADMISSION_REF,
        "package_admission_required": True,
        "single_use_execution_receipt_required": True,
        "actual_probes_currently_authorized": False,
        "future_actual_executable_package_refreeze_required": True,
    }
    return {**payload, "package_digest": canonical_digest(payload)}


def _schema_errors(package: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    keys = set(package)
    missing = sorted(PACKAGE_FIELDS - keys)
    unexpected = sorted(keys - PACKAGE_FIELDS)
    if missing:
        errors.append(f"missing_fields:{','.join(missing)}")
    if unexpected:
        errors.append(f"unexpected_fields:{','.join(unexpected)}")
    if missing:
        return errors
    if package["schema_version"] != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    expected_literals = {
        "scope": SCOPE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_bytes_source": "git_index",
        "package_admission_ref": EXTERNAL_ADMISSION_REF,
    }
    for field, expected in expected_literals.items():
        if package.get(field) != expected:
            errors.append(f"{field}_invalid")
    if not isinstance(package.get("package_ref"), str) or not package["package_ref"].strip():
        errors.append("package_ref_invalid")
    for field in ("a0_design_digest", "corpus_digest", "oracle_digest", "scenario_matrix_digest", "package_digest"):
        if not _is_sha256(package.get(field)):
            errors.append(f"{field}_must_be_sha256")
    if package.get("package_admission_required") is not True:
        errors.append("package_admission_required_must_be_true")
    if package.get("single_use_execution_receipt_required") is not True:
        errors.append("single_use_execution_receipt_required_must_be_true")
    if package.get("actual_probes_currently_authorized") is not False:
        errors.append("actual_probes_currently_authorized_must_be_false")
    if package.get("future_actual_executable_package_refreeze_required") is not True:
        errors.append("future_actual_executable_package_refreeze_required_must_be_true")
    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(PACKAGE_INPUTS):
        errors.append("input_file_sha256_set_invalid")
    elif any(not _is_sha256(value) for value in hashes.values()):
        errors.append("input_file_sha256_digest_invalid")
    if package.get("fixed_store_fingerprints") != _fixed_store_fingerprints():
        errors.append("fixed_store_fingerprints_invalid")
    return errors


def verify_package(package: dict[str, Any]) -> dict[str, Any]:
    try:
        calculated = package_payload_digest(package)
    except (KeyError, TypeError):
        return {"status": "package_schema_validation_failed", "schema_errors": _schema_errors(package), "mismatches": [], "calculated_package_digest": None}
    if package.get("package_digest") != calculated:
        return {"status": "package_digest_mismatch", "schema_errors": [], "mismatches": [], "calculated_package_digest": calculated}
    schema_errors = _schema_errors(package)
    if schema_errors:
        return {"status": "package_schema_validation_failed", "schema_errors": schema_errors, "mismatches": [], "calculated_package_digest": calculated}
    mismatches = []
    for relative_path, expected in sorted(package["input_file_sha256"].items()):
        if hashlib.sha256(_staged_bytes(relative_path)).hexdigest() != expected:
            mismatches.append(relative_path)
    a0_design = _staged_json(A0_DESIGN)
    if package["a0_design_digest"] != EXPECTED_A0_DESIGN_DIGEST or a0_design.get("design_digest") != EXPECTED_A0_DESIGN_DIGEST:
        mismatches.append("a0_design_digest")
    for path, digest_key, source in ((CORPUS, "corpus_digest", _staged_json(CORPUS)), (ORACLE, "oracle_digest", _staged_json(ORACLE)), (MATRIX, "scenario_matrix_digest", _staged_json(MATRIX))):
        if canonical_digest(source) != package[digest_key]:
            mismatches.append(f"{path}:{digest_key}")
    return {"status": "pass" if not mismatches else "package_input_digest_mismatch", "schema_errors": [], "mismatches": mismatches, "calculated_package_digest": calculated}


def verify_external_admission(package: dict[str, Any], admission: dict[str, Any] | None) -> dict[str, Any]:
    """Future actual authority check; this repair package never creates an admission."""

    if admission is None:
        return {"status": "package_admission_required"}
    required = {"admission_ref", "reviewer_identity", "decision", "package_ref", "package_digest", "scope", "authority_boundary"}
    if set(admission) != required:
        return {"status": "package_admission_schema_invalid"}
    expected = {"admission_ref": package["package_admission_ref"], "reviewer_identity": "william/003/total_reviewer", "decision": "admitted", "package_ref": package["package_ref"], "package_digest": package["package_digest"], "scope": package["scope"], "authority_boundary": package["authority_boundary"]}
    mismatch = sorted(field for field, value in expected.items() if admission.get(field) != value)
    return {"status": "pass" if not mismatch else "package_admission_binding_mismatch", "mismatch_fields": mismatch}


def _all_mapping_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_all_mapping_keys(item) for item in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_all_mapping_keys(item) for item in value)) if value else set()
    return set()


def _nonempty_strings(values: Any) -> bool:
    return isinstance(values, list) and bool(values) and all(isinstance(value, str) and value for value in values)


def validate_design_contracts(corpus: dict[str, Any], oracle: dict[str, Any], matrix: dict[str, Any]) -> dict[str, Any]:
    """Strict static validation; it never instantiates any M2 runtime type."""

    errors: list[str] = []
    expected_sectors = {"ai_semis", "saas", "healthcare", "banks"}
    expected_case_scope = {"tenant_id", "project_id", "case_id", "actor_snapshot_ref", "permission_snapshot_ref", "correlation_id", "created_at", "recorded_at"}
    expected_adapters = {"CaseScope", "CompilerInputSeed", "LegacyResearchObjective", "PackVersionMetadata"}
    if corpus.get("schema_version") != "finsight_point01_m2_a1_adversarial_input_corpus_v1_1":
        errors.append("corpus_schema_invalid")
    if set(corpus.get("adapter_alignment", {})) != expected_adapters:
        errors.append("corpus_adapter_alignment_invalid")
    forbidden = set(corpus.get("forbidden_fields", []))
    if forbidden & _all_mapping_keys(corpus.get("cases", [])):
        errors.append("corpus_contains_forbidden_oracle_field")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or len(cases) != 4:
        errors.append("corpus_case_count_invalid")
        cases = []
    case_ids: set[str] = set()
    case_by_id: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict):
            errors.append("corpus_case_not_mapping")
            continue
        case_id, sector = case.get("case_id"), case.get("sector")
        if not isinstance(case_id, str) or case_id in case_ids:
            errors.append("corpus_case_id_invalid_or_duplicate")
            continue
        case_ids.add(case_id)
        case_by_id[case_id] = case
        if sector not in expected_sectors:
            errors.append(f"corpus_sector_invalid:{case_id}")
        scope = case.get("case_scope")
        if not isinstance(scope, dict) or set(scope) != expected_case_scope or scope.get("case_id") != case_id or not all(isinstance(value, str) and value for value in scope.values()):
            errors.append(f"case_scope_invalid:{case_id}")
        seed = case.get("compiler_input_seed")
        legacy = case.get("legacy_research_objective")
        if not isinstance(seed, dict) or not isinstance(legacy, dict) or not isinstance(legacy.get("payload"), dict):
            errors.append(f"compiler_or_legacy_seed_invalid:{case_id}")
            continue
        payload = legacy["payload"]
        seed_required = {"query", "as_of", "universe", "language", "compiler_policy_ref", "sector", "report_type", "pack_selection", "required_cells_source", "required_cells_minimum"}
        if set(seed) != seed_required or seed.get("sector") != sector or seed.get("required_cells_source") != "legacy_research_objective.payload.required_items_via_adapter" or seed.get("required_cells_minimum") != 10:
            errors.append(f"compiler_input_seed_shape_invalid:{case_id}")
        if any(seed.get(field) != payload.get(field) for field in ("query", "as_of", "universe", "language")):
            errors.append(f"compiler_legacy_seed_mismatch:{case_id}")
        if legacy.get("adapter_function") != "adapt_legacy_research_objective":
            errors.append(f"legacy_adapter_invalid:{case_id}")
        required_items = payload.get("required_items")
        if not isinstance(required_items, list) or len(required_items) < 10:
            errors.append(f"legacy_required_items_invalid:{case_id}")
        else:
            ids = [item.get("required_item_id") for item in required_items if isinstance(item, dict)]
            if len(ids) != len(required_items) or len(set(ids)) != len(ids):
                errors.append(f"legacy_required_item_ids_invalid:{case_id}")
        packs = case.get("pack_version_metadata", {}).get("versions") if isinstance(case.get("pack_version_metadata"), dict) else None
        selected = seed.get("pack_selection", {}) if isinstance(seed.get("pack_selection"), dict) else {}
        if not isinstance(packs, list) or {pack.get("scope_kind") for pack in packs if isinstance(pack, dict)} != {"universal", "sector", "report_type"}:
            errors.append(f"pack_metadata_scope_invalid:{case_id}")
        elif not all(isinstance(pack.get("payload_digest"), str) and _is_sha256(pack.get("payload_digest")) and pack.get("pack_version_id") == f"{pack.get('pack_id')}:v{pack.get('pack_version')}" for pack in packs):
            errors.append(f"pack_metadata_version_invalid:{case_id}")
        elif not all(ref in {pack.get("pack_version_id") for pack in packs} for refs in selected.values() if isinstance(refs, list) for ref in refs):
            errors.append(f"pack_selection_ref_not_in_metadata:{case_id}")
    if {case.get("sector") for case in cases if isinstance(case, dict)} != expected_sectors:
        errors.append("corpus_sector_coverage_invalid")

    if oracle.get("schema_version") != "finsight_point01_m2_a1_independent_expected_cell_oracle_v1_1" or oracle.get("runtime_input_forbidden") is not True:
        errors.append("oracle_schema_or_access_invalid")
    if "must_not_import_read_hash_receive" not in str(oracle.get("access_rule", "")):
        errors.append("oracle_access_rule_invalid")
    oracle_cases = oracle.get("oracle_cases")
    oracle_refs: set[str] = set()
    sector_signatures: set[str] = set()
    if not isinstance(oracle_cases, list) or len(oracle_cases) != 4:
        errors.append("oracle_case_count_invalid")
        oracle_cases = []
    for expected in oracle_cases:
        if not isinstance(expected, dict):
            errors.append("oracle_case_not_mapping")
            continue
        ref = expected.get("input_case_ref")
        if not isinstance(ref, str) or ref not in case_by_id or ref in oracle_refs:
            errors.append("oracle_case_ref_invalid_or_duplicate")
        else:
            oracle_refs.add(ref)
            if expected.get("sector") != case_by_id[ref].get("sector"):
                errors.append(f"oracle_sector_mismatch:{ref}")
        selection = expected.get("expected_selection")
        cells = expected.get("required_cells")
        if not isinstance(selection, dict) or not _nonempty_strings(selection.get("required_pack_version_ids")) or not _nonempty_strings(expected.get("expected_archetype_families")):
            errors.append(f"oracle_selection_or_archetype_invalid:{ref}")
        if not isinstance(cells, list) or len(cells) < 4 or any(not isinstance(cell, dict) or not isinstance(cell.get("cell_key"), str) or not isinstance(cell.get("owner_role"), str) or cell.get("required") is not True or not _nonempty_strings(cell.get("required_evidence_roles")) or not isinstance(cell.get("forbidden_evidence_roles"), list) for cell in cells):
            errors.append(f"oracle_cell_contract_invalid:{ref}")
        if not isinstance(expected.get("legacy_semantic_loss_expectations"), list) or not expected.get("legacy_semantic_loss_expectations") or not _nonempty_strings(expected.get("must_not_assert")):
            errors.append(f"oracle_semantic_loss_contract_invalid:{ref}")
        signature = canonical_digest({"selection": selection, "archetypes": expected.get("expected_archetype_families"), "cells": cells, "forbidden": expected.get("forbidden_cells")})
        if signature in sector_signatures:
            errors.append("oracle_sector_specificity_invalid")
        sector_signatures.add(signature)
    if oracle_refs != case_ids:
        errors.append("oracle_corpus_coverage_invalid")

    if matrix.get("schema_version") != "finsight_point01_m2_a1_owner_authority_typed_stop_matrix_v1_1":
        errors.append("matrix_schema_invalid")
    counts = matrix.get("design_execution_counts")
    if not isinstance(counts, dict) or not counts or any(value != 0 for value in counts.values()):
        errors.append("design_execution_counts_nonzero_or_invalid")
    authority = matrix.get("future_actual_authority")
    if not isinstance(authority, dict) or authority.get("actual_probes_currently_authorized") is not False or authority.get("external_package_admission_required") is not True or authority.get("single_use_execution_receipt_required") is not True or authority.get("future_actual_requires_executable_package_refreeze") is not True:
        errors.append("future_actual_authority_invalid")
    if matrix.get("fixed_store_fingerprints") != _fixed_store_fingerprints():
        errors.append("matrix_fixed_store_fingerprints_invalid")
    topology = matrix.get("future_execution_topology")
    if not isinstance(topology, dict) or set(topology) != {"actual_runner", "oracle_evaluator", "reviewer_gate", "package_boundary"} or "immutable_actual_result_digest" not in json.dumps(topology, sort_keys=True):
        errors.append("future_execution_topology_invalid")
    canaries = matrix.get("future_actual_canary_contract")
    if not isinstance(canaries, dict) or set(canaries) != {"oracle_access_canary", "store_access_canary", "transport_constructor_canary", "model_admission_canary", "invariant"}:
        errors.append("future_actual_canary_contract_invalid")
    probes = matrix.get("probes")
    expected_scenarios = {
        "A0-M2-P01": {"p01-baseline-separated-input", "p01-oracle-path-access", "p01-oracle-hash-access", "p01-oracle-mutation-invariance"},
        "A0-M2-P02": {"p02-valid-versioned-baseline", "p02-unversioned-pack-ref", "p02-stale-or-superseded-pack", "p02-parent-or-digest-mismatch", "p02-selector-conflict", "p02-artifact-envelope-replay-mismatch"},
        "A0-M2-P03": {"p03-feature-off", "p03-model-denied", "p03-fixed-store-path", "p03-ambient-resolver", "p03-provider-constructor", "p03-network-tool-transport"},
    }
    if not isinstance(probes, list) or {probe.get("probe_id") for probe in probes if isinstance(probe, dict)} != set(expected_scenarios):
        errors.append("probe_ids_invalid")
    else:
        for probe in probes:
            scenario_ids: set[str] = set()
            scenarios = probe.get("scenarios") if isinstance(probe, dict) else None
            if not isinstance(scenarios, list):
                errors.append(f"scenario_list_invalid:{probe.get('probe_id')}")
                continue
            for scenario in scenarios:
                if not isinstance(scenario, dict):
                    errors.append("scenario_not_mapping")
                    continue
                scenario_ids.add(str(scenario.get("scenario_id", "")))
                required_fields = {"scenario_id", "input_ref", "mutation", "expected_typed_stop", "owner", "actual_assertions", "oracle_assertions"}
                if set(scenario) != required_fields or scenario.get("input_ref") not in case_ids or not _nonempty_strings(scenario.get("actual_assertions")) or not _nonempty_strings(scenario.get("oracle_assertions")):
                    errors.append(f"scenario_contract_invalid:{scenario.get('scenario_id')}")
            if scenario_ids != expected_scenarios[probe["probe_id"]]:
                errors.append(f"scenario_coverage_invalid:{probe['probe_id']}")
    checks = {
        "synthetic_compiler_consumable_four_sector_inputs": not any(error.startswith(prefix) for prefix in ("corpus_", "case_scope_", "compiler_", "legacy_", "pack_" ) for error in errors),
        "sector_specific_independent_oracle": not any(error.startswith(prefix) for prefix in ("oracle_",) for error in errors),
        "scenario_level_p01_p02_p03_matrix": not any(error.startswith(prefix) for prefix in ("probe_", "scenario_", "future_actual_", "future_execution_", "matrix_" ) for error in errors),
        "actual_oracle_topology_frozen": "future_execution_topology_invalid" not in errors and "oracle_schema_or_access_invalid" not in errors,
        "future_access_canaries_and_zero_counts_frozen": "future_actual_canary_contract_invalid" not in errors and "design_execution_counts_nonzero_or_invalid" not in errors,
        "actual_still_not_authorized": "future_actual_authority_invalid" not in errors,
    }
    return {"status": "pass" if not errors else "fail_closed", "errors": sorted(set(errors)), "checks": checks}


def build_gate(package: dict[str, Any]) -> dict[str, Any]:
    corpus, oracle, matrix = (_staged_json(path) for path in (CORPUS, ORACLE, MATRIX))
    package_verify = verify_package(package)
    design_verify = validate_design_contracts(corpus, oracle, matrix)
    failures = [name for name, passed in design_verify["checks"].items() if not passed]
    if package_verify["status"] != "pass":
        failures.append("package_verification_failed")
    payload = {
        "result_version": "finsight_point01_m2_a1_design_package_repair_freeze_gate_result_v1_1",
        "scope": SCOPE,
        "status": "design_package_repaired_pending_independent_review" if not failures else "fail_closed",
        "package_ref": package["package_ref"],
        "package_digest": package["package_digest"],
        "package_verify": package_verify,
        "design_contract_verify": design_verify,
        "future_actual_admission_status": verify_external_admission(package, None)["status"],
        "failures": sorted(failures),
        "execution_counts": {"compiler_or_shadow_fixture_runs": 0, "model_calls": 0, "network_requests": 0, "external_tool_calls": 0, "provider_calls": 0, "store_open_attempts": 0, "store_writes": 0, "business_case_mutations": 0, "legacy_authority_mutations": 0},
        "next_step_requires_total_reviewer": "Review the repaired M2-A1 design package only. Any actual A0-M2-P01/P02/P03 run requires a newly refrozen executable package, exact external admission and a single-use execution receipt.",
        "boundary": "Static staged-byte validation only. This runner does not import or invoke M2 compiler/shadow runtime, model, network, tool, provider, transport, store or business authority paths.",
    }
    return {**payload, "gate_digest": canonical_digest(payload)}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    package = build_package()
    gate = build_gate(package)
    _write(OUTPUT_PACKAGE, package)
    _write(OUTPUT_GATE, gate)
    print(json.dumps({"status": gate["status"], "package_digest": package["package_digest"], "gate_digest": gate["gate_digest"]}, ensure_ascii=False))
    return 0 if gate["status"] == "design_package_repaired_pending_independent_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
