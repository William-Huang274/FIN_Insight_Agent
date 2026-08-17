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
import scripts.research.run_s3_dynamic_five_cell_live as five_cell_runner  # noqa: E402
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    compile_finance_loop_messages,
)
from sec_agent.research.claim_surface_authority import (  # noqa: E402
    ClaimSurfaceAuthorityError,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
    validate_current_research_output,
)
from sec_agent.research.dynamic_research_runtime import (  # noqa: E402
    compile_dynamic_claim_surface_projection,
    compile_dynamic_research_input_projection,
)
from sec_agent.research.five_cell_runtime import (  # noqa: E402
    FiveCellResearchError,
    compile_five_cell_report,
    compile_five_cell_submission,
    compile_five_cell_submission_repair,
    validate_five_cell_synthesis,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest  # noqa: E402


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


@pytest.fixture(scope="module")
def r6_value_repair_replay() -> tuple[dict[str, object], dict[str, object]]:
    """Recompile the immutable R6 inputs under the v1.4 successor policy."""

    predecessor = _json(
        "data/workbench_private/s3_dynamic_five_cell/"
        "FIN013-S3-DELL-DYNAMIC-FIVE-CELL-R6/full_result.json"
    )
    evidence_service, _retrieval_service = _services()
    pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", READ)
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
        controlled_plan=predecessor["controlled_plan"],
        evidence_pack=pack,
    )["dynamic_research_input"]
    surface = compile_dynamic_claim_surface_projection(
        dynamic_research_input=base,
        claim_authority_template=_json(
            "configs/research/"
            "fin_ia_0_1_3_s3_dell_value_capture_dynamic_"
            "claim_authority_v1_1.json"
        ),
        claim_surface_template=_json(
            "configs/research/"
            "fin_ia_0_1_3_s3_dell_value_capture_dynamic_"
            "claim_surface_authority_v1_4.json"
        ),
    )["claim_surface_research_input"]
    assert base["research_input_digest"] == (
        "5c6b0bd2339bbcc84043f4b3dccacb9243f02916480164795f5be0e576aafcc1"
    )
    assert surface["research_input_digest"] == (
        "9a929d2e4a576dcea6ab94e186897138efc11f1a9a8468ef4fcd8887efce001d"
    )
    return predecessor, surface


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


def test_submission_repair_preserves_rejected_model_call_and_adds_typed_feedback(
    dynamic_surface_input: dict[str, object],
) -> None:
    rejected = deepcopy(_positive_payload(dynamic_surface_input)["cells"][0])
    rejected["thesis_atom"] = (
        "戴尔在 FY2026 Q1 与 FY2027 Q1 的公司层结果改善，"
        "但现有材料仍不能建立产品利润因果桥。"
    )
    selected_relation = next(
        row
        for row in dynamic_surface_input["numeric_relation_cards"]
        if row["numeric_relation_ref"]
        == rejected["numeric_relation_refs"][0]
    )
    omitted_endpoint = selected_relation["current_numeric_ref"]
    rejected["numeric_refs"].remove(omitted_endpoint)

    messages, tool, receipt = compile_five_cell_submission_repair(
        research_input=dynamic_surface_input,
        cell_id="CELL::value_capture",
        analysis_draft=(
            "公司层结果改善与产品组合变化同时出现，但现有证据只能支持"
            "有边界的公司观察，不能把利润改善主要归因于人工智能服务器。"
        ),
        rejected_arguments=rejected,
        terminal_failure_code="research_consumer_thesis_atom_invalid",
    )

    assert tool["function"]["name"] == "submit_research_judgment"
    assert messages[-3]["role"] == "assistant"
    preserved = json.loads(
        messages[-3]["tool_calls"][0]["function"]["arguments"]
    )
    assert preserved == rejected
    feedback = json.loads(messages[-2]["content"])
    assert feedback["failure_code"] == "research_consumer_thesis_atom_invalid"
    assert feedback["remaining_repair_turns"] == 1
    assert messages[-1]["role"] == "user"
    assert receipt["harness_generated_research_judgment"] is False
    assert receipt["rejected_submission_promoted"] is False

    corrected = deepcopy(rejected)
    corrected["thesis_atom"] = (
        "戴尔披露公司层结果改善与产品组合变化同时出现，但现有材料"
        "仍不能建立产品利润因果桥。"
    )
    validated = validate_current_research_output(
        {"cells": [corrected]},
        research_input=dynamic_surface_input,
        required_cell_ids=["CELL::value_capture"],
    )
    compiled = validated["cells"][0]
    assert omitted_endpoint in compiled["numeric_refs"]
    assert omitted_endpoint in compiled[
        "numeric_relation_endpoint_receipt"
    ]["deterministically_added_numeric_refs"]


