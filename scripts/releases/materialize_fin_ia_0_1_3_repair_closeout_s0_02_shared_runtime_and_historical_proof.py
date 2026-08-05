from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


BASELINE_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s0_01_"
    "delta_inheritance_namespace_and_current_truth_baseline_v1_0.json"
)
OLD_REGISTRY_REF = Path(
    "configs/runtime/fin_ia_0_1_3_runtime_resource_registry_v1_0.json"
)
SUCCESSOR_REGISTRY_REF = Path(
    "configs/runtime/fin_ia_0_1_3_repair_closeout_"
    "runtime_resource_registry_v1_0.json"
)
DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s0_02_"
    "shared_runtime_admission_replay_and_historical_proof_debt_v1_0.json"
)
ACTIVE_SUITE_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s0_02_"
    "active_test_suite_successor_v1_0.json"
)
NEW_TEST_REF = Path(
    "tests/contract/test_fin_0_1_3_repair_closeout_s0_02_"
    "shared_runtime_admission_replay_and_historical_proof_debt.py"
)
MISSING_RESOURCE_REF = Path(
    "configs/runtime/fin_ia_0_1_2_s4_t05_"
    "current_evidence_fact_candidate_pool_profiles_v1_0.json"
)


def _load(ref: Path) -> dict[str, Any]:
    value = json.loads((ROOT / ref).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{ref.as_posix()}")
    return value


def _sha(ref: Path) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def _write(ref: Path, value: dict[str, Any]) -> None:
    target = ROOT / ref
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _binding(ref: Path, role: str) -> dict[str, str]:
    return {"ref": ref.as_posix(), "sha256": _sha(ref), "role": role}


def _successor_registry() -> dict[str, Any]:
    registry = _load(OLD_REGISTRY_REF)
    baseline = _load(BASELINE_REF)
    candidate = next(
        row
        for row in baseline["historical_namespace_inventory"]["assets"]
        if row["ref"] == OLD_REGISTRY_REF.as_posix()
    )
    if candidate["sha256"] != _sha(OLD_REGISTRY_REF):
        raise ValueError("s0_02_old_registry_candidate_digest_drift")
    resource = ROOT / MISSING_RESOURCE_REF
    missing_row = {
        "resource_id": "fin_0_1_2.s4.current_evidence_fact_candidate_pool_profiles",
        "repo_relative_path": MISSING_RESOURCE_REF.as_posix(),
        "sha256": hashlib.sha256(resource.read_bytes()).hexdigest(),
        "bytes": resource.stat().st_size,
        "classification": "deterministic_fact_candidate_profile_set",
        "consumer_ids": [
            "apps.workbench.fact_candidate_pool_planner.FactCandidatePoolPlanner.from_registry"
        ],
        "load_phase": "current_evidence_deterministic_contract_compilation",
        "required": True,
        "source_owner": "apps.workbench.backend.application.fact_candidate_pool_planner",
    }
    rows = [*registry["resources"], missing_row]
    rows.sort(key=lambda row: row["resource_id"])
    registry["registry_id"] = (
        "FIN-0.1.3-REPAIR-CLOSEOUT-S0-02-RUNTIME-RESOURCE-REGISTRY-R1"
    )
    registry["status"] = "tracked_typed_runtime_resource_authority"
    registry["resources"] = rows
    registry["resource_count"] = len(rows)
    registry["resource_bytes"] = sum(int(row["bytes"]) for row in rows)
    registry["resource_canonical_digest"] = canonical_digest(rows)
    return registry


def _candidate_rows() -> list[dict[str, Any]]:
    baseline = _load(BASELINE_REF)
    assets = {
        row["ref"]: row
        for row in baseline["historical_namespace_inventory"]["assets"]
    }
    dispositions = {
        "configs/runtime/fin_ia_0_1_3_reference_role_registry_v1_0.json": (
            "rejected_superseded_by_v1_1",
            "v1_0 lacks execution_started package-relative audit role",
        ),
        "configs/runtime/fin_ia_0_1_3_reference_role_registry_v1_1.json": (
            "reused_by_exact_digest",
            "latest typed role registry; closure and mutation tests pass",
        ),
        "configs/runtime/fin_ia_0_1_3_repository_reference_proof_policy_v3_0.json": (
            "reused_by_exact_digest",
            "binds reference registry v1_1 by exact digest",
        ),
        "configs/runtime/fin_ia_0_1_3_runtime_resource_registry_v1_0.json": (
            "rejected_incomplete_then_successor_materialized",
            "static detector finds one legitimate runtime resource absent from old registry",
        ),
        "configs/runtime/fin_ia_0_1_3_typed_environment_semantic_parity_v1_0.json": (
            "reused_by_exact_digest",
            "typed roots and semantic projection mutation tests pass",
        ),
        "tests/contract/test_fin_0_1_3_s0_reference_role_registry_and_collect_all_compiler.py": (
            "logic_reused_via_canonical_successor_test",
            "historical filename is not promoted as current authority",
        ),
        "tests/contract/test_fin_0_1_3_s0_runtime_resource_registry_and_dependency_compiler.py": (
            "rejected_stale_fixed_counts_then_replaced",
            "correctly exposed incomplete old registry but fixed counts are not a successor gate",
        ),
        "tests/contract/test_fin_0_1_3_s0_typed_environment_semantic_parity.py": (
            "logic_reused_via_canonical_successor_test",
            "historical filename is not promoted as current authority",
        ),
    }
    rows: list[dict[str, Any]] = []
    for ref, (disposition, reason) in dispositions.items():
        candidate = assets[ref]
        current_sha = _sha(Path(ref))
        if candidate["sha256"] != current_sha:
            raise ValueError(f"s0_02_candidate_digest_drift:{ref}")
        rows.append(
            {
                "ref": ref,
                "sha256": current_sha,
                "disposition": disposition,
                "reason": reason,
            }
        )
    return rows


def materialize() -> dict[str, Any]:
    _write(SUCCESSOR_REGISTRY_REF, _successor_registry())
    bindings = [
        _binding(BASELINE_REF, "canonical_S0_01_baseline"),
        _binding(
            Path("src/sec_agent/shared_admission_ledger.py"),
            "shared_content_addressed_consumption_ledger",
        ),
        _binding(
            Path(
                "apps/workbench/backend/application/"
                "fin_0_1_3_shared_admission_guarded_search.py"
            ),
            "current_FIN_0_1_3_mandatory_guarded_runner",
        ),
        _binding(
            Path(
                "apps/workbench/backend/application/"
                "fin_0_1_2_s4_t03_executable_agentic_search.py"
            ),
            "legacy_runner_with_optional_compatibility_hook",
        ),
        _binding(
            SUCCESSOR_REGISTRY_REF,
            "canonical_runtime_resource_registry_successor",
        ),
        _binding(
            Path(
                "tests/contract/test_fin_0_1_2_s4_t05_b_dell_"
                "current_search_fresh_admission_issuance.py"
            ),
            "historical_issuer_nonreplayable_receipt_test",
        ),
        _binding(
            Path("tests/contract/test_fin_0_1_2_s4_t05_c_mu_current_search_sequence.py"),
            "disposable_identity_historical_issuance_test",
        ),
        _binding(
            Path("tests/contract/test_fin_0_1_2_s4_t05_scope_entry_decision.py"),
            "historical_source_binding_role_test",
        ),
        _binding(
            Path("tests/contract/test_fin_0_1_s5_decision_only_honest_block_handoff.py"),
            "historical_living_document_role_test",
        ),
        _binding(Path(__file__).resolve().relative_to(ROOT), "deterministic_materializer"),
        _binding(NEW_TEST_REF, "canonical_S0_02_contract_and_mutation_test"),
    ]
    body = {
        "schema_version": (
            "fin_ia_0_1_3_repair_closeout_s0_02_shared_runtime_admission_"
            "replay_and_historical_proof_debt_v1_0"
        ),
        "decision_id": (
            "FIN-0.1.3-013-S0-02-SHARED-RUNTIME-ADMISSION-REPLAY-AND-"
            "HISTORICAL-PROOF-DEBT"
        ),
        "recorded_at": "2026-08-06T00:00:00Z",
        "status": "engineering_pass_zero_call_current_successor",
        "shared_admission_contract": {
            "key": "admission_digest",
            "store": "shared_SQLite_outside_disposable_runtime_roots",
            "reservation_before_any_source_model_provider_or_business_side_effect": True,
            "reservation_is_consumption_even_if_process_crashes": True,
            "automatic_release_retry_replay_or_renewal_after_crash": False,
            "cross_runtime_second_consumption": "fail_closed",
            "terminal_binding": [
                "admission_digest",
                "run_id",
                "attempt_id",
                "terminal_status",
                "terminal_phase",
                "terminal_code",
                "terminal_result_digest",
            ],
            "current_FIN_0_1_3_runner_requires_shared_ledger": True,
            "legacy_FIN_0_1_2_runner_optional_hook_is_history_compatibility_only": True,
        },
        "historical_proof_policy": {
            "old_decisions_and_receipts_are_never_rewritten_to_match_today": True,
            "immutable_artifact_binding_revalidated_against_current_bytes": True,
            "historical_mutable_code_or_living_document_binding": (
                "recorded_ref_and_digest_shape_preserved_not_rebased"
            ),
            "current_successor_must_bind_current_digest_at_new_issuance": True,
            "one_time_fresh_issuance_tests_use_disposable_unconsumed_roots": True,
            "fixed_consumed_runtime_root_is_not_a_replayable_test_fixture": True,
        },
        "candidate_revalidation": _candidate_rows(),
        "successor_runtime_resource_registry": {
            "ref": SUCCESSOR_REGISTRY_REF.as_posix(),
            "sha256": _sha(SUCCESSOR_REGISTRY_REF),
            "resource_count": 31,
            "missing_old_candidate_resource_closed": MISSING_RESOURCE_REF.as_posix(),
        },
        "source_bindings": bindings,
        "root_cause_disposition": {
            "RC-P36-115": "closed_by_current_mandatory_shared_exact_once_ledger",
            "RC-P36-128": "closed_by_historical_receipt_role_and_disposable_issuance_policy",
            "new_product_or_research_pass_created": False,
        },
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_or_source_calls": 0,
            "business_runs": 0,
            "business_artifacts": 0,
            "historical_receipts_rewritten": 0,
        },
        "stage_truth": {
            "FIN_0_1_3_S0_02": "engineering_pass",
            "FIN_0_1_3_S0": "in_progress_S0_03_pending",
            "FIN_0_1_3_S1_to_S5": "not_started",
            "release_qualified": False,
        },
        "next_action": "FIN-0.1.3-013-S0-03-FINANCIAL-SEMANTIC-TRUTH-ORACLE-CLASSIFICATION",
    }
    decision = {**body, "decision_digest": canonical_digest(body)}
    _write(DECISION_REF, decision)
    active_body = {
        "schema_version": (
            "fin_ia_0_1_3_repair_closeout_s0_02_active_test_suite_successor_v1_0"
        ),
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S0-ACTIVE-SUITE-R2",
        "status": "current_S0_01_and_S0_02_only",
        "selected_tests": [
            {
                "ref": (
                    "tests/contract/test_fin_0_1_3_repair_closeout_s0_01_"
                    "delta_inheritance_namespace_and_current_truth_baseline.py"
                ),
                "stage": "013-S0-01",
            },
            {"ref": NEW_TEST_REF.as_posix(), "stage": "013-S0-02"},
        ],
        "historical_FIN_0_1_3_test_names_establish_current_authority": False,
        "decision_ref": DECISION_REF.as_posix(),
        "decision_sha256": _sha(DECISION_REF),
        "next_action": body["next_action"],
    }
    active = {**active_body, "suite_digest": canonical_digest(active_body)}
    _write(ACTIVE_SUITE_REF, active)
    return {
        "decision_ref": DECISION_REF.as_posix(),
        "decision_sha256": _sha(DECISION_REF),
        "active_suite_ref": ACTIVE_SUITE_REF.as_posix(),
        "active_suite_sha256": _sha(ACTIVE_SUITE_REF),
        "successor_registry_ref": SUCCESSOR_REGISTRY_REF.as_posix(),
        "successor_registry_sha256": _sha(SUCCESSOR_REGISTRY_REF),
    }


if __name__ == "__main__":
    print(json.dumps(materialize(), ensure_ascii=False, indent=2))
