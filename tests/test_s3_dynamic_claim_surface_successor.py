from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (  # noqa: E402
    ResearchEvidencePackPrincipal,
)
from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
)
from scripts.research.run_s3_current_research_consumer_zero_call import (  # noqa: E402
    _services,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    compile_finance_loop_messages,
)
from sec_agent.research.claim_surface_authority import (  # noqa: E402
    ClaimSurfaceAuthorityError,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    CurrentResearchConsumerError,
    validate_current_research_output,
)
from sec_agent.research.dynamic_research_runtime import (  # noqa: E402
    compile_dynamic_claim_surface_projection,
    compile_dynamic_research_input_projection,
)
from sec_agent.research.five_cell_runtime import (  # noqa: E402
    compile_five_cell_submission,
)


READ = frozenset({"current_product:read"})
MARGIN_EV = "EV::5388E016C17032C1"
MARGIN_QF = (
    "QF::DELL::AI_SERVER_MIX_PRESSURE_ON_COMPANY_GROSS_MARGIN::FY2026Q3"
)
MARGIN_ANCHOR = (
    "The decreases in gross margin percentage and non-GAAP gross margin "
    "percentage were primarily driven by a shift in mix towards our "
    "AI-optimized server offerings."
)


def _json(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dynamic_surface_input() -> dict[str, object]:
    evidence_service, retrieval_service = _services()
    pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", READ)
    )
    controlled = retrieval_service.execute_controlled_plan(
        "DELL",
        _json(
            "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
        ),
        _json(
            "tests/fixtures/research/"
            "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
        ),
        ResearchRetrievalPrincipal("current", READ),
    )
    base = compile_dynamic_research_input_projection(
        truth_spine_policy=_json(
            "configs/research/"
            "fin_ia_0_1_3_s3_dynamic_truth_spine_policy_v1_0.json"
        ),
        consumer_policy=_json(
            "configs/research/"
            "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_4.json"
        ),
        controlled_plan=controlled,
        evidence_pack=pack,
    )["dynamic_research_input"]
    return compile_dynamic_claim_surface_projection(
        dynamic_research_input=base,
        claim_authority_template=_json(
            "configs/research/"
            "fin_ia_0_1_3_s3_dell_value_capture_dynamic_"
            "claim_authority_v1_1.json"
        ),
        claim_surface_template=_json(
            "configs/research/"
            "fin_ia_0_1_3_s3_dell_value_capture_dynamic_"
            "claim_surface_authority_v1_3.json"
        ),
    )["claim_surface_research_input"]


