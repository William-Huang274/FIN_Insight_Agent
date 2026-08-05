from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
RUNTIME = ROOT / "configs" / "runtime"
CONTRACT_TESTS = ROOT / "tests" / "contract"
DEFAULT_DB = ROOT / "data" / "workbench_private" / "workbench.sqlite"
DEFAULT_BASELINE = RELEASES / (
    "fin_ia_0_1_3_repair_closeout_s0_01_delta_inheritance_namespace_"
    "and_current_truth_baseline_v1_0.json"
)
DEFAULT_ACTIVE_SUITE = RELEASES / (
    "fin_ia_0_1_3_repair_closeout_s0_01_active_test_suite_successor_v1_0.json"
)
PREDECESSOR_ACTIVE_SUITE = RELEASES / (
    "fin_ia_0_1_2_s0_current_active_test_suite_manifest_v2_3.json"
)
S5_HANDOFF = RELEASES / (
    "fin_ia_0_1_2_s5_decision_only_honest_block_candidate_freeze_"
    "and_fin_0_1_3_handoff_v1_0.json"
)

REUSABLE_TEST_NAMES = {
    "test_fin_0_1_3_s0_reference_role_registry_and_collect_all_compiler.py",
    "test_fin_0_1_3_s0_runtime_resource_registry_and_dependency_compiler.py",
    "test_fin_0_1_3_s0_typed_environment_semantic_parity.py",
}


