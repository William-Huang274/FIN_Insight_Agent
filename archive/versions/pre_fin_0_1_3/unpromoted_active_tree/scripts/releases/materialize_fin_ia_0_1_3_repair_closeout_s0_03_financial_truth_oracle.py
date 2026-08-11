from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.financial_semantic_truth_oracle import (  # noqa: E402
    evaluate_financial_truth,
)


POLICY_REF = Path(
    "configs/runtime/fin_ia_0_1_3_repair_closeout_"
    "financial_semantic_truth_oracle_v1_0.json"
)
FIXTURE_REF = Path(
    "tests/fixtures/fin_0_1_3/"
    "financial_semantic_truth_oracle_three_case_v1.json"
)
DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s0_03_"
    "financial_semantic_truth_oracle_classification_v1_0.json"
)
ACTIVE_SUITE_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s0_03_"
    "active_test_suite_successor_v1_0.json"
)
PREVIOUS_SUITE_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s0_02_"
    "active_test_suite_successor_v1_0.json"
)
TEST_REF = Path(
    "tests/contract/test_fin_0_1_3_repair_closeout_s0_03_"
    "financial_semantic_truth_oracle_classification.py"
)
MODULE_REF = Path("src/sec_agent/financial_semantic_truth_oracle.py")
CURRENT_DELL_PACK_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_evidence_pack_v1_0.json"
)
QUALITY_RUBRIC_REF = Path(
    "docs/eval/FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md"
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


def materialize() -> dict[str, Any]:
    policy = _load(POLICY_REF)
    fixture = _load(FIXTURE_REF)
    positive_results = [
        evaluate_financial_truth(row, row)
        for row in fixture["reviewed_truth_rows"]
    ]
    known = fixture["known_current_failure"]
    current_dell_result = evaluate_financial_truth(
        known["candidate"], known["reviewed_truth"]
    )
    if not all(row["financial_truth_entry_allowed"] for row in positive_results):
        raise ValueError("s0_03_reviewed_positive_fixture_failed")
    if current_dell_result["financial_truth_entry_allowed"]:
        raise ValueError("s0_03_known_dell_failure_not_detected")

    bindings = [
        _binding(POLICY_REF, "current_financial_semantic_oracle_policy"),
        _binding(FIXTURE_REF, "reviewed_three_case_truth_fixture_and_known_failure"),
        _binding(CURRENT_DELL_PACK_REF, "immutable_current_DELL_wrong_numeric_projection"),
        _binding(QUALITY_RUBRIC_REF, "current_research_quality_layer_requirement_successor"),
        _binding(MODULE_REF, "deterministic_truth_oracle_classifier"),
        _binding(TEST_REF, "canonical_S0_03_contract_and_mutation_test"),
        _binding(Path(__file__).resolve().relative_to(ROOT), "deterministic_materializer"),
        _binding(PREVIOUS_SUITE_REF, "S0_01_S0_02_active_suite_predecessor"),
    ]
    body = {
        "schema_version": (
            "fin_ia_0_1_3_repair_closeout_s0_03_"
            "financial_semantic_truth_oracle_classification_v1_0"
        ),
        "decision_id": (
            "FIN-0.1.3-013-S0-03-FINANCIAL-SEMANTIC-TRUTH-"
            "ORACLE-CLASSIFICATION"
        ),
        "recorded_at": "2026-08-06T00:00:00Z",
        "status": "engineering_pass_known_product_truth_failure_correctly_blocked",
        "classification_contract": {
            "layers": policy["layers"],
            "financial_truth_dimensions": policy["material_financial_dimensions"],
            "truth_gate_blocks": ["shape_integrity", "financial_truth"],
            "analysis_quality_is_release_blocking_at_owner_stage": True,
            "product_usability_is_release_blocking_at_owner_stage": True,
            "shape_test_count_never_substitutes_for_financial_truth": True,
        },
        "reviewed_fixture_result": {
            "case_keys": [row["case_key"] for row in fixture["reviewed_truth_rows"]],
            "reviewed_positive_count": len(positive_results),
            "reviewed_positive_pass_count": sum(
                int(row["financial_truth_entry_allowed"])
                for row in positive_results
            ),
            "known_current_DELL_result": current_dell_result,
            "current_DELL_product_truth_pass": False,
            "current_DELL_repair_owner": "013-S1-01",
        },
        "mutation_coverage": [
            "entity_and_issuer",
            "annual_quarter_and_duration",
            "unit_and_currency",
            "scale_and_normalized_value",
            "formula_recalculation",
            "filed_published_as_of_snapshot_roles",
            "shape_vs_financial_truth",
            "analysis_quality_vs_product_usability_stage_routing",
        ],
        "source_bindings": bindings,
        "root_cause_disposition": {
            "RC-P36-130": (
                "oracle_classification_closed_underlying_DELL_truth_repair_open_S1_01"
            ),
            "RC-P36-131": "unchanged_open_S2_S3_research_quality_runtime_translation",
            "RC-P36-132": "unchanged_open_S4_S5_product_workflow_and_release",
        },
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_or_source_calls": 0,
            "business_runs": 0,
            "business_artifacts": 0,
            "current_data_rows_rewritten": 0,
        },
        "stage_truth": {
            "FIN_0_1_3_S0_03": "engineering_pass",
            "FIN_0_1_3_S0": "complete",
            "FIN_0_1_3_S1": "not_started_entry_authorized_for_repair_only",
            "FIN_0_1_3_S2_to_S5": "not_started",
            "release_qualified": False,
        },
        "known_boundary": (
            "S0 completion means the gate detects and routes semantic truth failures. "
            "It does not make the current DELL number correct or authorize model/full-chain work."
        ),
        "next_action": (
            "FIN-0.1.3-013-S1-01-DELL-FINANCIAL-TEMPORAL-TRUTH-"
            "AND-TIME-ROLE-REPAIR"
        ),
    }
    decision = {**body, "decision_digest": canonical_digest(body)}
    _write(DECISION_REF, decision)

    previous = _load(PREVIOUS_SUITE_REF)
    selected = [*previous["selected_tests"], {"ref": TEST_REF.as_posix(), "stage": "013-S0-03"}]
    active_body = {
        "schema_version": (
            "fin_ia_0_1_3_repair_closeout_s0_03_active_test_suite_successor_v1_0"
        ),
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S0-ACTIVE-SUITE-R3",
        "status": "current_S0_complete_truth_repair_still_blocked",
        "selected_tests": selected,
        "historical_FIN_0_1_3_test_names_establish_current_authority": False,
        "decision_ref": DECISION_REF.as_posix(),
        "decision_sha256": _sha(DECISION_REF),
        "current_DELL_financial_truth_pass": False,
        "model_or_full_chain_authorized": False,
        "next_action": body["next_action"],
    }
    active = {**active_body, "suite_digest": canonical_digest(active_body)}
    _write(ACTIVE_SUITE_REF, active)
    return {
        "decision_ref": DECISION_REF.as_posix(),
        "decision_sha256": _sha(DECISION_REF),
        "active_suite_ref": ACTIVE_SUITE_REF.as_posix(),
        "active_suite_sha256": _sha(ACTIVE_SUITE_REF),
    }


if __name__ == "__main__":
    print(json.dumps(materialize(), ensure_ascii=False, indent=2))
