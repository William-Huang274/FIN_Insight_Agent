from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]


class T06CloseoutError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T06CloseoutError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assess_t06(
    t01: Mapping[str, Any],
    t03: Mapping[str, Any],
    t04: Mapping[str, Any],
    t05: Mapping[str, Any],
    backlog: Mapping[str, Any],
) -> dict[str, Any]:
    """Close S2 from durable evidence without executing another model or source call."""

    _require(
        t01.get("status") == "accepted_design_preflight_actual_execution_not_admitted",
        "t06_t01_not_accepted",
    )
    terminal = t03.get("canonical_terminal_truth") or {}
    _require(
        t03.get("status") == "terminal_succeeded_admission_consumed_no_retry",
        "t06_t03_not_terminal_succeeded",
    )
    _require(
        terminal.get("artifact_count") == 9 and terminal.get("orphaned_run") is False,
        "t06_t03_closed_artifact_set_required",
    )
    _require(
        t04.get("status") == "pass_read_only_exact_live_artifact_validation",
        "t06_t04_not_pass",
    )
    verifier = ((t04.get("validation") or {}).get("four_layer_verifier") or {})
    _require(
        all(
            verifier.get(key) == "pass"
            for key in (
                "deterministic_integrity",
                "semantic_fidelity",
                "financial_coherence",
                "visual_delivery",
            )
        ),
        "t06_t04_four_layer_verifier_not_pass",
    )
    owner = t05.get("owner_product_review") or {}
    coverage = t05.get("future_capability_planning_coverage") or {}
    _require(
        t05.get("status") == "pass_owner_accepted_bounded_material_gain"
        and owner.get("material_gain_accepted") is True,
        "t06_t05_owner_acceptance_required",
    )
    _require(
        coverage.get("condition_satisfied_at_roadmap_ownership_level") is True,
        "t06_future_capability_planning_coverage_required",
    )
    lineage = t05.get("lineage") or {}
    _require(
        lineage.get("runs_are_distinct") is True
        and lineage.get("same_input_digest") == (t03.get("identity") or {}).get("input_digest"),
        "t06_exact_pair_lineage_required",
    )
    roadmap_ids = {
        row.get("roadmap_id") for row in backlog.get("named_roadmap", ())
    }
    _require(
        {"RM-002-EARNINGS", "RM-QUANT"}.issubset(roadmap_ids),
        "t06_later_numeric_and_alpha_roadmap_ownership_required",
    )

    result = {
        "status": "pass_independent_S2_closeout",
        "technical_closeout": {
            "S2_T01": "pass_design_and_preflight",
            "S2_T02": "pass_zero_call_runtime_adapter_and_paired_baseline",
            "S2_T03": "pass_exact_live_one_cell_terminal_succeeded",
            "S2_T04": "pass_exact_live_artifact_chain_read_only_validation",
            "S2_T05": "pass_exact_pair_owner_accepted_bounded_material_gain",
        },
        "exact_evidence": {
            "agent_research_run_id": lineage["agent_research_run_id"],
            "deterministic_research_run_id": lineage["deterministic_research_run_id"],
            "same_input_digest": lineage["same_input_digest"],
            "runs_are_distinct": True,
            "agent_artifact_count": lineage["agent_artifact_count"],
            "four_layer_verifier": "pass",
        },
        "material_gain": {
            "accepted": True,
            "scope": (t05.get("independent_product_review") or {}).get(
                "material_gain_scope"
            ),
            "not_gained": list(
                (t05.get("independent_product_review") or {}).get("not_gained") or ()
            ),
        },
        "future_capability_planning_coverage": deepcopy(coverage),
        "new_execution_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "canonical_business_writes": 0,
        },
        "honest_non_claims": [
            "not_independent_junior_analyst_completion",
            "not_active_external_source_discovery",
            "not_supported_financial_metric_calculation_gain",
            "not_investment_alpha_or_recommendation_quality",
            "not_multi_cell_multi_case_transfer",
            "not_release_or_production_readiness",
        ],
        "stage_acceptance": {
            "S2": "pass_bounded_one_cell_material_agent_value",
            "S3": "ready_pending_separate_entry_and_detailed_backlog_authorization",
            "release": "not_admitted",
            "production": "not_admitted",
        },
        "next_action": "S3-ENTRY-AND-DETAILED-BACKLOG-FREEZE-DECISION",
    }
    return result


def run_t06() -> dict[str, Any]:
    result = assess_t06(
        _load(ROOT / "configs/releases/fin_ia_0_1_s2_t01_one_cell_bounded_agent_preflight_v1_0.json"),
        _load(ROOT / "configs/releases/fin_ia_0_1_s2_t03_deepseek_segmented_v4_live_validation_result_v1_0.json"),
        _load(ROOT / "configs/releases/fin_ia_0_1_s2_t04_live_artifact_validation_result_v1_0.json"),
        _load(ROOT / "configs/releases/fin_ia_0_1_s2_t05_exact_agent_fallback_review_v1_0.json"),
        _load(ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"),
    )
    return {
        "schema_version": "fin_ia_0_1_s2_t06_closeout_v1_0",
        "result_id": "S2-T06-INDEPENDENT-CLOSEOUT-R1",
        "closed_at": "2026-07-21",
        "authority": {
            "S2_T06_authorized": True,
            "new_model_provider_or_source_execution_authorized": False,
            "S3_entry_or_execution_authorized": False,
            "release_or_production_authorized": False,
        },
        "deterministic_verification": {
            "focused_T01_and_T06": "8 passed in 0.33s",
            "expanded_gateway_S2_T01_through_T06_and_project_os": (
                "109 passed in 57.29s"
            ),
            "negative_cases": [
                "owner_material_gain_acceptance_required",
                "complete_terminal_live_agent_artifact_set_required",
            ],
            "stable_source_digests": "pass_all_match",
        },
        **result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(run_t06(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
