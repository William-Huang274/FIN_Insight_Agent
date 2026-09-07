from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import (  # noqa: E402
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.evidence_set_coverage import compile_requirement_plan  # noqa: E402
from sec_agent.research.material_scope import (  # noqa: E402
    ResearchMaterialScopeError,
    compile_research_material_scope,
    compile_research_material_scope_messages,
    parse_research_material_scope_output,
)


KERNEL = load_financial_research_kernel(
    json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_2.json"
        ).read_text(encoding="utf-8")
    )
)
SCOPE_POLICY = json.loads(
    (
        ROOT
        / "configs/research/fin_ia_0_1_3_s3_material_scope_policy_v1_0.json"
    ).read_text(encoding="utf-8")
)
MATERIAL_POLICY = json.loads(
    (
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_material_evidence_runtime_policy_v1_0.json"
    ).read_text(encoding="utf-8")
)
ONTOLOGY = json.loads(
    (
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_2.json"
    ).read_text(encoding="utf-8")
)


def _request(
    *,
    request_id: str = "REQ::DELL-WORKING-CAPITAL-SCOPE",
    facet_id: str = "working_capital_risk",
    metric_intents: list[str] | None = None,
    product_intents: list[str] | None = None,
    fiscal_years: list[int] | None = None,
    case_key: str = "DELL",
    subject_ticker: str = "DELL",
):
    return load_evidence_request(
        {
            "schema_version": "fin_ia_evidence_request_v1_0",
            "request_id": request_id,
            "cell_id": f"CELL::{case_key}-MATERIAL-SCOPE",
            "requester_role": "cash_conversion_specialist",
            "evidence_domain": "operating_performance",
            "case_key": case_key,
            "subject_ticker": subject_ticker,
            "research_as_of": "2026-08-06",
            "target_entities": [subject_ticker],
            "requested_facet_ids": [facet_id],
            "metric_intents": metric_intents
            if metric_intents is not None
            else ["inventory", "accounts_receivable"],
            "product_intents": product_intents
            if product_intents is not None
            else ["AI infrastructure working-capital dynamics"],
            "period": {
                "start_date": "2025-02-01",
                "end_date": "2026-08-06",
                "fiscal_years": fiscal_years or [2026, 2027],
            },
            "granularity": "quarter_and_fiscal_year",
            "unit": "reported_source_unit",
            "acceptable_sources": ["10-K", "10-Q", "8-K"],
            "acceptable_proxy": False,
            "forbidden_proxy": ["unbound industry demand"],
            "stop_condition": "return candidates, typed facts, or typed gaps",
            "clarification_policy": "return_typed_gap",
        },
        KERNEL,
    )


def _working_capital_payload(request_id: str) -> dict[str, object]:
    return {
        "schema_version": "fin_ia_research_material_scope_atoms_v1_0",
        "research_plan_digest": "PLAN::DEVELOPMENT",
        "request_scopes": [
            {
                "request_id": request_id,
                "product_intent_dispositions": [
                    {
                        "product_intent_index": 0,
                        "disposition": "contextual_retrieval_only",
                    }
                ],
                "requirement_atoms": [
                    {
                        "facet_id": "working_capital_risk",
                        "role": "bridge",
                        "metric_intent_indices": [0, 1],
                        "product_intent_indices": [],
                        "period_mode": "any",
                        "coverage_mode": "collective_axes",
                    },
                    {
                        "facet_id": "working_capital_risk",
                        "role": "counter",
                        "metric_intent_indices": [],
                        "product_intent_indices": [],
                        "period_mode": "any",
                        "coverage_mode": "collective_axes",
                    },
                ],
            }
        ],
    }


def test_material_scope_compiles_composite_topic_without_literal_product_gate() -> None:
    request = _request()
    result = compile_research_material_scope(
        _working_capital_payload(request.request_id),
        research_plan_digest="PLAN::DEVELOPMENT",
        requests=[request],
        required_request_ids=[request.request_id],
        policy=SCOPE_POLICY,
        material_runtime_policy=MATERIAL_POLICY,
        intent_ontology=ONTOLOGY,
    )

    scope = result["request_scopes"][0]
    assert scope["explicit_scope_ready"] is True
    assert scope["product_intent_dispositions"] == [
        {
            "product_intent_index": 0,
            "product_intent": "AI infrastructure working-capital dynamics",
            "disposition": "contextual_retrieval_only",
        }
    ]
    requirements = scope["research_blueprint"]["material_requirements"]
    assert len(requirements) == 2
    assert {
        (row["role"], tuple(row["metric_ids"]), tuple(row["product_ids"]))
        for row in requirements
    } == {
        ("bridge", ("inventory", "accounts_receivable"), ()),
        ("counter", (), ()),
    }
    assert result["summary"]["candidate_or_reference_inputs_read"] is False
    assert result["authority"]["numeric_authority"] is False