def test_submission_repair_rejects_untyped_or_already_valid_predecessor(
    dynamic_surface_input: dict[str, object],
) -> None:
    valid = _positive_payload(dynamic_surface_input)["cells"][0]

    with pytest.raises(
        FiveCellResearchError,
        match="five_cell_submission_repair_failure_code_invalid",
    ):
        compile_five_cell_submission_repair(
            research_input=dynamic_surface_input,
            cell_id="CELL::value_capture",
            analysis_draft="有边界的公司层分析草案。",
            rejected_arguments=valid,
            terminal_failure_code="research_consumer_numeric_relation_boundary_invalid",
        )

    with pytest.raises(
        FiveCellResearchError,
        match="five_cell_submission_repair_predecessor_not_rejected",
    ):
        compile_five_cell_submission_repair(
            research_input=dynamic_surface_input,
            cell_id="CELL::value_capture",
            analysis_draft="有边界的公司层分析草案。",
            rejected_arguments=valid,
            terminal_failure_code="research_consumer_thesis_atom_invalid",
        )


def test_R6_value_capture_replays_to_one_typed_repair_and_full_fake_report(
    r6_value_repair_replay: tuple[dict[str, object], dict[str, object]],
) -> None:
    predecessor, research_input = r6_value_repair_replay
    rows = {
        row["cell_id"]: row for row in predecessor["cell_steps"]
    }
    value_row = rows["CELL::value_capture"]
    rejected = deepcopy(value_row["raw_model_arguments"])

    with pytest.raises(CurrentResearchConsumerError) as rejected_error:
        validate_current_research_output(
            {"cells": [rejected]},
            research_input=research_input,
            required_cell_ids=["CELL::value_capture"],
        )
    assert rejected_error.value.code == "research_consumer_thesis_atom_invalid"
    assert canonical_digest(rejected) == (
        "028f0f49724aef1e37dd227feee0f1f78b1bfd1814b89fc9f14a99fac586388e"
    )

    capture_receipt = five_cell_runner._validate_reused_analysis_capture(
        value_row
    )
    assert capture_receipt["analysis_reuse_digest"] == (
        "076efa18e68cc533063e7ebced693c76cc2c615086b70d259ccca3bbfa04fa18"
    )
    assert capture_receipt["content_digest"] == (
        "a19a48c196944039b21893ae24958ad4a25425c4281b754459c96562a3d6bd28"
    )

    messages, tool, repair_receipt = compile_five_cell_submission_repair(
        research_input=research_input,
        cell_id="CELL::value_capture",
        analysis_draft=value_row["analysis_step"]["content"],
        rejected_arguments=rejected,
        terminal_failure_code="research_consumer_thesis_atom_invalid",
    )
    assert tool["function"]["name"] == "submit_research_judgment"
    assert repair_receipt["rejected_submission_promoted"] is False
    assert json.loads(
        messages[-3]["tool_calls"][0]["function"]["arguments"]
    ) == rejected

    corrected = deepcopy(rejected)
    corrected["thesis_atom"] = (
        "戴尔披露的公司层收入与毛利表现共同改善，但现有资料仍不足以"
        "把该改善主要归因于人工智能服务器，也没有建立产品利润桥。"
    )
    compiled_value = validate_current_research_output(
        {"cells": [corrected]},
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
    )["cells"][0]
    endpoint_receipt = compiled_value["numeric_relation_endpoint_receipt"]
    assert endpoint_receipt["deterministically_added_numeric_refs"] == [
        "NUM::ADC81E7A547FAB94",
        "NUM::F8C8EB238E997BA2",
    ]
    surface_receipt = compiled_value["claim_surface_authority_receipt"]
    assert surface_receipt["qualitative_fact_binding_receipt"][
        "deterministically_added_qualitative_fact_refs"
    ] == [MARGIN_QF]

    raw_cells = []
    historical_digests = {
        "CELL::demand_quality": (
            "cf298e12c5a8318199bbc38101dc11769090b86f2419d2626221827ed2355c22"
        ),
        "CELL::operating_performance": (
            "45243e0c490fe302e413004bf2e46062fde43212fc2568857dd8ddd485e02b12"
        ),
        "CELL::cash_conversion": (
            "68fb76dee98cbdee6ac32f2edc062cc0775c5f00572b8ae286579005668e3e19"
        ),
        "CELL::counterevidence": (
            "786d4b61cad6dda699c9f1f8d7919bfc1d035fa7829475685be27dcb1baec4c2"
        ),
    }
    for cell_id in five_cell_runner.REQUIRED_CELL_IDS:
        raw = corrected if cell_id == "CELL::value_capture" else deepcopy(
            rows[cell_id]["raw_model_arguments"]
        )
        raw_cells.append(raw)
        if cell_id in historical_digests:
            validated = validate_current_research_output(
                {"cells": [raw]},
                research_input=research_input,
                required_cell_ids=[cell_id],
            )["cells"][0]
            assert canonical_digest(validated) == historical_digests[cell_id]

    judgment = validate_current_research_output(
        {"cells": raw_cells},
        research_input=research_input,
        required_cell_ids=five_cell_runner.REQUIRED_CELL_IDS,
    )
    deliverable = compile_current_research_deliverable(
        research_input=research_input,
        judgment_output={"cells": raw_cells},
        required_cell_ids=five_cell_runner.REQUIRED_CELL_IDS,
    )
    assert len(deliverable["deliverable_digest"]) == 64

    synthesis_payload = {
        "overall_judgment": "mixed",
        "confidence_basis": "mixed_source_strength",
        "inference_authority": "bounded_inference",
        "executive_thesis": (
            "需求、经营结果和现金表现方向一致，但产品利润归因仍受"
            "公司范围与证据缺口限制。"
        ),
        "cross_cell_mechanism": (
            "需求兑现影响收入和现金形成，产品组合与成本结构共同限制"
            "价值获取，反方证据保留替代解释。"
        ),
        "strongest_counterargument": (
            "公司层改善可能同时来自多项业务和成本因素，现有材料不能"
            "把整体改善单独归于一个产品类别。"
        ),
        "key_cell_ids": list(five_cell_runner.REQUIRED_CELL_IDS),
        "cell_links": [
            {
                "from_cell_id": "CELL::demand_quality",
                "to_cell_id": "CELL::operating_performance",
                "relation": "supports",
                "explanation": "需求兑现能够支持经营表现，但并不单独关闭利润归因。",
            },
            {
                "from_cell_id": "CELL::counterevidence",
                "to_cell_id": "CELL::value_capture",
                "relation": "limits",
                "explanation": "反方证据限制产品组合到公司利润的因果外推。",
            },
        ],
        "evidence_refs": [],
        "numeric_refs": [],
        "numeric_relation_refs": [],
        "remaining_gap_refs": [],
        "what_would_change": {
            "observable": "产品价格数量成本与公司利润形成连续可复算桥",
            "direction": "resolve_gap",
            "time_horizon": "后续连续披露期",
            "evidence_route": "发行人定期申报与官方经营说明",
            "threshold_numeric_ref": "",
        },
    }
    synthesis = validate_five_cell_synthesis(
        synthesis_payload,
        research_input=research_input,
        judgment_output=judgment,
    )
    report = compile_five_cell_report(
        research_input=research_input,
        structured_deliverable=deliverable,
        synthesis=synthesis,
    )
    assert report["status"] == "five_cell_internal_research_report_compiled"
    assert report["rendering_authority"][
        "harness_generated_research_conclusion"
    ] is False