def _positive_payload(research_input: dict[str, object]) -> dict[str, object]:
    cell = next(
        row
        for row in research_input["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )
    return {
        "cells": [
            {
                "cell_id": "CELL::value_capture",
                "judgment_status": "mixed",
                "confidence_basis": "mixed_source_strength",
                "inference_authority": "bounded_inference",
                "claim_scope": "multi_scope",
                "financial_scope": "multi_scope_financial",
                "causal_bridge_authority": "management_assertion_only",
                "claim_relations": [
                    {
                        "atom_field": "thesis_atom",
                        "claim_relation_ref": (
                            "CR::DELL::HISTORICAL_MIX_PRESSURE"
                        ),
                    },
                    {
                        "atom_field": "mechanism_atom",
                        "claim_relation_ref": (
                            "CR::DELL::COMPANY_MARGIN_OBSERVATION"
                        ),
                    },
                    {
                        "atom_field": "counterargument_atom",
                        "claim_relation_ref": "CR::DELL::PROFIT_BRIDGE_GAP",
                    },
                ],
                "qualitative_fact_refs": [MARGIN_QF],
                "evidence_uses": [
                    {"evidence_ref": MARGIN_EV, "use_role": "support"}
                ],
                "numeric_refs": list(cell["allowed_numeric_refs"]),
                "numeric_relation_refs": ["REL::B60164179DFFDF5A"],
                "method_step_refs": [
                    row["method_step_ref"]
                    for row in cell["role_method_pack"]["method_steps"]
                ],
                "graph_edge_refs": [
                    row["graph_edge_ref"]
                    for row in cell["graph_context_pack"]["edges"]
                ],
                "thesis_atom": (
                    "戴尔披露，历史申报期内产品组合向人工智能优化服务器"
                    "倾斜主要驱动公司毛利率下降；该发行人归因只适用于"
                    "该历史期间。"
                ),
                "mechanism_atom": (
                    "同口径公司毛利率关系显示历史变化，但这项公司观察"
                    "不建立产品利润率、售价、销量或利润分配桥。"
                ),
                "counterargument_atom": (
                    "该历史归因不能外推到当前申报期，也不能证明产品独立"
                    "因果；现有缺口仍要求产品价格、数量与成本桥。"
                ),
                "what_would_change": {
                    "observable": "产品价格、数量、成本与利润形成连续可复算桥",
                    "direction": "resolve_gap",
                    "time_horizon": "后续连续披露期",
                    "evidence_route": "发行人定期申报和官方业绩说明",
                    "threshold_numeric_ref": None,
                },
            }
        ]
    }


def _demand_payload(research_input: dict[str, object]) -> dict[str, object]:
    cell = next(
        row
        for row in research_input["cells"]
        if row["cell_id"] == "CELL::demand_quality"
    )
    return {
        "cell_id": "CELL::demand_quality",
        "judgment_status": "mixed",
        "confidence_basis": "direct_source_only",
        "inference_authority": "bounded_inference",
        "evidence_uses": [
            {
                "evidence_ref": cell["allowed_evidence_refs"][0],
                "use_role": "support",
            }
        ],
        "numeric_refs": [],
        "numeric_relation_refs": [],
        "method_step_refs": [
            row["method_step_ref"]
            for row in cell["role_method_pack"]["method_steps"]
        ],
        "graph_edge_refs": [
            row["graph_edge_ref"]
            for row in cell["graph_context_pack"]["edges"]
        ],
        "thesis_atom": (
            "戴尔披露的需求信号支持当前方向，但现有材料仍不能单独"
            "证明订单会持续转化。"
        ),
        "mechanism_atom": (
            "客户采购、积压兑现和部署进度共同决定需求能否形成"
            "持续收入。"
        ),
        "counterargument_atom": (
            "提前采购和后续消化可能改变表面需求强度，现有资料"
            "不能关闭这一反向解释。"
        ),
        "what_would_change": {
            "observable": "订单兑现与客户复购保持一致方向",
            "direction": "persist",
            "time_horizon": "后续连续披露期",
            "evidence_route": "公司业绩材料与客户采购披露",
            "threshold_numeric_ref": None,
        },
    }


def test_dynamic_surface_exposes_exact_reviewed_anchor_and_historical_relation(
    dynamic_surface_input: dict[str, object],
) -> None:
    evidence = next(
        row
        for row in dynamic_surface_input["evidence_cards"]
        if row["evidence_ref"] == MARGIN_EV
    )
    value = next(
        row
        for row in dynamic_surface_input["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )

    assert evidence["source_visible_fact_excerpt"] == MARGIN_ANCHOR
    assert evidence["reviewed_anchor_receipt"]["anchor_start"] > 1200
    assert MARGIN_QF in value["allowed_qualitative_fact_refs"]
    assert "CR::DELL::HISTORICAL_MIX_PRESSURE" in dynamic_surface_input[
        "model_output_contract"
    ]["allowed_claim_relation_refs"]


def test_dynamic_historical_relation_validates_without_cross_period_expansion(
    dynamic_surface_input: dict[str, object],
) -> None:
    validated = validate_current_research_output(
        _positive_payload(dynamic_surface_input),
        research_input=dynamic_surface_input,
        required_cell_ids=["CELL::value_capture"],
    )

    thesis = validated["cells"][0]["claim_relations"][0]
    assert thesis["claim_relation"] == (
        "issuer_attributed_historical_mix_pressure"
    )
    assert thesis["causal_bridge_authority"] == "management_assertion_only"
    assert validated["cells"][0]["qualitative_fact_refs"] == [MARGIN_QF]


def test_claim_surface_contract_is_compiled_only_for_qualified_value_cell(
    dynamic_surface_input: dict[str, object],
) -> None:
    demand_cell = _demand_payload(dynamic_surface_input)
    validated = validate_current_research_output(
        {"cells": [demand_cell]},
        research_input=dynamic_surface_input,
        required_cell_ids=["CELL::demand_quality"],
    )
    assert validated["cells"][0]["cell_id"] == "CELL::demand_quality"

    demand_messages, demand_tool = compile_five_cell_submission(
        research_input=dynamic_surface_input,
        cell_id="CELL::demand_quality",
        analysis_draft=(
            "需求披露能够支持当前判断，但持续性仍取决于订单兑现、"
            "客户复购和供给缓解后的真实消化。"
        ),
    )
    demand_properties = demand_tool["function"]["parameters"]["properties"]
    claim_fields = {
        "claim_scope",
        "financial_scope",
        "causal_bridge_authority",
        "claim_relations",
        "qualitative_fact_refs",
    }
    assert claim_fields.isdisjoint(demand_properties)
    serialized_demand = json.dumps(
        demand_messages, ensure_ascii=False, sort_keys=True
    )
    assert "CR::DELL::COMPANY_MARGIN_OBSERVATION" not in serialized_demand
    assert "ClaimRelationCard" not in serialized_demand
    loop_messages = compile_finance_loop_messages(
        research_input=dynamic_surface_input,
        required_cell_ids=["CELL::demand_quality"],
    )
    serialized_loop = json.dumps(
        loop_messages, ensure_ascii=False, sort_keys=True
    )
    assert "CR::DELL::COMPANY_MARGIN_OBSERVATION" not in serialized_loop
    assert "claim_surface_authority_contract" not in serialized_loop

    _value_messages, value_tool = compile_five_cell_submission(
        research_input=dynamic_surface_input,
        cell_id="CELL::value_capture",
        analysis_draft=(
            "利润获取同时受到产品组合、成本与其他业务影响，现有资料"
            "只能支持有边界的公司层判断。"
        ),
    )
    value_properties = value_tool["function"]["parameters"]["properties"]
    assert claim_fields.issubset(value_properties)
    relation_enum = value_properties["claim_relations"]["items"][
        "properties"
    ]["claim_relation_ref"]["enum"]
    assert "CR::DELL::COMPANY_MARGIN_OBSERVATION" in relation_enum


def test_nonqualified_cell_rejects_value_only_claim_authority_fields(
    dynamic_surface_input: dict[str, object],
) -> None:
    demand_cell = _demand_payload(dynamic_surface_input)
    demand_cell.update(
        {
            "claim_scope": "company",
            "financial_scope": "non_financial",
            "causal_bridge_authority": "bridge_unavailable",
            "claim_relations": [
                {
                    "atom_field": "thesis_atom",
                    "claim_relation_ref": (
                        "CR::DELL::COMPANY_MARGIN_OBSERVATION"
                    ),
                },
                {
                    "atom_field": "mechanism_atom",
                    "claim_relation_ref": "CR::DELL::PROFIT_BRIDGE_GAP",
                },
                {
                    "atom_field": "counterargument_atom",
                    "claim_relation_ref": (
                        "CR::DELL::HISTORICAL_MIX_PRESSURE"
                    ),
                },
            ],
            "qualitative_fact_refs": [],
        }
    )
    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_output_cell_fields_invalid",
    ):
        validate_current_research_output(
            {"cells": [demand_cell]},
            research_input=dynamic_surface_input,
            required_cell_ids=["CELL::demand_quality"],
        )


def test_unattributed_direct_surface_and_cross_case_ref_fail_closed(
    dynamic_surface_input: dict[str, object],
) -> None:
    unattributed = _positive_payload(dynamic_surface_input)
    unattributed["cells"][0]["thesis_atom"] = (
        "人工智能服务器组合迁移主要驱动公司毛利率下降，并形成产品到"
        "公司利润的确定因果链。"
    )
    with pytest.raises(
        CurrentResearchConsumerError,
        match="claim_surface_narrative_relation_conflict",
    ):
        validate_current_research_output(
            unattributed,
            research_input=dynamic_surface_input,
            required_cell_ids=["CELL::value_capture"],
        )

    contaminated = _positive_payload(dynamic_surface_input)
    contaminated["cells"][0]["evidence_uses"][0]["evidence_ref"] = (
        "EV::MU::CROSS_CASE"
    )
    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_evidence_use_invalid",
    ):
        validate_current_research_output(
            contaminated,
            research_input=dynamic_surface_input,
            required_cell_ids=["CELL::value_capture"],
        )


def test_historical_fact_period_and_source_surface_mutations_fail_closed(
    dynamic_surface_input: dict[str, object],
) -> None:
    del dynamic_surface_input
    evidence_service, retrieval_service = _services()
    pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", READ)
    )
    controlled = retrieval_service.execute_controlled_plan(
        "DELL",
        _json(
            "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
        ),
        _json(
            "tests/fixtures/research/"
            "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
        ),
        ResearchRetrievalPrincipal("current", READ),
    )
    base = compile_dynamic_research_input_projection(
        truth_spine_policy=_json(
            "configs/research/"
            "fin_ia_0_1_3_s3_dynamic_truth_spine_policy_v1_0.json"
        ),
        consumer_policy=_json(
            "configs/research/"
            "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_4.json"
        ),
        controlled_plan=controlled,
        evidence_pack=pack,
    )["dynamic_research_input"]
    claim_template = _json(
        "configs/research/"
        "fin_ia_0_1_3_s3_dell_value_capture_dynamic_claim_authority_v1_1.json"
    )
    surface_template = _json(
        "configs/research/"
        "fin_ia_0_1_3_s3_dell_value_capture_dynamic_"
        "claim_surface_authority_v1_3.json"
    )

    for field, mutation in (
        ("period_end", "2025-11-01"),
        ("source_surface", "Dell reported an invented margin bridge."),
    ):
        drift = deepcopy(surface_template)
        drift["source_bound_qualitative_facts"][1][field] = mutation
        with pytest.raises(ClaimSurfaceAuthorityError):
            compile_dynamic_claim_surface_projection(
                dynamic_research_input=base,
                claim_authority_template=claim_template,
                claim_surface_template=drift,
            )