@pytest.mark.parametrize(
    ("case_key", "product_intents"),
    [
        (
            "DELL",
            [
                "AI server revenue contribution",
                "segment profitability",
                "EPS impact",
            ],
        ),
        (
            "MU",
            ["HBM revenue contribution", "memory profitability", "EPS impact"],
        ),
        (
            "NVDA",
            [
                "data center revenue contribution",
                "platform profitability",
                "EPS impact",
            ],
        ),
    ],
)
def test_collective_scope_preserves_multi_axis_set_without_cartesian_growth(
    case_key: str, product_intents: list[str]
) -> None:
    request = _request(
        request_id=f"REQ::{case_key}-REPORTED-RESULTS-SCOPE",
        facet_id="reported_results",
        metric_intents=[
            "revenue",
            "operating_income",
            "net_income",
            "diluted_eps",
            "gross_margin",
            "operating_margin",
        ],
        product_intents=product_intents,
        case_key=case_key,
        subject_ticker=case_key,
    )
    payload = {
        "schema_version": "fin_ia_research_material_scope_atoms_v1_0",
        "research_plan_digest": "PLAN::COLLECTIVE",
        "request_scopes": [
            {
                "request_id": request.request_id,
                "product_intent_dispositions": [
                    {
                        "product_intent_index": index,
                        "disposition": "hard_material_axis",
                    }
                    for index in range(3)
                ],
                "requirement_atoms": [
                    {
                        "facet_id": "reported_results",
                        "role": "direct",
                        "metric_intent_indices": list(range(6)),
                        "product_intent_indices": list(range(3)),
                        "period_mode": "any",
                        "coverage_mode": "collective_axes",
                    }
                ],
            }
        ],
    }
    result = compile_research_material_scope(
        payload,
        research_plan_digest="PLAN::COLLECTIVE",
        requests=[request],
        required_request_ids=[request.request_id],
        policy=SCOPE_POLICY,
        material_runtime_policy=MATERIAL_POLICY,
        intent_ontology=ONTOLOGY,
    )

    requirements = result["request_scopes"][0]["research_blueprint"][
        "material_requirements"
    ]
    assert len(requirements) == 1
    assert requirements[0]["metric_ids"] == list(request.metric_intents)
    assert requirements[0]["product_ids"] == list(request.product_intents)
    runtime_requirements = [
        {
            **requirements[0],
            "requirement_id": "REQ::COLLECTIVE-MULTI-AXIS",
            "priority": 1,
        }
    ]
    plan = compile_requirement_plan(
        evidence_request=request.as_dict(),
        material_requirements=runtime_requirements,
        review_k=16,
        schema_version="fin_ia_material_evidence_requirement_plan_v1_1",
    )
    assert plan["maximum_reserved_capacity"] == 2


def test_collective_scope_compilation_is_stable_under_atom_permutation() -> None:
    request = _request()
    first_payload = _working_capital_payload(request.request_id)
    second_payload = deepcopy(first_payload)
    second_payload["request_scopes"][0]["requirement_atoms"].reverse()

    first = compile_research_material_scope(
        first_payload,
        research_plan_digest="PLAN::DEVELOPMENT",
        requests=[request],
        required_request_ids=[request.request_id],
        policy=SCOPE_POLICY,
        material_runtime_policy=MATERIAL_POLICY,
        intent_ontology=ONTOLOGY,
    )
    second = compile_research_material_scope(
        second_payload,
        research_plan_digest="PLAN::DEVELOPMENT",
        requests=[request],
        required_request_ids=[request.request_id],
        policy=SCOPE_POLICY,
        material_runtime_policy=MATERIAL_POLICY,
        intent_ontology=ONTOLOGY,
    )
    assert first == second