def test_R6_value_repair_capture_and_claim_mutations_fail_closed(
    r6_value_repair_replay: tuple[dict[str, object], dict[str, object]],
) -> None:
    predecessor, research_input = r6_value_repair_replay
    value_row = next(
        row
        for row in predecessor["cell_steps"]
        if row["cell_id"] == "CELL::value_capture"
    )
    capture_drift = deepcopy(value_row)
    capture_drift["analysis_step"]["request_digest"] = "0" * 64
    with pytest.raises(
        five_cell_runner.DynamicFiveCellLiveError,
        match="five_cell_node_successor_capture_integrity_invalid",
    ):
        five_cell_runner._validate_reused_analysis_capture(capture_drift)

    rejected = deepcopy(value_row["raw_model_arguments"])
    rejected["thesis_atom"] = (
        "戴尔披露的公司层表现有所改善，但仍不能据此建立产品利润桥。"
    )
    rejected["claim_relations"][0]["claim_relation_ref"] = (
        "CR::MU::CROSS_CASE"
    )
    with pytest.raises(
        CurrentResearchConsumerError,
        match="claim_surface_relation_alias_invalid",
    ):
        validate_current_research_output(
            {"cells": [rejected]},
            research_input=research_input,
            required_cell_ids=["CELL::value_capture"],
        )
