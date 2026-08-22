from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.research.task_quantitative_program import (
    TaskQuantitativeProgramError,
    compile_task_quantitative_program,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "configs"
    / "financial_facts"
    / "fin_ia_0_1_3_s2_dell_task_quantitative_program_v1_0.json"
)
PACK = (
    ROOT
    / "data"
    / "workbench_private"
    / "fin_0_1_3_s1_dell_external_source_evidence"
    / "dell-r3-capture-replay"
    / "successor"
    / "pack.json"
)
REPLAY = (
    ROOT
    / "data"
    / "workbench_private"
    / "fin_0_1_3_s1_source_route_truth_replay"
    / "dell-r1"
    / "full_result.json"
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _compile(program: dict | None = None, pack: dict | None = None) -> dict:
    replay = _json(REPLAY)
    return compile_task_quantitative_program(
        program=program or _json(PROGRAM),
        evidence_pack=pack or _json(PACK),
        request_results=replay["product_projection"]["request_results"],
        recorded_at="2026-08-23",
    )


def test_dell_task_quantitative_program_preserves_authority_boundaries() -> None:
    result = _compile()

    assert result["status"] == "ready_for_bounded_dynamic_single_unit_with_typed_gaps"
    assert result["quantitative_authority"]["summary"] == {
        "reported_fact_count": 38,
        "deterministic_derived_metric_count": 27,
        "research_estimate_count": 2,
        "scenario_count": 2,
        "typed_gap_count": 9,
        "typed_conflict_count": 0,
    }
    assert result["task_readiness"]["ready"] is True
    assert len(result["typed_gap_dispositions"]) == 14
    assert all(row["closed"] is False for row in result["typed_gap_dispositions"])
    assert all(
        row["numeric_fact_authority"] is False
        for row in result["quantitative_authority"]["research_estimates"]
    )
    assert result["authority"]["target_company_ASP_units_PVM_or_allocation_inferred"] is False


def test_unbound_or_mutated_industry_source_fails_closed() -> None:
    pack = _json(PACK)
    material = next(
        row
        for row in pack["source_materials"]
        if row["material_ref"] == "source_material_external_1ccdcc84c6c40b6bbcd755cc"
    )
    material["source_text"] = material["source_text"].replace("20-25%", "30-35%")

    with pytest.raises(
        TaskQuantitativeProgramError,
        match="task_quantitative_evidence_support_source_invalid",
    ):
        _compile(pack=pack)


def test_industry_scenario_cannot_close_dell_asp_or_pvm_gap() -> None:
    program = _json(PROGRAM)
    target = next(
        row
        for row in program["typed_gap_dispositions"]
        if row["gap_id"] == "dell-gap-pricing-asp"
    )
    target["closed"] = True

    with pytest.raises(
        TaskQuantitativeProgramError,
        match="task_quantitative_gap_disposition_invalid",
    ):
        _compile(program=program)


def test_every_current_pack_gap_requires_explicit_owner() -> None:
    program = _json(PROGRAM)
    program["typed_gap_dispositions"] = program["typed_gap_dispositions"][:-1]

    with pytest.raises(
        TaskQuantitativeProgramError,
        match="task_quantitative_gap_coverage_invalid",
    ):
        _compile(program=program)