def test_material_scope_expands_hard_product_same_basis_by_metric() -> None:
    request = _request(
        request_id="REQ::COST-TEMPORAL-SCOPE",
        facet_id="reported_results",
        metric_intents=["revenue", "gross_profit"],
        product_intents=["FY2024 FY2025 comparison", "membership fee revenue"],
        fiscal_years=[2024, 2025],
    )
    payload = {
        "schema_version": "fin_ia_research_material_scope_atoms_v1_0",
        "research_plan_digest": "PLAN::TEMPORAL",
        "request_scopes": [
            {
                "request_id": request.request_id,
                "product_intent_dispositions": [
                    {
                        "product_intent_index": 0,
                        "disposition": "temporal_directive",
                    },
                    {
                        "product_intent_index": 1,
                        "disposition": "hard_material_axis",
                    },
                ],
                "requirement_atoms": [
                    {
                        "facet_id": "reported_results",
                        "role": "direct",
                        "metric_intent_indices": [0],
                        "product_intent_indices": [1],
                        "period_mode": "all_periods_same_basis",
                        "coverage_mode": "single_binding",
                    },
                    {
                        "facet_id": "reported_results",
                        "role": "direct",
                        "metric_intent_indices": [1],
                        "product_intent_indices": [1],
                        "period_mode": "all_periods_same_basis",
                        "coverage_mode": "single_binding",
                    },
                ],
            }
        ],
    }
    result = compile_research_material_scope(
        payload,
        research_plan_digest="PLAN::TEMPORAL",
        requests=[request],
        required_request_ids=[request.request_id],
        policy=SCOPE_POLICY,
        material_runtime_policy=MATERIAL_POLICY,
        intent_ontology=ONTOLOGY,
    )

    requirements = result["request_scopes"][0]["research_blueprint"][
        "material_requirements"
    ]
    assert len(requirements) == 2
    assert {tuple(row["metric_ids"]) for row in requirements} == {
        ("revenue",),
        ("gross_profit",),
    }
    assert all(row["product_ids"] == ["membership fee revenue"] for row in requirements)
    assert all(row["fiscal_years"] == [2024, 2025] for row in requirements)


def test_material_scope_messages_are_request_visible_and_candidate_blind() -> None:
    request = _request()
    system, user = compile_research_material_scope_messages(
        research_plan_digest="PLAN::DEVELOPMENT",
        requests=[request],
        required_request_ids=[request.request_id],
        policy=SCOPE_POLICY,
        material_runtime_policy=MATERIAL_POLICY,
        intent_ontology=ONTOLOGY,
    )
    visible = json.loads(user["content"])
    serialized = json.dumps(visible, ensure_ascii=False)

    assert system["role"] == "system"
    assert visible["requests"][0]["request_id"] == request.request_id
    assert visible["requests"][0]["metric_intents"][0] == {
        "index": 0,
        "value": "inventory",
    }
    contract = visible["output_contract"]
    schema = contract["json_schema"]
    assert contract["top_level_fields_exact"] == [
        "schema_version",
        "research_plan_digest",
        "request_scopes",
    ]
    assert schema["additionalProperties"] is False
    assert schema["required"] == contract["top_level_fields_exact"]
    scope_properties = schema["properties"]["request_scopes"]["items"][
        "properties"
    ]
    disposition_enum = scope_properties["product_intent_dispositions"]["items"][
        "properties"
    ]["disposition"]["enum"]
    atom_properties = scope_properties["requirement_atoms"]["items"]["properties"]
    assert set(disposition_enum) == set(SCOPE_POLICY["allowed_intent_dispositions"])
    assert set(atom_properties["period_mode"]["enum"]) == set(
        SCOPE_POLICY["allowed_period_modes"]
    )
    assert set(atom_properties["coverage_mode"]["enum"]) == set(
        SCOPE_POLICY["allowed_coverage_modes"]
    )
    assert any(
        "request_scopes (plural)" in rule
        for rule in contract["cross_field_rules"]
    )
    assert "request_scopes (plural)" in system["content"]
    assert "source_record_id" not in serialized
    assert "compiled_object_id" not in serialized
    assert "COBJ::" not in serialized
    assert "http://" not in serialized and "https://" not in serialized


@pytest.mark.parametrize(
    ("case_key", "facet_id", "metric", "product"),
    [
        ("DELL", "working_capital_risk", "inventory", "AI server inventory"),
        ("MU", "upstream_capacity_context", "shipments", "HBM capacity"),
        ("NVDA", "orders_and_backlog", "orders", "AI platform demand"),
    ],
)
def test_model_visible_contract_is_case_neutral_and_request_bound(
    case_key: str,
    facet_id: str,
    metric: str,
    product: str,
) -> None:
    request = _request(
        request_id=f"REQ::{case_key}-CONTRACT",
        case_key=case_key,
        subject_ticker=case_key,
        facet_id=facet_id,
        metric_intents=[metric],
        product_intents=[product],
    )
    _, user = compile_research_material_scope_messages(
        research_plan_digest=f"PLAN::{case_key}",
        requests=[request],
        required_request_ids=[request.request_id],
        policy=SCOPE_POLICY,
        material_runtime_policy=MATERIAL_POLICY,
        intent_ontology=ONTOLOGY,
    )
    visible = json.loads(user["content"])
    contract = visible["output_contract"]
    request_id_enum = contract["json_schema"]["properties"]["request_scopes"][
        "items"
    ]["properties"]["request_id"]["enum"]
    assert request_id_enum == [request.request_id]
    assert visible["requests"][0]["facet_id"] == facet_id
    assert "candidate_id" not in json.dumps(visible, ensure_ascii=False)