class S001BaselineError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S001BaselineError(code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _historical_paths() -> list[Path]:
    releases = [
        path
        for path in RELEASES.glob("fin_ia_0_1_3*.json")
        if not path.name.startswith("fin_ia_0_1_3_repair_closeout_")
    ]
    runtime = list(RUNTIME.glob("fin_ia_0_1_3*.json"))
    tests = [
        path
        for path in CONTRACT_TESTS.glob("test_fin_0_1_3*.py")
        if not path.name.startswith("test_fin_0_1_3_repair_closeout_")
    ]
    return sorted([*releases, *runtime, *tests], key=lambda item: item.as_posix())


def _classification(path: Path) -> tuple[str, str]:
    relative = path.relative_to(ROOT).as_posix()
    if relative.startswith("configs/releases/"):
        return (
            "historical_event_not_current_authority",
            "preserve_immutable_stage_decision_or_projection_but_do_not_gate_new_FIN_0_1_3",
        )
    if relative.startswith("configs/runtime/"):
        if "current_program_projection" in path.name:
            return (
                "superseded_projection_not_reusable_as_current_truth",
                "retain_for_history_only",
            )
        return (
            "reusable_version_neutral_candidate_pending_013_S0_02",
            "may_reuse_only_by_exact_digest_after_semantic_and_dependency_revalidation",
        )
    if path.name in REUSABLE_TEST_NAMES:
        return (
            "reusable_test_candidate_pending_013_S0_02",
            "not_a_current_gate_until_renamed_or_bound_by_canonical_successor",
        )
    return (
        "historical_test_not_current_gate",
        "preserve_historical_assertion_without_promoting_old_product_version_authority",
    )


def build_historical_inventory() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in _historical_paths():
        classification, disposition = _classification(path)
        rows.append(
            {
                "ref": path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(path),
                "classification": classification,
                "disposition": disposition,
            }
        )
    return rows


def _safe_review_projection(db_path: Path) -> dict[str, Any]:
    _require(db_path.is_file(), "private_workbench_db_missing")
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        session_count = int(
            conn.execute("SELECT COUNT(*) FROM t07_reviewer_sessions").fetchone()[0]
        )
        event_count = int(
            conn.execute("SELECT COUNT(*) FROM t07_reviewer_security_events").fetchone()[0]
        )
        decisions = conn.execute(
            "SELECT payload_json FROM t07_reviewer_decisions ORDER BY decision_id"
        ).fetchall()
    _require(len(decisions) == 1, "expected_one_bounded_NVDA_decision")
    decision = json.loads(str(decisions[0][0]))
    allowed = {
        "case_key": decision.get("case_key"),
        "action": decision.get("action"),
        "decided_at": decision.get("decided_at"),
        "manifest_digest": decision.get("manifest_digest"),
        "case_projection_digest": decision.get("case_projection_digest"),
        "handoff_digest": decision.get("handoff_digest"),
        "packet_digest": decision.get("packet_digest"),
        "authenticated_reviewer_identity": decision.get(
            "authenticated_reviewer_identity"
        ),
        "qualified_human_review": decision.get("qualified_human_review"),
        "bounded_NVDA_R3": decision.get("bounded_NVDA_R3"),
        "release_qualified": decision.get("release_qualified"),
    }
    _require(
        allowed["case_key"] == "NVDA"
        and allowed["action"] == "accept_exact_version"
        and allowed["authenticated_reviewer_identity"] is True
        and allowed["qualified_human_review"] is True
        and allowed["bounded_NVDA_R3"] is True
        and allowed["release_qualified"] is False,
        "bounded_NVDA_review_truth_invalid",
    )
    body = {
        "private_store_counts": {
            "review_sessions": session_count,
            "security_events": event_count,
            "qualified_decisions": len(decisions),
        },
        "allowlisted_decision_projection": allowed,
        "projection_policy": {
            "database_open_mode": "read_only",
            "private_identity_projected": False,
            "review_text_projected": False,
            "secret_material_projected": False,
        },
    }
    return {**body, "projection_digest": _canonical_digest(body)}


def _binding(
    role: str, path: Path, *, canonical_ref_path: Path | None = None
) -> dict[str, str]:
    _require(path.is_file(), f"missing_source_binding:{path}")
    ref_path = canonical_ref_path or path
    return {
        "role": role,
        "ref": ref_path.relative_to(ROOT).as_posix(),
        "sha256": _sha256(path),
    }


def _current_gate_refs(active_suite: dict[str, Any]) -> list[str]:
    return [
        str(ref)
        for suite in active_suite.get("suites", [])
        if suite.get("selected") and suite.get("gates_current_release")
        for ref in suite.get("test_paths", [])
    ]


def validate_baseline(
    baseline: dict[str, Any], active_suite: dict[str, Any]
) -> None:
    inventory = baseline["historical_namespace_inventory"]
    _require(inventory["counts"] == {"release_configs": 18, "runtime_configs": 16, "contract_tests": 13, "total": 47}, "historical_namespace_count_drift")
    _require(len(inventory["assets"]) == 47, "historical_asset_inventory_incomplete")
    _require(
        inventory["inventory_digest"] == _canonical_digest(inventory["assets"]),
        "historical_asset_inventory_digest_invalid",
    )
    current_refs = _current_gate_refs(active_suite)
    _require(
        current_refs
        == [
            "tests/contract/test_fin_0_1_3_repair_closeout_s0_01_delta_inheritance_namespace_and_current_truth_baseline.py"
        ],
        "canonical_current_gate_ref_invalid",
    )
    _require(
        not any("test_fin_0_1_3_s0_" in ref for ref in current_refs),
        "old_FIN_0_1_3_test_promoted_to_current_gate",
    )
    review = baseline["secret_safe_T07_C_current_truth"]
    _require(
        review["private_store_counts"]
        == {"review_sessions": 1, "security_events": 4, "qualified_decisions": 1},
        "private_review_count_drift",
    )
    forbidden_keys = {"credential_digest", "session_id", "reviewer_ref", "reviewer_note"}
    _require(
        not forbidden_keys.intersection(review["allowlisted_decision_projection"]),
        "private_review_field_projected",
    )
    _require(
        baseline["inheritance_policy"][
            "old_R2_R3_auto_promotable_after_changed_input_data_or_contract"
        ]
        is False,
        "old_product_acceptance_auto_promotion_forbidden",
    )
    _require(
        set(baseline["observed_counts"].values()) == {0},
        "S0_01_must_remain_zero_call_and_zero_business_write",
    )


def materialize(
    *, db_path: Path, baseline_path: Path, active_suite_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    inventory_rows = build_historical_inventory()
    category_counts = {
        "historical_event_not_current_authority": 0,
        "superseded_projection_not_reusable_as_current_truth": 0,
        "reusable_version_neutral_candidate_pending_013_S0_02": 0,
        "reusable_test_candidate_pending_013_S0_02": 0,
        "historical_test_not_current_gate": 0,
    }
    for row in inventory_rows:
        category_counts[row["classification"]] += 1
    reusable_candidates = [
        row
        for row in inventory_rows
        if row["classification"].startswith("reusable_")
    ]
    active_suite = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_active_test_suite_v1_0",
        "manifest_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S0-01-ACTIVE-SUITE-R1",
        "created_at": "2026-08-06T14:00:00+08:00",
        "status": "canonical_S0_01_gate_only_old_namespace_not_current_authority",
        "predecessor": _binding("FIN_0_1_2_active_suite", PREDECESSOR_ACTIVE_SUITE),
        "suites": [
            {
                "suite_id": "canonical_repair_closeout_S0_01",
                "proof_class": "current_delta_inheritance_and_namespace_gate",
                "selected": True,
                "gates_current_release": True,
                "test_paths": [
                    "tests/contract/test_fin_0_1_3_repair_closeout_s0_01_delta_inheritance_namespace_and_current_truth_baseline.py"
                ],
            },
            {
                "suite_id": "old_FIN_0_1_3_reusable_candidates",
                "proof_class": "pending_exact_digest_semantic_revalidation",
                "selected": False,
                "gates_current_release": False,
                "candidate_assets": reusable_candidates,
                "promotion_owner": "013-S0-02",
            },
        ],
        "selection_policy": {
            "filename_version_match_establishes_authority": False,
            "historical_event_mutation_allowed": False,
            "reusable_candidate_requires_exact_digest": True,
            "reusable_candidate_requires_semantic_and_dependency_revalidation": True,
        },
    }
    _write_json(active_suite_path, active_suite)

    safe_review = _safe_review_projection(db_path)
    historical_inventory = {
        "counts": {
            "release_configs": 18,
            "runtime_configs": 16,
            "contract_tests": 13,
            "total": 47,
        },
        "classification_counts": category_counts,
        "assets": inventory_rows,
        "inventory_digest": _canonical_digest(inventory_rows),
    }
    baseline = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s0_01_delta_baseline_v1_0",
        "baseline_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S0-01-DELTA-BASELINE-R1",
        "recorded_at": "2026-08-06T14:00:00+08:00",
        "status": "S0_01_engineering_pass_canonical_namespace_and_current_truth_baseline_ready_S0_02_next",
        "authority": {
            "user_instruction": "你可以开始下一步了",
            "S0_01_implementation_authorized": True,
            "S0_02_or_later_implementation_authorized_by_this_record": False,
            "model_provider_network_source_or_external_tool_authorized": False,
        },
        "source_bindings": [
            _binding("FIN_0_1_2_terminal_handoff", S5_HANDOFF),
            _binding("predecessor_active_suite", PREDECESSOR_ACTIVE_SUITE),
            _binding(
                "three_case_current_projection",
                RELEASES
                / "fin_ia_0_1_2_s4_t06_a_current_product_projection_manifest_v1_0.json",
            ),
            _binding(
                "typed_return_replay_handoff",
                RELEASES
                / "fin_ia_0_1_2_s4_t06_c_current_review_control_and_t07_handoff_zero_call_implementation_v1_0.json",
            ),
            _binding(
                "bounded_reviewer_session_engineering",
                RELEASES
                / "fin_ia_0_1_2_s4_t07_b_bounded_internal_reviewer_session_zero_call_implementation_v1_0.json",
            ),
            _binding(
                "research_content_quality_hard_gate",
                ROOT
                / "docs"
                / "eval"
                / "FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md",
            ),
            _binding(
                "canonical_active_suite_successor",
                active_suite_path,
                canonical_ref_path=DEFAULT_ACTIVE_SUITE,
            ),
        ],
        "historical_namespace_inventory": historical_inventory,
        "secret_safe_T07_C_current_truth": safe_review,
        "inheritance_policy": {
            "unchanged_engineering_contract_may_be_reused_by_exact_digest": True,
            "old_product_attempts_remain_immutable": True,
            "old_R2_R3_auto_promotable_after_changed_input_data_or_contract": False,
            "old_FIN_0_1_3_filename_establishes_current_authority": False,
            "current_repair_closeout_namespace_prefix": "fin_ia_0_1_3_repair_closeout",
        },
        "inherited_capabilities": {
            "three_case_current_projection_shape_and_lineage_anchor": "inherited_engineering_anchor_not_release_truth",
            "typed_return_replay_and_handoff": "inherited_engineering_contract",
            "bounded_reviewer_session": "inherited_engineering_contract",
            "bounded_NVDA_R3_local_action": "projected_current_truth_not_new_candidate_acceptance",
            "research_content_quality_rubric": "current_requirement_runtime_translation_pending",
        },
        "stage_truth": {
            "FIN_0_1_2": "terminal_honest_block_release_not_qualified",
            "FIN_0_1_3_S0_01": "engineering_pass",
            "FIN_0_1_3_S0_02": "next_not_started",
            "FIN_0_1_3_S1_to_S5": "not_started",
            "FIN_0_2_definition": "unchanged",
            "release_qualified": False,
        },
        "observed_counts": {
            "credential_or_private_identity_reads": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_or_source_calls": 0,
            "business_runs_or_artifacts": 0,
            "private_store_writes": 0,
        },
        "next_action": "FIN-0.1.3-013-S0-02-SHARED-RUNTIME-ADMISSION-REPLAY-AND-HISTORICAL-PROOF-DEBT",
    }
    validate_baseline(baseline, active_suite)
    _write_json(baseline_path, baseline)
    return baseline, active_suite


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the zero-call FIN 0.1.3 repair-closeout S0-01 baseline."
    )
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB)
    parser.add_argument("--baseline-path", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--active-suite-path", type=Path, default=DEFAULT_ACTIVE_SUITE)
    args = parser.parse_args()
    baseline, _ = materialize(
        db_path=args.db_path,
        baseline_path=args.baseline_path,
        active_suite_path=args.active_suite_path,
    )
    print(
        json.dumps(
            {
                "status": baseline["status"],
                "historical_assets": baseline["historical_namespace_inventory"][
                    "counts"
                ]["total"],
                "private_store_counts": baseline["secret_safe_T07_C_current_truth"][
                    "private_store_counts"
                ],
                "next_action": baseline["next_action"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
