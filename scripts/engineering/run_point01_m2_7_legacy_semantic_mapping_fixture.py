from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.legacy_objective_adapter import (  # noqa: E402
    LegacyObjectiveAdapterError,
    LegacySemanticMapping,
    LegacySemanticMappingPolicy,
    adapt_legacy_objective_semantically,
)
from sec_agent.canonical_runtime.planning_service import DecisionCellSeed, EvidenceSlotSeed  # noqa: E402


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_7_legacy_semantic_mapping_policy_v1_0.json"
PLAN_PATH = ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_7_legacy_semantic_mapping_fixture_result_v1_0.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy() -> LegacySemanticMappingPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return LegacySemanticMappingPolicy.model_validate({key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}})


def _target_cells() -> tuple[DecisionCellSeed, ...]:
    return tuple(
        DecisionCellSeed(
            cell_key=key,
            decision_question=f"{key} decision question",
            origin_type="pack_composition",
            owner_role="fundamental_analyst",
            materiality="high",
            stop_rule="accepted primary route or typed gap",
            evidence_slots=(
                EvidenceSlotSeed(
                    evidence_role="issuer_metric",
                    entity_scope=("AAA",),
                    period_scope="latest_fiscal_period",
                    source_policy_ref="issuer_first",
                    forbidden_substitutions=("relationship_graph_only",),
                    acceptance_role="primary",
                ),
            ),
        )
        for key in ("demand_signal", "margin_signal", "financial_quality")
    )


def _legacy_payload(case_name: str) -> dict[str, Any]:
    return {
        "query": f"{case_name} legacy objective",
        "required_items": [
            {"required_item_id": "legacy_unit_economics", "must_answer": "What is unit economics?"},
            {"required_item_id": "legacy_revenue", "must_answer": "What is revenue quality?"},
            {"required_item_id": "legacy_cashflow", "must_answer": "What is cash-flow quality?"},
            {"required_item_id": "legacy_fact_search", "must_answer": "Find legacy standalone facts"},
        ],
    }


def _mappings() -> tuple[LegacySemanticMapping, ...]:
    return (
        LegacySemanticMapping(
            legacy_required_item_id="legacy_unit_economics",
            action="split",
            target_cell_keys=("demand_signal", "margin_signal"),
            information_loss_tags=("legacy_question_split_into_mechanism_cells",),
        ),
        LegacySemanticMapping(
            legacy_required_item_id="legacy_revenue",
            action="merge",
            target_cell_keys=("financial_quality",),
            information_loss_tags=("legacy_metric_not_direct_cell_equivalence",),
        ),
        LegacySemanticMapping(
            legacy_required_item_id="legacy_cashflow",
            action="merge",
            target_cell_keys=("financial_quality",),
            information_loss_tags=("legacy_metric_merged_with_financial_quality",),
        ),
        LegacySemanticMapping(
            legacy_required_item_id="legacy_fact_search",
            action="downgrade",
            information_loss_tags=("legacy_fact_search_becomes_bounded_context",),
            downgrade_reason="legacy fact lookup is not an independent material DecisionCell",
        ),
    )


def _error_code(action) -> str:
    try:
        action()
    except LegacyObjectiveAdapterError as exc:
        return str(exc)
    return "not_rejected"


def build_result() -> dict[str, Any]:
    policy = _policy()
    target_cells = _target_cells()
    cases = {
        sector: adapt_legacy_objective_semantically(_legacy_payload(sector), target_cells=target_cells, mappings=_mappings(), policy=policy)
        for sector in ("ai_semis", "saas", "healthcare", "banks")
    }
    invalid_action = _error_code(
        lambda: adapt_legacy_objective_semantically(
            _legacy_payload("invalid"),
            target_cells=target_cells,
            mappings=(LegacySemanticMapping(legacy_required_item_id="legacy_unit_economics", action="direct_equivalence", target_cell_keys=("demand_signal",), information_loss_tags=("invalid",)),) + _mappings()[1:],
            policy=policy,
        )
    )
    missing_mapping = _error_code(
        lambda: adapt_legacy_objective_semantically(
            _legacy_payload("missing"), target_cells=target_cells, mappings=_mappings()[:-1], policy=policy
        )
    )
    checks = {
        "four_case_parity": len(cases) == 4 and all(set(plan.legacy_required_item_ids) == {"legacy_unit_economics", "legacy_revenue", "legacy_cashflow", "legacy_fact_search"} for plan in cases.values()),
        "merge_split_downgrade_present": all({mapping.action for mapping in plan.mappings} == {"merge", "split", "downgrade"} for plan in cases.values()),
        "information_loss_review_present": all(len(plan.information_loss_review) == 4 and plan.one_to_one_equivalence_count == 0 for plan in cases.values()),
        "invalid_action_rejected": invalid_action == "legacy_mapping_action_not_allowed",
        "missing_mapping_rejected": missing_mapping == "legacy_mapping_coverage_invalid",
        "model_free": all(plan.model_call_count == 0 and plan.external_call_count == 0 for plan in cases.values()),
    }
    return {
        "result_version": "finsight_point01_m2_7_legacy_semantic_mapping_fixture_result_v1_0",
        "scope": "Point01_M2_7_legacy_objective_semantic_migration",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "cases": {sector: plan.model_dump(mode="json") for sector, plan in cases.items()},
        "negative_errors": {"invalid_action": invalid_action, "missing_mapping": missing_mapping},
        "authority_boundary": {"legacy_task_run": "authoritative", "canonical_lane": "shadow_only", "model_call_count": 0, "external_call_count": 0},
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m2_7_legacy_semantic_mapping_policy_v1_0.json": _sha256(POLICY_PATH),
            "scripts/engineering/run_point01_m2_7_legacy_semantic_mapping_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/legacy_objective_adapter.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/legacy_objective_adapter.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(PLAN_PATH),
        },
        "boundary": "This fixture creates an auditable semantic mapping plan only. It does not mutate legacy state, treat legacy facts as DecisionCells, call a model or change authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M2.7 legacy semantic-mapping fixture.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "checks": result["checks"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
