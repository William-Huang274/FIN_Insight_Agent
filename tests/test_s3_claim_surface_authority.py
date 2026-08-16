from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    compile_finance_judgment_tool,
)
from sec_agent.research.claim_authority import (  # noqa: E402
    compile_claim_authority_research_input,
)
from sec_agent.research.claim_surface_authority import (  # noqa: E402
    ClaimSurfaceAuthorityError,
    compile_claim_surface_authority_research_input,
    load_claim_surface_authority_policy,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
    compile_current_research_messages,
    validate_current_research_output,
)
from tests.test_s3_current_research_consumer import (  # noqa: E402
    CLAIM_AUTHORITY_POLICY,
    _current_inputs,
    _json,
)


SURFACE_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_v1_0.json"
)
ALIAS_SURFACE_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_v1_1.json"
)
FAILED_CHAT_PAYLOAD = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_authority_chat_r1_failed_payload_v1_0.json"
)
POSITIVE_PAYLOAD = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_fake_payload_v1_0.json"
)
ALIAS_POSITIVE_PAYLOAD = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_alias_fake_payload_v1_0.json"
)
QF_REF = "QF::DELL::AI_SERVER_OPERATING_INCOME_RATE_TARGET::FY2027Q1"


@pytest.fixture(scope="module")
def surface_input() -> dict[str, object]:
    _, _, base = _current_inputs()
    claim_input = compile_claim_authority_research_input(
        base,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    return compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(SURFACE_POLICY),
    )


@pytest.fixture(scope="module")
def alias_surface_input() -> dict[str, object]:
    _, _, base = _current_inputs()
    claim_input = compile_claim_authority_research_input(
        base,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    return compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(ALIAS_SURFACE_POLICY),
    )


def _normalized_failed_payload() -> dict[str, object]:
    payload = _json(FAILED_CHAT_PAYLOAD)
    payload["cells"][0]["what_would_change"]["threshold_numeric_ref"] = None
    return payload


def test_surface_policy_is_source_bound_and_does_not_create_numeric_fact(
    surface_input: dict[str, object],
) -> None:
    policy = load_claim_surface_authority_policy(_json(SURFACE_POLICY))
    assert policy["authority"]["model_owns_narrative_judgment"] is True
    assert policy["authority"][
        "harness_renders_selected_fact_surface_without_point_estimate"
    ] is True
    assert surface_input["schema_version"] == (
        "fin_ia_current_research_input_v1_3"
    )
    fact = surface_input["source_bound_qualitative_fact_cards"][0]
    assert fact["qualitative_fact_ref"] == QF_REF
    assert fact["display_surface_zh"] == "中个位数经营利润率目标"
    assert fact["point_estimate_forbidden"] is True
    assert fact["audited_numeric_fact"] is False
    assert all(
        row["numeric_ref"] != QF_REF
        for row in surface_input["numeric_fact_cards"]
    )


def test_alias_surface_contract_exposes_only_relation_refs_to_model(
    alias_surface_input: dict[str, object],
) -> None:
    assert alias_surface_input["schema_version"] == (
        "fin_ia_current_research_input_v1_4"
    )
    assert alias_surface_input["model_output_contract"][
        "payload_schema_version"
    ] == "fin_ia_current_research_judgment_payload_v1_5"
    assert alias_surface_input["claim_surface_authority_contract"][
        "model_view_mode"
    ] == "claim_relation_alias_compact_v1"

    messages = compile_current_research_messages(
        alias_surface_input,
        required_cell_ids=["CELL::value_capture"],
        submission_transport="final_tool",
    )
    shape = json.loads(messages[1]["content"])["output_contract"][
        "payload_shape"
    ]["submit_research_judgment_arguments"]
    assert set(shape["claim_relations"][0]) == {
        "atom_field",
        "claim_relation_ref",
    }

    tool = compile_finance_judgment_tool(
        research_input=alias_surface_input,
        required_cell_ids=["CELL::value_capture"],
        strict=True,
    )
    relation = tool["function"]["parameters"]["properties"][
        "claim_relations"
    ]["items"]["properties"]
    assert set(relation) == {"atom_field", "claim_relation_ref"}
    assert relation["claim_relation_ref"]["enum"] == [
        "CR::DELL::PRODUCT_TARGET",
        "CR::DELL::COMPANY_MARGIN_OBSERVATION",
        "CR::DELL::MULTI_DRIVER_CONTEXT",
        "CR::DELL::PROFIT_BRIDGE_GAP",
    ]