def test_legacy_R2_singular_top_level_shape_remains_rejected() -> None:
    request = _request()
    payload = _working_capital_payload(request.request_id)
    payload["request_scope"] = payload.pop("request_scopes")
    with pytest.raises(ResearchMaterialScopeError, match="output_fields_invalid"):
        compile_research_material_scope(
            payload,
            research_plan_digest="PLAN::DEVELOPMENT",
            requests=[request],
            required_request_ids=[request.request_id],
            policy=SCOPE_POLICY,
            material_runtime_policy=MATERIAL_POLICY,
            intent_ontology=ONTOLOGY,
        )


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (
            lambda value: value["request_scopes"][0][
                "product_intent_dispositions"
            ].clear(),
            "product_disposition_coverage_invalid",
        ),
        (
            lambda value: value["request_scopes"][0]["requirement_atoms"].pop(),
            "metric_coverage_invalid",
        ),
        (
            lambda value: value["request_scopes"][0]["requirement_atoms"][0].update(
                {"metric_intent_indices": [2]}
            ),
            "metric_indices_invalid",
        ),
        (
            lambda value: value["request_scopes"][0].update(
                {"candidate_id": "COBJ::ANSWER"}
            ),
            "request_fields_invalid",
        ),
        (
            lambda value: value["request_scopes"][0]["requirement_atoms"][1].update(
                {"metric_intent_indices": [0]}
            ),
            "role_metric_axis_forbidden",
        ),
    ],
)
def test_material_scope_fails_closed_on_scope_expansion_and_missing_axes(
    mutation, error: str
) -> None:
    request = _request()
    payload = _working_capital_payload(request.request_id)
    mutation(payload)
    with pytest.raises(ResearchMaterialScopeError, match=error):
        compile_research_material_scope(
            payload,
            research_plan_digest="PLAN::DEVELOPMENT",
            requests=[request],
            required_request_ids=[request.request_id],
            policy=SCOPE_POLICY,
            material_runtime_policy=MATERIAL_POLICY,
            intent_ontology=ONTOLOGY,
        )


def test_material_scope_rejects_contextual_intent_as_hard_axis() -> None:
    request = _request()
    payload = _working_capital_payload(request.request_id)
    payload["request_scopes"][0]["requirement_atoms"][0][
        "product_intent_indices"
    ] = [0]
    with pytest.raises(ResearchMaterialScopeError, match="non_hard_product_bound"):
        compile_research_material_scope(
            payload,
            research_plan_digest="PLAN::DEVELOPMENT",
            requests=[request],
            required_request_ids=[request.request_id],
            policy=SCOPE_POLICY,
            material_runtime_policy=MATERIAL_POLICY,
            intent_ontology=ONTOLOGY,
        )


def test_material_scope_cannot_weaken_known_hard_product_when_resolving_new_topic() -> None:
    request = _request(
        product_intents=[
            "AI-optimized servers",
            "novel composite deployment economics",
        ]
    )
    payload = _working_capital_payload(request.request_id)
    payload["request_scopes"][0]["product_intent_dispositions"] = [
        {
            "product_intent_index": 0,
            "disposition": "contextual_retrieval_only",
        },
        {
            "product_intent_index": 1,
            "disposition": "contextual_retrieval_only",
        },
    ]
    with pytest.raises(
        ResearchMaterialScopeError, match="fixed_disposition_changed"
    ):
        compile_research_material_scope(
            payload,
            research_plan_digest="PLAN::DEVELOPMENT",
            requests=[request],
            required_request_ids=[request.request_id],
            policy=SCOPE_POLICY,
            material_runtime_policy=MATERIAL_POLICY,
            intent_ontology=ONTOLOGY,
        )


def test_material_scope_parser_requires_exact_json() -> None:
    payload = _working_capital_payload("REQ::DELL-WORKING-CAPITAL-SCOPE")
    parsed = parse_research_material_scope_output(
        json.dumps(payload, ensure_ascii=False)
    )
    assert parsed["schema_version"] == "fin_ia_research_material_scope_atoms_v1_0"

    with pytest.raises(ResearchMaterialScopeError, match="not_exact_json"):
        parse_research_material_scope_output(
            "```json\n" + json.dumps(payload) + "\n```"
        )
    with pytest.raises(ResearchMaterialScopeError, match="json_invalid"):
        parse_research_material_scope_output("{not-json}")
