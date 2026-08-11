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

from sec_agent.canonical_runtime.cell_composition import (  # noqa: E402
    CellArchetype,
    CellCompositionEngine,
    CellCompositionError,
    CellCompositionPolicy,
    CellSlotTemplate,
)


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_5_cell_composition_policy_v1_0.json"
PLAN_PATH = ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_5_cell_composition_fixture_result_v1_0.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy() -> CellCompositionPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return CellCompositionPolicy.model_validate({key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}})


def _slot(slot_key: str, fact_key: str, *, source_policy_ref: str = "issuer_first") -> CellSlotTemplate:
    return CellSlotTemplate(
        slot_key=slot_key,
        evidence_role="issuer_metric",
        entity_scope=("AAA",),
        period_scope="latest_fiscal_period",
        metric_scope=(fact_key,),
        source_policy_ref=source_policy_ref,
        forbidden_substitutions=("unbounded_proxy", "relationship_graph_only"),
        acceptance_role="primary",
        fact_keys=(fact_key,),
    )


def build_archetypes(sector: str) -> tuple[CellArchetype, ...]:
    policy = _policy()
    roles = policy.allowed_owner_roles
    archetypes: list[CellArchetype] = []
    for index in range(5):
        archetypes.append(
            CellArchetype(
                archetype_id=f"universal-{sector}-{index}",
                source_pack_ref="universal-core:v1",
                merge_key=f"core_{index}",
                decision_question=f"Universal material question {index}",
                owner_role=roles[index % len(roles)],
                materiality="high",
                stop_rule="accepted primary route or typed gap",
                slots=(_slot(f"universal_slot_{index}", f"universal_fact_{index}"),),
                what_would_change=(f"universal_driver_{index}",),
                counterevidence_owner_role="risk_counterevidence_analyst",
                dependency_merge_keys=(f"core_{index - 1}",) if index else (),
            )
        )
    archetypes.append(
        CellArchetype(
            archetype_id=f"sector-{sector}-merge-core-0",
            source_pack_ref=f"sector-{sector}:v1",
            merge_key="core_0",
            decision_question="Universal material question 0",
            owner_role=roles[0],
            materiality="high",
            stop_rule="accepted primary route or typed gap",
            slots=(_slot("sector_extension_slot", f"{sector}_extension_fact", source_policy_ref="official_first"),),
            what_would_change=("universal_driver_0",),
            counterevidence_owner_role="risk_counterevidence_analyst",
        )
    )
    for index in range(1, 5):
        archetypes.append(
            CellArchetype(
                archetype_id=f"sector-{sector}-{index}",
                source_pack_ref=f"sector-{sector}:v1",
                merge_key=f"{sector}_{index}",
                decision_question=f"{sector} material question {index}",
                owner_role=roles[index % len(roles)],
                materiality="high",
                stop_rule="accepted primary route or typed gap",
                slots=(_slot(f"sector_slot_{index}", f"{sector}_fact_{index}"),),
                what_would_change=(f"{sector}_driver_{index}",),
                counterevidence_owner_role="risk_counterevidence_analyst",
                dependency_merge_keys=(f"{sector}_{index - 1}",) if index > 1 else ("core_4",),
                split_labels=("demand", "monetization") if index == 4 else (),
            )
        )
    return tuple(archetypes)


def _error_code(action) -> str:
    try:
        action()
    except CellCompositionError as exc:
        return str(exc)
    return "not_rejected"


def build_result() -> dict[str, Any]:
    engine = CellCompositionEngine(_policy())
    sectors = ("ai_semis", "saas", "healthcare", "banks")
    positives = {
        sector: engine.compose(
            case_id=f"case-{sector}",
            selected_pack_refs=("universal-core:v1", f"sector-{sector}:v1"),
            archetypes=build_archetypes(sector),
        )
        for sector in sectors
    }
    adversarial_templates = list(build_archetypes("ai_semis"))
    adversarial_templates[5] = adversarial_templates[5].model_copy(update={"decision_question": "conflicting merge question"})
    merge_conflict = _error_code(
        lambda: engine.compose(case_id="case-adversarial", selected_pack_refs=("universal-core:v1", "sector-ai_semis:v1"), archetypes=tuple(adversarial_templates))
    )
    dependency_templates = list(build_archetypes("saas"))
    dependency_templates[1] = dependency_templates[1].model_copy(update={"dependency_merge_keys": ("missing_merge_key",)})
    dependency_missing = _error_code(
        lambda: engine.compose(case_id="case-adversarial", selected_pack_refs=("universal-core:v1", "sector-saas:v1"), archetypes=tuple(dependency_templates))
    )
    pack_missing = _error_code(
        lambda: engine.compose(case_id="case-adversarial", selected_pack_refs=("universal-core:v1",), archetypes=build_archetypes("banks"))
    )
    checks = {
        "four_positive_cases": set(positives) == set(sectors),
        "all_positive_cases_have_ten_material_cells": all(len(result.cells) == 10 for result in positives.values()),
        "merge_split_dedupe_trace": all(result.merged_archetype_ids and result.split_cell_keys for result in positives.values()),
        "fact_to_slot_mapping_present": all(all(cell.fact_to_slot_keys for cell in result.cells) for result in positives.values()),
        "adversarial_merge_conflict": merge_conflict == "merge_contract_conflict:core_0",
        "adversarial_dependency_missing": dependency_missing == "dependency_merge_key_missing:core_1:missing_merge_key",
        "adversarial_pack_missing": pack_missing.startswith("archetype_pack_not_selected:"),
        "model_free": all(result.model_call_count == 0 and result.external_call_count == 0 for result in positives.values()),
    }
    return {
        "result_version": "finsight_point01_m2_5_cell_composition_fixture_result_v1_0",
        "scope": "Point01_M2_5_cell_composition",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "positive_cases": {sector: result.model_dump(mode="json") for sector, result in positives.items()},
        "adversarial_errors": {"merge_conflict": merge_conflict, "dependency_missing": dependency_missing, "pack_missing": pack_missing},
        "authority_boundary": {"legacy_task_run": "authoritative", "canonical_lane": "shadow_only", "model_call_count": 0, "external_call_count": 0},
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m2_5_cell_composition_policy_v1_0.json": _sha256(POLICY_PATH),
            "scripts/engineering/run_point01_m2_5_cell_composition_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/cell_composition.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/cell_composition.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(PLAN_PATH),
        },
        "boundary": "Composition transforms selected shadow pack templates into deterministic candidate cells only. It does not resolve live evidence, call a model, write legacy state or change authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M2.5 cell-composition fixture.")
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