def test_alias_selection_is_expanded_locally_before_delivery(
    alias_surface_input: dict[str, object],
) -> None:
    payload = _json(ALIAS_POSITIVE_PAYLOAD)
    validated = validate_current_research_output(
        payload,
        research_input=alias_surface_input,
        required_cell_ids=["CELL::value_capture"],
    )
    relations = validated["cells"][0]["claim_relations"]
    assert relations[0] == {
        "atom_field": "thesis_atom",
        "claim_relation_ref": "CR::DELL::PRODUCT_TARGET",
        "claim_subject": "ai_server_product",
        "claim_outcome": "product_operating_income_rate_target",
        "claim_relation": "management_reported_in_line_with_target",
        "attribution_basis": "issuer_management_assertion",
        "claim_scope": "product",
        "financial_scope": "product_financial",
        "causal_bridge_authority": "management_assertion_only",
    }
    assert all(len(row) == 9 for row in relations)

    deliverable = compile_current_research_deliverable(
        research_input=alias_surface_input,
        judgment_output=payload,
        required_cell_ids=["CELL::value_capture"],
    )
    assert deliverable["schema_version"] == (
        "fin_ia_current_research_deliverable_v1_5"
    )
    assert deliverable["cells"][0]["claim_relations"] == relations


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            {
                "claim_relations": _json(POSITIVE_PAYLOAD)["cells"][0][
                    "claim_relations"
                ]
            },
            "claim_surface_claim_relation_invalid",
        ),
        (
            {
                "claim_relations": [
                    {
                        "atom_field": "thesis_atom",
                        "claim_relation_ref": "CR::MU::PRODUCT_TARGET",
                    },
                    *_json(ALIAS_POSITIVE_PAYLOAD)["cells"][0][
                        "claim_relations"
                    ][1:],
                ]
            },
            "claim_surface_relation_alias_invalid",
        ),
    ],
)
def test_alias_surface_mutations_fail_closed(
    alias_surface_input: dict[str, object],
    mutation: dict[str, object],
    expected: str,
) -> None:
    payload = _json(ALIAS_POSITIVE_PAYLOAD)
    payload["cells"][0].update(deepcopy(mutation))
    with pytest.raises(CurrentResearchConsumerError) as exc:
        validate_current_research_output(
            payload,
            research_input=alias_surface_input,
            required_cell_ids=["CELL::value_capture"],
        )
    assert exc.value.code == expected


def test_surface_model_view_and_final_tool_are_compiled_from_same_contract(
    surface_input: dict[str, object],
) -> None:
    messages = compile_current_research_messages(
        surface_input,
        required_cell_ids=["CELL::value_capture"],
        submission_transport="final_tool",
    )
    visible = json.loads(messages[1]["content"])
    assert visible["claim_surface_authority_contract"][
        "structured_claim_relation_primary"
    ] is True
    assert visible["source_bound_qualitative_fact_catalog"][0][
        "qualitative_fact_ref"
    ] == QF_REF
    shape = visible["output_contract"]["payload_shape"][
        "submit_research_judgment_arguments"
    ]
    assert "claim_relations" in shape
    assert "qualitative_fact_refs" in shape

    tool = compile_finance_judgment_tool(
        research_input=surface_input,
        required_cell_ids=["CELL::value_capture"],
        strict=True,
    )
    function = tool["function"]
    properties = function["parameters"]["properties"]
    assert function["strict"] is True
    relation_properties = properties["claim_relations"]["items"][
        "properties"
    ]
    assert relation_properties["claim_subject"]["enum"] == surface_input[
        "model_output_contract"
    ]["allowed_claim_subjects"]
    assert properties["qualitative_fact_refs"]["items"]["enum"] == [
        QF_REF
    ]


def test_saved_failed_live_replay_exposes_both_missing_contract_layers(
    surface_input: dict[str, object],
) -> None:
    raw = _normalized_failed_payload()
    with pytest.raises(CurrentResearchConsumerError) as exc:
        validate_current_research_output(
            raw,
            research_input=surface_input,
            required_cell_ids=["CELL::value_capture"],
        )
    assert exc.value.code == "research_consumer_output_cell_fields_invalid"

    positive = _json(POSITIVE_PAYLOAD)
    alias_migrated = deepcopy(raw)
    for field in ("claim_relations", "qualitative_fact_refs"):
        alias_migrated["cells"][0][field] = deepcopy(
            positive["cells"][0][field]
        )
    with pytest.raises(CurrentResearchConsumerError) as exc:
        validate_current_research_output(
            alias_migrated,
            research_input=surface_input,
            required_cell_ids=["CELL::value_capture"],
        )
    assert exc.value.code == "research_consumer_thesis_atom_invalid"

    alias_migrated["cells"][0]["thesis_atom"] = alias_migrated["cells"][0][
        "thesis_atom"
    ].replace("其中个位数经营利润率目标", "所选管理层经营利润率目标")
    alias_migrated["cells"][0]["mechanism_atom"] = alias_migrated[
        "cells"
    ][0]["mechanism_atom"].replace(
        "中个位数经营利润率目标", "所选管理层经营利润率目标"
    )
    with pytest.raises(CurrentResearchConsumerError) as exc:
        validate_current_research_output(
            alias_migrated,
            research_input=surface_input,
            required_cell_ids=["CELL::value_capture"],
        )
    assert exc.value.code == "claim_surface_narrative_relation_conflict"


@pytest.mark.parametrize(
    "mechanism_atom",
    [
        (
            "管理层关于 AI 服务器产品盈利符合其所述目标的表述属自述口径，"
            "未经独立审计，不能据此建立产品到分部或公司利润的财务桥；"
            "产品级价格、量与配置拆分的缺失使产品盈利如何转化为分部或"
            "公司利润不可推断。"
        ),
        (
            "“AI 服务器收入转化为公司利润”的命题缺乏直接证据，"
            "不能据此建立产品到公司的利润桥。"
        ),
        (
            "The evidence does not establish that AI server revenue drives "
            "company profit, so the product-to-company bridge remains unproven."
        ),
    ],
)
def test_negated_or_unsupported_causal_surface_is_not_a_positive_conflict(
    alias_surface_input: dict[str, object],
    mechanism_atom: str,
) -> None:
    payload = _json(ALIAS_POSITIVE_PAYLOAD)
    payload["cells"][0]["mechanism_atom"] = mechanism_atom

    validated = validate_current_research_output(
        payload,
        research_input=alias_surface_input,
        required_cell_ids=["CELL::value_capture"],
    )

    assert validated["cells"][0]["mechanism_atom"] == mechanism_atom


@pytest.mark.parametrize(
    "mechanism_atom",
    [
        "AI 服务器增长驱动 Dell 公司利润改善。",
        "AI server revenue translates into Dell company profit.",
    ],
)
def test_positive_cross_scope_causal_surface_still_fails_closed(
    alias_surface_input: dict[str, object],
    mechanism_atom: str,
) -> None:
    payload = _json(ALIAS_POSITIVE_PAYLOAD)
    payload["cells"][0]["mechanism_atom"] = mechanism_atom

    with pytest.raises(CurrentResearchConsumerError) as exc:
        validate_current_research_output(
            payload,
            research_input=alias_surface_input,
            required_cell_ids=["CELL::value_capture"],
        )

    assert exc.value.code == "claim_surface_narrative_relation_conflict"


def test_corrected_successor_renders_qualitative_surface_without_point_estimate(
    surface_input: dict[str, object],
) -> None:
    payload = _json(POSITIVE_PAYLOAD)
    validated = validate_current_research_output(
        payload,
        research_input=surface_input,
        required_cell_ids=["CELL::value_capture"],
    )
    row = validated["cells"][0]
    assert row["claim_relations"][0]["claim_subject"] == "ai_server_product"
    assert row["claim_relations"][0]["claim_relation"] == (
        "management_reported_in_line_with_target"
    )
    assert row["qualitative_fact_refs"] == [QF_REF]
    assert row["claim_surface_authority_receipt"][
        "structured_claim_relation_primary"
    ] is True
    assert row["claim_surface_authority_receipt"][
        "qualitative_fact_point_estimate_generated"
    ] is False

    deliverable = compile_current_research_deliverable(
        research_input=surface_input,
        judgment_output=payload,
        required_cell_ids=["CELL::value_capture"],
    )
    assert deliverable["schema_version"] == (
        "fin_ia_current_research_deliverable_v1_4"
    )
    surfaces = deliverable["cells"][0][
        "source_bound_qualitative_fact_surfaces"
    ]
    assert surfaces == [
        {
            "qualitative_fact_ref": QF_REF,
            "display_surface_zh": "中个位数经营利润率目标",
            "qualifier_zh": (
                "管理层目标；未经独立审计；不得转换为单点数值或"
                "产品到分部／公司的利润桥"
            ),
            "point_estimate_generated": False,
        }
    ]
    assert deliverable["rendering_authority"][
        "harness_generated_research_conclusion"
    ] is False


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            {"qualitative_fact_refs": ["QF::MU::CROSS_CASE"]},
            "research_consumer_qualitative_fact_boundary_invalid",
        ),
        (
            {
                "evidence_uses": [
                    {
                        "evidence_ref": "EV::0063F22F643B94ED",
                        "use_role": "context",
                    },
                    {
                        "evidence_ref": "EV::5388E016C17032C1",
                        "use_role": "limit",
                    },
                    {
                        "evidence_ref": "EV::38BBF02CB241E81D",
                        "use_role": "limit",
                    },
                    {
                        "evidence_ref": "EV::7F4D7E6762C21D83",
                        "use_role": "support",
                    },
                ]
            },
            "claim_surface_required_authority_missing",
        ),
        (
            {
                "claim_relations": [
                    {
                        **_json(POSITIVE_PAYLOAD)["cells"][0][
                            "claim_relations"
                        ][0],
                        "claim_relation": "same_scope_numeric_observation",
                    },
                    *_json(POSITIVE_PAYLOAD)["cells"][0][
                        "claim_relations"
                    ][1:],
                ]
            },
            "claim_surface_combination_invalid",
        ),
    ],
)
def test_surface_mutations_fail_closed(
    surface_input: dict[str, object],
    mutation: dict[str, object],
    expected: str,
) -> None:
    payload = _json(POSITIVE_PAYLOAD)
    payload["cells"][0].update(deepcopy(mutation))
    with pytest.raises(CurrentResearchConsumerError) as exc:
        validate_current_research_output(
            payload,
            research_input=surface_input,
            required_cell_ids=["CELL::value_capture"],
        )
    assert exc.value.code == expected


@pytest.mark.parametrize("foreign_case", ["MU", "NVDA"])
def test_surface_policy_cannot_cross_case_boundary(foreign_case: str) -> None:
    _, _, base = _current_inputs()
    claim_input = compile_claim_authority_research_input(
        base,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    contaminated = deepcopy(claim_input)
    contaminated["case_identity"]["case_key"] = foreign_case
    with pytest.raises(ClaimSurfaceAuthorityError) as exc:
        compile_claim_surface_authority_research_input(
            contaminated,
            policy=_json(SURFACE_POLICY),
        )
    assert exc.value.code == "claim_surface_base_input_not_qualified"


def test_surface_policy_rejects_source_digest_drift() -> None:
    _, _, base = _current_inputs()
    claim_input = compile_claim_authority_research_input(
        base,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    policy = _json(SURFACE_POLICY)
    policy["source_bound_qualitative_facts"][0][
        "source_evidence_item_digest"
    ] = "0" * 64
    with pytest.raises(ClaimSurfaceAuthorityError) as exc:
        compile_claim_surface_authority_research_input(
            claim_input,
            policy=policy,
        )
    assert exc.value.code == "claim_surface_qualitative_fact_source_drift"
