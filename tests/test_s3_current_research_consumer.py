from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from sec_agent.research.current_consumer import (
    CURRENT_RESEARCH_MODEL_TEXT_SERVER_PATTERN,
    CurrentResearchConsumerError,
    bind_current_research_model_text_schema_definition,
    compile_current_research_model_text_schema,
    compile_current_research_deliverable,
    compile_current_research_input,
    compile_current_research_messages,
    load_current_research_consumer_policy,
    parse_current_research_output,
    validate_current_research_evidence_route,
    validate_current_research_model_text,
    validate_current_research_output,
)
import sec_agent.research.current_consumer as current_consumer
from sec_agent.research.claim_authority import (
    compile_claim_authority_research_input,
    load_claim_authority_policy,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_resource_registry import read_registered_runtime_json


POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_2.json"
)
FIVE_CELL_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_3.json"
)
FIVE_CELL_POLICY_SUCCESSOR = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_4.json"
)
OBJECTIVE = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
)
ATOMS = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
)
FAKE_PAYLOAD_V1_2 = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_current_research_consumer_fake_payload_v1_2.json"
)
FIVE_CELL_FAKE_PAYLOAD = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_current_research_consumer_fake_payload_v1_3.json"
)
CLAIM_AUTHORITY_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_claim_authority_v1_0.json"
)
R2_FULL_RESULT = ROOT / (
    "data/workbench_private/fin_0_1_3_s3_current_research_consumer/"
    "research-context-chat-r2-value-capture/full_result.json"
)
R1_FAILED_PAYLOAD = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_consumer_canary_r1_failed_payload.json"
)
READ = frozenset({"current_product:read"})


def _zero_call_runner():
    path = ROOT / "scripts/research/run_s3_current_research_consumer_zero_call.py"
    spec = importlib.util.spec_from_file_location(
        "s3_current_research_consumer_zero_call_runner",
        path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bounded_zero_call_runner():
    path = ROOT / "scripts/research/run_s3_bounded_finance_loop_zero_call.py"
    spec = importlib.util.spec_from_file_location(
        "s3_bounded_finance_loop_zero_call_runner",
        path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    paths = resolve_runtime_paths(ROOT)
    evidence_config = deepcopy(
        read_registered_runtime_json(
            ROOT, "application.config.current_research_evidence_pack_projection"
        )
    )
    # Historical fixed-Pack authority fixtures below are digest-bound to the
    # pre-anchor projection. Keep that immutable replay surface separate from
    # the current anchored product path exercised by the dedicated anchor and
    # dynamic Runtime tests.
    evidence_config["schema_version"] = (
        "fin_ia_current_research_evidence_pack_projection_config_v1_0"
    )
    evidence_config.pop("reviewed_anchor_catalog_resource_id")
    evidence_service = ResearchEvidencePackService(
        config=evidence_config,
        result=read_registered_runtime_json(
            ROOT, str(evidence_config["source_result_resource_id"])
        ),
        private_object_root=(
            paths.reviewed_evidence_root
            / str(evidence_config["private_object_root_relative"])
        ),
        private_root_base=paths.reviewed_evidence_root,
    )
    evidence_pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", READ)
    )
    retrieval = ResearchRetrievalService(
        snapshot=read_registered_runtime_json(
            ROOT, "application.result.current_research_retrieval_snapshot"
        ),
        ranking_comparison=read_registered_runtime_json(
            ROOT, "application.result.current_s1c_ranking_comparison_projection"
        ),
        kernel=read_registered_runtime_json(
            ROOT, "application.config.current_financial_research_kernel"
        ),
        route_policy=read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        planning_policy=read_registered_runtime_json(
            ROOT, "application.config.current_research_planning_policy"
        ),
        hybrid_candidate_runtime=None,
        company_financial_fact_mart_path=(
            paths.company_financial_fact_mart_path
        ),
    )
    controlled = retrieval.execute_controlled_plan(
        "DELL",
        _json(OBJECTIVE),
        _json(ATOMS),
        ResearchRetrievalPrincipal("current", READ),
    )
    research_input = compile_current_research_input(
        policy=_json(POLICY),
        evidence_pack=evidence_pack,
        controlled_plan=controlled,
    )
    return evidence_pack, controlled, research_input


@pytest.fixture(scope="module")
def current_inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    return _current_inputs()


@pytest.fixture(scope="module")
def claim_authority_input(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> dict[str, object]:
    _, _, research_input = current_inputs
    return compile_claim_authority_research_input(
        research_input,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )


def _r2_judgment() -> dict[str, object]:
    full = _json(R2_FULL_RESULT)
    return deepcopy(full["loop_result"]["judgment_output"])


def _bounded_claim_judgment() -> dict[str, object]:
    payload = _r2_judgment()
    row = payload["cells"][0]
    row.update(
        {
            "claim_scope": "multi_scope",
            "financial_scope": "multi_scope_financial",
            "causal_bridge_authority": "multi_driver_context_only",
            "thesis_atom": (
                "Dell company and segment profit improved while AI server mix "
                "pressured gross margin, but the reviewed evidence does not "
                "isolate the product contribution."
            ),
            "mechanism_atom": (
                "Management describes product profitability, storage "
                "profitability, traditional server margins and revenue scale as "
                "separate factors, so the current pack cannot allocate the "
                "company change to one product."
            ),
            "counterargument_atom": (
                "The product target is unaudited and the missing product profit, "
                "unit, price and mix bridge leaves the value-capture conclusion "
                "bounded."
            ),
        }
    )
    return payload


def test_claim_authority_overlay_is_fixed_pack_only_and_does_not_mutate_v1_2(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
    claim_authority_input: dict[str, object],
) -> None:
    _, _, base = current_inputs
    assert base["schema_version"] == "fin_ia_current_research_input_v1_1"
    assert "claim_authority_contract" not in base
    assert claim_authority_input["schema_version"] == (
        "fin_ia_current_research_input_v1_2"
    )
    boundary = claim_authority_input["claim_authority_contract"]
    assert boundary["base_research_input_digest"] == base["research_input_digest"]
    assert boundary["fixed_pack_unit_test_only"] is True
    assert boundary["dynamic_retrieval_executed"] is False
    assert boundary["agentic_research_claimed"] is False
    assert boundary["qualified_cell_ids"] == ["CELL::value_capture"]
    target = next(
        row
        for row in claim_authority_input["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )
    assert target["claim_authority_card"][
        "allowed_causal_bridge_authorities"
    ] == [
        "same_scope_observation_only",
        "management_assertion_only",
        "multi_driver_context_only",
        "bridge_unavailable",
    ]
    assert "direct_cross_scope_bridge" not in target["claim_authority_card"][
        "allowed_causal_bridge_authorities"
    ]


def test_claim_authority_policy_and_model_view_are_exact(
    claim_authority_input: dict[str, object],
) -> None:
    loaded = load_claim_authority_policy(_json(CLAIM_AUTHORITY_POLICY))
    assert loaded["authority"]["model_owns_narrative_judgment"] is True
    messages = compile_current_research_messages(
        claim_authority_input,
        required_cell_ids=["CELL::value_capture"],
        submission_transport="final_tool",
    )
    visible = json.loads(messages[1]["content"])
    assert visible["claim_authority_contract"]["agentic_research_claimed"] is False
    card = visible["cells"][0]["claim_authority_card"]
    assert card["cell_id"] == "CELL::value_capture"
    shape = visible["output_contract"]["payload_shape"][
        "submit_research_judgment_arguments"
    ]
    assert shape["claim_scope"].startswith("one claim scope")
    assert shape["financial_scope"].startswith("one financial scope")
    assert shape["causal_bridge_authority"].startswith("one bridge authority")


def test_saved_r2_overclaim_is_rejected_by_claim_authority_replay(
    claim_authority_input: dict[str, object],
) -> None:
    payload = _r2_judgment()
    payload["cells"][0].update(
        {
            "claim_scope": "multi_scope",
            "financial_scope": "multi_scope_financial",
            "causal_bridge_authority": "multi_driver_context_only",
        }
    )
    with pytest.raises(CurrentResearchConsumerError) as exc:
        validate_current_research_output(
            payload,
            research_input=claim_authority_input,
            required_cell_ids=["CELL::value_capture"],
        )
    assert exc.value.code == (
        "claim_authority_cross_scope_causal_language_unbound"
    )


def test_bounded_multi_driver_claim_passes_without_harness_authorship(
    claim_authority_input: dict[str, object],
) -> None:
    payload = _bounded_claim_judgment()
    validated = validate_current_research_output(
        payload,
        research_input=claim_authority_input,
        required_cell_ids=["CELL::value_capture"],
    )
    row = validated["cells"][0]
    assert row["claim_scope"] == "multi_scope"
    assert row["financial_scope"] == "multi_scope_financial"
    assert row["causal_bridge_authority"] == "multi_driver_context_only"
    assert row["claim_authority_receipt"][
        "cross_scope_causal_language_guard_pass"
    ] is True
    assert row["claim_authority_receipt"][
        "harness_generated_research_judgment"
    ] is False
    deliverable = compile_current_research_deliverable(
        research_input=claim_authority_input,
        judgment_output=payload,
        required_cell_ids=["CELL::value_capture"],
    )
    assert deliverable["schema_version"] == (
        "fin_ia_current_research_deliverable_v1_3"
    )
    assert deliverable["fixed_pack_experiment_boundary"] == {
        "dynamic_retrieval_executed": False,
        "agentic_research_claimed": False,
        "harness_generated_research_conclusion": False,
    }


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            {
                "causal_bridge_authority": "direct_cross_scope_bridge",
            },
            "claim_authority_output_enum_invalid",
        ),
        (
            {
                "claim_scope": "product",
                "financial_scope": "company_financial",
            },
            "claim_authority_scope_combination_invalid",
        ),
        (
            {
                "claim_scope": "product",
                "financial_scope": "product_financial",
                "causal_bridge_authority": "management_assertion_only",
                "evidence_uses": [
                    {
                        "evidence_ref": "EV::0063F22F643B94ED",
                        "use_role": "context",
                    },
                    {
                        "evidence_ref": "EV::7F4D7E6762C21D83",
                        "use_role": "support",
                    }
                ],
            },
            "claim_authority_management_assertion_evidence_missing",
        ),
    ],
)
def test_claim_authority_mutations_fail_closed(
    claim_authority_input: dict[str, object],
    mutation: dict[str, object],
    expected: str,
) -> None:
    payload = _bounded_claim_judgment()
    payload["cells"][0].update(deepcopy(mutation))
    with pytest.raises(CurrentResearchConsumerError) as exc:
        validate_current_research_output(
            payload,
            research_input=claim_authority_input,
            required_cell_ids=["CELL::value_capture"],
        )
    assert exc.value.code == expected


def test_current_input_consumes_reviewed_pack_and_deduplicated_numeric_facts(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    evidence_pack, controlled, research_input = current_inputs

    assert controlled["summary"]["numeric_fact_count"] == 58
    summary = research_input["input_selection_summary"]
    assert summary["semantic_unique_fact_count_before_period_selection"] == 45
    assert summary["model_visible_numeric_fact_count"] == 25
    assert summary["model_visible_evidence_count"] == 19
    assert summary["model_visible_gap_count"] == 10
    assert summary["model_visible_numeric_relation_count"] == 10
    assert len(evidence_pack["evidence_items"]) == 20
    assert [row["cell_id"] for row in research_input["cells"]] == [
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    ]
    transcripts = [
        row
        for row in research_input["evidence_cards"]
        if row["source_type"] == "EARNINGS_CALL_TRANSCRIPT"
    ]
    assert len(transcripts) == 5
    assert all(
        row["source_tier"] == "official_hosted_management_call_transcript"
        for row in transcripts
    )
    assert "EARNINGS_CALL_TRANSCRIPT" not in research_input["objective"][
        "allowed_source_types"
    ]
    assert research_input["authority"]["source_policy_domains_remain_separate"]
    assert "candidates" not in research_input
    assert "rejected_items" not in research_input
    assert all("candidates" not in row for row in research_input["cells"])


def test_model_sees_exact_facts_but_does_not_own_fact_rendering(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    messages = compile_current_research_messages(research_input)
    visible = json.loads(messages[1]["content"])
    serialized = messages[1]["content"]

    assert visible["case_identity"]["subject_ticker"] == "DELL"
    assert "43842000000" in serialized
    assert "24.4 billion" in serialized
    assert "51.3 billion" in serialized
    assert "source_visible_fact_excerpt" in serialized
    assert "Do not repeat or alter identities" in serialized
    assert len(messages[1]["content"]) <= 80000
    for internal_field in (
        "target_id",
        "source_record_id",
        "source_text_digest",
        "source_numeric_fact_ids",
        "source_fact_request_ids",
        "source_observation_ids",
        "source_digests",
        "citation_urls",
    ):
        assert internal_field not in visible
        assert f'"{internal_field}"' not in serialized


def test_fake_judgments_compile_a_reference_safe_workpaper(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    fake = _json(FAKE_PAYLOAD_V1_2)
    validated = validate_current_research_output(
        fake, research_input=research_input
    )
    deliverable = compile_current_research_deliverable(
        research_input=research_input,
        judgment_output=fake,
    )

    assert len(validated["cells"]) == 5
    assert deliverable["status"] == (
        "structured_workpaper_and_report_preview_compiled"
    )
    assert deliverable["rendering_authority"][
        "harness_generated_research_conclusion"
    ] is False
    demand = deliverable["cells"][0]
    assert demand["thesis_atom"] == fake["cells"][0]["thesis_atom"]
    operating = deliverable["cells"][1]
    assert any(
        row["metric_id"] == "revenue"
        and row["value_decimal"] == "43842000000"
        and row["unit"] == "USD"
        for row in operating["numeric_facts"]
    )
    assert any(
        row["evidence"]["source_type"] == "EARNINGS_CALL_TRANSCRIPT"
        for cell in deliverable["cells"]
        for row in cell["evidence_uses_rendered"]
        if row["use_role"] == "support"
    )


def test_v1_1_message_exposes_exact_enums_and_cell_local_views(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    messages = compile_current_research_messages(research_input)
    visible = json.loads(messages[1]["content"])
    contract = visible["output_contract"]

    assert len(messages[1]["content"]) == 72862
    assert len(messages[1]["content"]) <= 80000
    assert contract["allowed_judgment_statuses"] == [
        "supported",
        "bounded_support",
        "mixed",
        "insufficient_evidence",
    ]
    assert contract["allowed_evidence_use_roles"] == [
        "support",
        "limit",
        "context",
    ]
    assert contract["allowed_inference_authorities"] == [
        "directly_supported",
        "bounded_inference",
        "not_inferable",
    ]
    assert len(visible["evidence_fact_catalog"]) == 19
    assert len(visible["numeric_fact_catalog"]) == 25
    assert len(visible["numeric_relation_catalog"]) == 10
    assert any(row["role_method_pack"] for row in visible["cells"])
    assert all("cell_evidence_views" in row for row in visible["cells"])
    assert all("evidence_cards" not in row for row in visible["cells"])
    assert "research_input_digest" not in messages[1]["content"]


def test_v1_1_single_cell_scope_keeps_only_cell_local_catalogs(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    cell_id = "CELL::demand_quality"
    messages = compile_current_research_messages(
        research_input,
        required_cell_ids=[cell_id],
    )
    visible = json.loads(messages[1]["content"])
    allowed = next(
        row for row in research_input["cells"] if row["cell_id"] == cell_id
    )

    assert visible["output_contract"]["required_cell_ids"] == [cell_id]
    assert [row["cell_id"] for row in visible["cells"]] == [cell_id]
    assert {row["evidence_ref"] for row in visible["evidence_fact_catalog"]} == set(
        allowed["allowed_evidence_refs"]
    )
    assert visible["numeric_fact_catalog"] == []
    assert len(messages[1]["content"]) < 18000

    fake = _json(FAKE_PAYLOAD_V1_2)
    one_cell = {
        "cells": [row for row in fake["cells"] if row["cell_id"] == cell_id]
    }
    deliverable = compile_current_research_deliverable(
        research_input=research_input,
        judgment_output=one_cell,
        required_cell_ids=[cell_id],
    )
    assert [row["cell_id"] for row in deliverable["cells"]] == [cell_id]

    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_required_cell_scope_invalid",
    ):
        compile_current_research_messages(
            research_input,
            required_cell_ids=["CELL::not_current_case"],
        )


def test_v1_1_json_and_final_tool_views_share_business_payload(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    cell_id = "CELL::value_capture"
    json_view = json.loads(
        compile_current_research_messages(
            research_input,
            required_cell_ids=[cell_id],
            submission_transport="json",
        )[1]["content"]
    )
    tool_view = json.loads(
        compile_current_research_messages(
            research_input,
            required_cell_ids=[cell_id],
            submission_transport="final_tool",
        )[1]["content"]
    )

    assert "submission_transport" not in json_view["output_contract"]
    assert (
        tool_view["output_contract"]["submission_transport"]
        == "final_tool"
    )
    contracts = []
    for view in (json_view, tool_view):
        contract = dict(view.pop("output_contract"))
        contract.pop("submission_transport", None)
        shape = dict(contract.pop("payload_shape"))
        cell_shape = dict(
            shape["cells"][0]
            if "cells" in shape
            else shape["submit_research_judgment_arguments"]
        )
        wwc = dict(cell_shape["what_would_change"])
        wwc["threshold_numeric_ref"] = "transport-specific-empty-value"
        cell_shape["what_would_change"] = wwc
        contract["normalized_cell_payload_shape"] = cell_shape
        contracts.append(contract)
        view["rules"][0] = "transport-specific-final-submission"
    assert json_view == tool_view
    assert contracts[0] == contracts[1]

    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_submission_transport_invalid",
    ):
        compile_current_research_messages(
            research_input,
            required_cell_ids=[cell_id],
            submission_transport="unsupported",
        )


def test_v1_1_payload_injects_trusted_envelope_and_renders_typed_uses(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    payload = _json(FAKE_PAYLOAD_V1_2)
    parsed = parse_current_research_output(json.dumps(payload))
    validated = validate_current_research_output(
        parsed, research_input=research_input
    )
    deliverable = compile_current_research_deliverable(
        research_input=research_input,
        judgment_output=payload,
    )

    assert validated["research_input_digest"] == research_input[
        "research_input_digest"
    ]
    assert validated["schema_version"].endswith("payload_v1_2")
    assert deliverable["rendering_authority"][
        "harness_generated_research_conclusion"
    ] is False
    assert deliverable["schema_version"].endswith("deliverable_v1_2")
    demand = deliverable["cells"][0]
    assert [row["use_role"] for row in demand["evidence_uses"]] == [
        "support",
        "support",
        "limit",
    ]
    assert all("evidence" in row for row in demand["evidence_uses_rendered"])
    assert demand["remaining_gap_refs"] == ["GAP::00730082A5C08C4C"]


def test_one_evidence_may_support_a_fact_and_limit_a_broader_inference(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    payload = deepcopy(_json(FAKE_PAYLOAD_V1_2))
    payload["cells"][0]["evidence_uses"].append(
        {"evidence_ref": "EV::734A9C177164E08E", "use_role": "limit"}
    )

    validated = validate_current_research_output(
        payload, research_input=research_input
    )

    roles = {
        (row["evidence_ref"], row["use_role"])
        for row in validated["cells"][0]["evidence_uses"]
    }
    assert ("EV::734A9C177164E08E", "support") in roles
    assert ("EV::734A9C177164E08E", "limit") in roles


@pytest.mark.parametrize(
    "route",
    [
        "官方业绩稿或 10-Q 的毛利与收入，按既有公式生成同口径关系",
        "后续 10-K 与 8-K 的已审财务表和公司说明",
        "发行人 20-F、40-F 或 6-K 中的同口径官方披露",
    ],
)
def test_wwc_route_accepts_only_qualified_document_identifiers(
    route: str,
) -> None:
    assert validate_current_research_evidence_route(
        route,
        maximum=180,
    ) == route


@pytest.mark.parametrize(
    "route",
    [
        "官方 10-Q 显示毛利率增长 20% 后再作判断",
        "官方 10-Q 在 2027 年的下一期披露",
        "官方 12-Z 的毛利与收入披露",
        "https://example.com/10-Q 中的毛利与收入",
    ],
)
def test_wwc_route_rejects_unregistered_or_financial_numeric_surface(
    route: str,
) -> None:
    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_wwc_evidence_route_invalid",
    ):
        validate_current_research_evidence_route(route, maximum=180)


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda value: value["cells"][0]["evidence_uses"].append(
                {"evidence_ref": "EV::734A9C177164E08E", "use_role": "support"}
            ),
            "research_consumer_evidence_use_invalid",
        ),
        (
            lambda value: value["cells"][0].__setitem__(
                "judgment_status", "supported_with_caveats"
            ),
            "research_consumer_output_enum_invalid",
        ),
        (
            lambda value: value["cells"][0].__setitem__(
                "inference_authority", "issuer_plus_ecosystem"
            ),
            "research_consumer_output_enum_invalid",
        ),
        (
            lambda value: value["cells"][0]["evidence_uses"].append(
                {"evidence_ref": "EV::7F4D7E6762C21D83", "use_role": "context"}
            ),
            "research_consumer_evidence_use_invalid",
        ),
        (
            lambda value: value["cells"][2].__setitem__(
                "remaining_gap_refs", []
            ),
            "research_consumer_output_cell_fields_invalid",
        ),
        (
            lambda value: value["cells"][3].__setitem__(
                "thesis_atom", "现金流增长两位数，人工智能订单已经完全转化为现金。"
            ),
            "research_consumer_thesis_atom_invalid",
        ),
    ],
)
def test_v1_1_mutations_fail_closed(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
    mutator,
    code: str,
) -> None:
    _, _, research_input = current_inputs
    payload = deepcopy(_json(FAKE_PAYLOAD_V1_2))
    mutator(payload)

    with pytest.raises(CurrentResearchConsumerError, match=code):
        compile_current_research_deliverable(
            research_input=research_input,
            judgment_output=payload,
        )


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda value: (
                value["cells"][2].__setitem__("numeric_relation_refs", []),
                value["cells"][2].__setitem__(
                    "thesis_atom", "利润率同比变化可见，但产品级利润桥仍然缺失。"
                ),
            ),
            "research_consumer_year_over_year_without_same_basis_relation",
        ),
        (
            lambda value: value["cells"][2].__setitem__(
                "numeric_refs",
                value["cells"][2]["numeric_refs"][1:],
            ),
            "research_consumer_numeric_relation_boundary_invalid",
        ),
        (
            lambda value: value["cells"][2].__setitem__(
                "method_step_refs",
                value["cells"][2]["method_step_refs"][:3],
            ),
            "research_consumer_method_consumption_invalid",
        ),
        (
            lambda value: value["cells"][2].__setitem__(
                "graph_edge_refs", ["GRAPH::CROSS_CASE_CONTAMINATION"]
            ),
            "research_consumer_graph_consumption_invalid",
        ),
    ],
)
def test_v1_2_context_and_same_basis_mutations_fail_closed(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
    mutator,
    code: str,
) -> None:
    _, _, research_input = current_inputs
    payload = deepcopy(_json(FAKE_PAYLOAD_V1_2))
    mutator(payload)

    with pytest.raises(CurrentResearchConsumerError, match=code):
        compile_current_research_deliverable(
            research_input=research_input,
            judgment_output=payload,
        )


def test_immutable_r1_response_is_not_silently_promoted_to_v1_1(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    raw = _json(R1_FAILED_PAYLOAD)

    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_output_cell_fields_invalid",
    ):
        validate_current_research_output(raw, research_input=research_input)

    assert {
        row["judgment_status"] for row in raw["cells"]
    } == {"supported_with_caveats"}
    assert {
        row["confidence_basis"] for row in raw["cells"]
    } == {"issuer_disclosure_plus_ecosystem_readthrough"}
    assert any(
        set(row["supporting_evidence_refs"])
        & set(row["counterevidence_refs"])
        for row in raw["cells"]
    )


def test_v1_1_capacity_fails_closed_without_raising_the_policy_limit(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    changed = deepcopy(research_input)
    changed["model_input_contract"]["maximum_user_message_chars"] = 45000

    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_model_input_capacity_exceeded",
    ):
        compile_current_research_messages(changed)


def test_v1_1_policy_contract_drift_fails_closed() -> None:
    policy = _json(POLICY)
    policy["model_output_contract"]["allowed_evidence_use_roles"] = [
        "support",
        "counter",
        "context",
    ]

    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_model_output_policy_invalid",
    ):
        load_current_research_consumer_policy(policy)


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda pack, _: pack["evidence_items"][0].__setitem__(
                "case_key", "MU"
            ),
            "research_consumer_evidence_boundary_invalid",
        ),
        (
            lambda pack, _: pack["evidence_items"][-1]["source"].__setitem__(
                "source_tier", "unknown_transcript_tier"
            ),
            "research_consumer_reviewed_source_not_allowed",
        ),
        (
            lambda pack, _: pack["evidence_items"][0].__setitem__(
                "publication_date", "2027-01-01"
            ),
            "research_consumer_evidence_temporal_boundary_invalid",
        ),
        (
            lambda pack, _: pack["rejected_items"].append(
                {"writer_citable": True}
            ),
            "research_consumer_rejected_item_boundary_invalid",
        ),
        (
            lambda _, controlled: controlled["request_results"][2][
                "typed_fact_results"
            ][0]["facts"][0].__setitem__("numeric_fact_authority", False),
            "research_consumer_numeric_fact_boundary_invalid",
        ),
    ],
)
def test_input_mutations_fail_closed(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
    mutator,
    code: str,
) -> None:
    evidence_pack, controlled, _ = current_inputs
    changed_pack = deepcopy(evidence_pack)
    changed_controlled = deepcopy(controlled)
    mutator(changed_pack, changed_controlled)

    with pytest.raises(CurrentResearchConsumerError, match=code):
        compile_current_research_input(
            policy=_json(POLICY),
            evidence_pack=changed_pack,
            controlled_plan=changed_controlled,
        )


def test_parser_requires_exact_json() -> None:
    fake = _json(FAKE_PAYLOAD_V1_2)
    assert parse_current_research_output(json.dumps(fake))["cells"]
    with pytest.raises(CurrentResearchConsumerError, match="not_exact_json"):
        parse_current_research_output("```json\n{}\n```")
    with pytest.raises(CurrentResearchConsumerError, match="json_invalid"):
        parse_current_research_output("not-json")


@pytest.mark.parametrize(
    "text",
    [
        "公司需求存在支撑但利润转化仍需直接证据验证",
        "Demand is supported while the profit bridge remains unproven",
    ],
)
def test_model_text_server_pattern_accepts_valid_financial_prose(
    text: str,
) -> None:
    assert re.fullmatch(CURRENT_RESEARCH_MODEL_TEXT_SERVER_PATTERN, text)
    assert (
        validate_current_research_model_text(
            text,
            maximum=200,
            code="test_model_text_invalid",
        )
        == text
    )


@pytest.mark.parametrize(
    "text",
    [
        "The conclusion follows from the 10-Q filing",
        "The FY27 Q1 result supports the conclusion",
        "The 8-K filing supports the conclusion",
        "Margin improved by 20% according to the filing",
        "Revenue reached $ amount while profit lagged",
        "Revenue stated in USD supports the conclusion",
        "Verify the conclusion at https://example.com/source",
        "The selected NUM::DELL::REVENUE ref supports the conclusion",
        "利润改善处于中个位数区间但归因仍不明确",
        "利润改善处于两位数区间但归因仍不明确",
        "利润改善约三十个基点但归因仍不明确",
    ],
)
def test_model_text_server_pattern_and_local_validator_reject_same_surfaces(
    text: str,
) -> None:
    assert re.fullmatch(CURRENT_RESEARCH_MODEL_TEXT_SERVER_PATTERN, text) is None
    with pytest.raises(CurrentResearchConsumerError, match="test_model_text_invalid"):
        validate_current_research_model_text(
            text,
            maximum=200,
            code="test_model_text_invalid",
        )


def test_model_text_schema_uses_one_shared_server_predicate() -> None:
    field = compile_current_research_model_text_schema(
        description="Model-owned financial judgment atom."
    )
    schema = bind_current_research_model_text_schema_definition(
        {
            "type": "object",
            "properties": {"thesis_atom": field},
            "required": ["thesis_atom"],
            "additionalProperties": False,
        }
    )

    assert field == {
        "$ref": "#/$defs/t",
        "description": "Model-owned financial judgment atom.",
    }
    assert schema["$defs"] == {
        "t": {
            "type": "string",
            "pattern": CURRENT_RESEARCH_MODEL_TEXT_SERVER_PATTERN,
        }
    }


def test_clean_reproof_authority_binds_head_upstream_and_only_itself_untracked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _zero_call_runner()
    commit = "a" * 40
    authority_path = ROOT / (
        "configs/research/evals/"
        "fin_ia_0_1_3_s3_dell_current_research_consumer_"
        "zero_call_authority_v1_2.json"
    )
    binding = {
        "implementation_commit": commit,
        "head_must_equal_implementation_commit": True,
        "upstream_must_equal_implementation_commit": True,
        "tracked_worktree_must_be_clean": True,
        "only_authority_may_be_untracked": True,
    }

    def clean_git(*args: str) -> str:
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return f"?? {authority_path.relative_to(ROOT).as_posix()}"
        return commit

    monkeypatch.setattr(runner, "_git", clean_git)
    runner._validate_clean_implementation(
        {"clean_implementation": binding},
        authority_path=authority_path,
    )

    monkeypatch.setattr(
        runner,
        "_git",
        lambda *args: (
            f"?? {authority_path.relative_to(ROOT).as_posix()}\n"
            " M src/sec_agent/research/current_consumer.py"
            if args == ("status", "--porcelain=v1", "--untracked-files=all")
            else commit
        ),
    )
    with pytest.raises(
        runner.CurrentResearchConsumerRunnerError,
        match="current_consumer_implementation_worktree_not_clean",
    ):
        runner._validate_clean_implementation(
            {"clean_implementation": binding},
            authority_path=authority_path,
        )


def test_v1_1_runner_binds_content_audit_to_immutable_failed_payload(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    runner = _zero_call_runner()
    _, _, research_input = current_inputs
    replay = runner._replay_failed_r1(
        research_input=research_input,
        payload=_json(R1_FAILED_PAYLOAD),
        audit=_json(
            ROOT
            / "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_current_research_consumer_"
            "canary_r1_content_audit_v1_0.json"
        ),
    )

    assert replay["automatic_salvage_or_publication"] is False
    assert replay["v1_1_rejection_code"] == (
        "research_consumer_output_cell_fields_invalid"
    )
    assert replay["qualified_content_audit_finding_codes"] == [
        "ai_to_group_and_segment_profit_attribution_unproven",
        "ai_working_capital_attribution_unproven",
        "demand_durability_overreach",
        "supply_easing_unproven",
        "unbound_comparative_margin_and_leverage_claim",
    ]


@pytest.fixture(scope="module")
def five_cell_context_input(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> dict[str, object]:
    evidence_pack, controlled, _ = current_inputs
    return compile_current_research_input(
        policy=_json(FIVE_CELL_POLICY),
        evidence_pack=evidence_pack,
        controlled_plan=controlled,
    )


def _value_capture_capacity_fixture() -> tuple[
    list[dict[str, object]], list[dict[str, object]]
]:
    cards: list[dict[str, object]] = []
    relations: list[dict[str, object]] = []
    for metric_id in (
        "revenue",
        "gross_profit",
        "gross_margin",
        "operating_income",
        "operating_margin",
    ):
        current_ref = f"NUM::{metric_id.upper()}::CURRENT"
        prior_ref = f"NUM::{metric_id.upper()}::PRIOR"
        cards.extend(
            [
                {
                    "numeric_ref": current_ref,
                    "ticker": "DELL",
                    "metric_id": metric_id,
                },
                {
                    "numeric_ref": prior_ref,
                    "ticker": "DELL",
                    "metric_id": metric_id,
                },
            ]
        )
        relations.append(
            {
                "current_numeric_ref": current_ref,
                "comparison_numeric_ref": prior_ref,
            }
        )
    return cards, relations


def test_five_cell_policy_successor_derives_value_capacity_from_atomic_bundle(
) -> None:
    policy = load_current_research_consumer_policy(
        _json(FIVE_CELL_POLICY_SUCCESSOR)
    )
    contract = next(
        row
        for row in policy["cell_contracts"]
        if row["cell_id"] == "CELL::value_capture"
    )
    capacity = contract["numeric_capacity_contract"]
    assert contract["maximum_numeric_facts"] == 10
    assert len(capacity["allowed_metric_ids"]) == 5
    assert capacity["maximum_periods_per_metric"] == 2
    assert capacity["same_cadence_pair_atomic"] is True

    weakened = _json(FIVE_CELL_POLICY_SUCCESSOR)
    next(
        row
        for row in weakened["cell_contracts"]
        if row["cell_id"] == "CELL::value_capture"
    )["maximum_numeric_facts"] = 9
    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_numeric_capacity_contract_invalid",
    ):
        load_current_research_consumer_policy(weakened)


def test_value_capture_atomic_ten_is_order_stable_and_plus_one_fails_closed(
) -> None:
    policy = load_current_research_consumer_policy(
        _json(FIVE_CELL_POLICY_SUCCESSOR)
    )
    contract = next(
        row
        for row in policy["cell_contracts"]
        if row["cell_id"] == "CELL::value_capture"
    )
    cards, relations = _value_capture_capacity_fixture()
    current_consumer._enforce_cell_numeric_capacity(
        cards=cards,
        relation_cards=relations,
        contract=contract,
        case_key="DELL",
    )
    current_consumer._enforce_cell_numeric_capacity(
        cards=list(reversed(cards)),
        relation_cards=list(reversed(relations)),
        contract=contract,
        case_key="DELL",
    )

    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_cell_capacity_exceeded",
    ):
        current_consumer._enforce_cell_numeric_capacity(
            cards=cards
            + [
                {
                    "numeric_ref": "NUM::NET_INCOME::CURRENT",
                    "ticker": "DELL",
                    "metric_id": "net_income",
                }
            ],
            relation_cards=relations,
            contract=contract,
            case_key="DELL",
        )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("duplicate", "research_consumer_numeric_capacity_duplicate_invalid"),
        ("cross_case", "research_consumer_numeric_capacity_ticker_invalid"),
        (
            "missing_pair_relation",
            "research_consumer_numeric_capacity_comparable_pair_invalid",
        ),
    ],
)
def test_value_capture_atomic_bundle_mutations_fail_closed(
    mutation: str, expected_code: str
) -> None:
    policy = load_current_research_consumer_policy(
        _json(FIVE_CELL_POLICY_SUCCESSOR)
    )
    contract = next(
        row
        for row in policy["cell_contracts"]
        if row["cell_id"] == "CELL::value_capture"
    )
    cards, relations = _value_capture_capacity_fixture()
    if mutation == "duplicate":
        cards[-1] = dict(cards[0])
    elif mutation == "cross_case":
        cards[0] = {**cards[0], "ticker": "MU"}
    else:
        relations = relations[1:]
    with pytest.raises(CurrentResearchConsumerError, match=expected_code):
        current_consumer._enforce_cell_numeric_capacity(
            cards=cards,
            relation_cards=relations,
            contract=contract,
            case_key="DELL",
        )


def test_five_cell_context_successor_preserves_v1_2_and_binds_one_method_pack_per_cell(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
    five_cell_context_input: dict[str, object],
) -> None:
    _, _, historical_input = current_inputs
    assert historical_input["research_input_digest"] != five_cell_context_input[
        "research_input_digest"
    ]
    assert sum(
        bool(row.get("role_method_pack")) for row in historical_input["cells"]
    ) == 1

    expected = {
        "CELL::demand_quality": "ROLE_METHOD::DEMAND_QUALITY::V1",
        "CELL::operating_performance": "ROLE_METHOD::OPERATING_PERFORMANCE::V1",
        "CELL::value_capture": "ROLE_METHOD::VALUE_CAPTURE::V1",
        "CELL::cash_conversion": "ROLE_METHOD::CASH_CONVERSION::V1",
        "CELL::counterevidence": "ROLE_METHOD::COUNTEREVIDENCE::V1",
    }
    assert {
        row["cell_id"]: row["role_method_pack"]["pack_id"]
        for row in five_cell_context_input["cells"]
    } == expected
    assert all(
        row["role_method_pack"]["cell_id"] == row["cell_id"]
        and row["context_consumption_contract"]["minimum_method_step_refs"] == 4
        for row in five_cell_context_input["cells"]
    )

    serialized = json.dumps(
        [row["role_method_pack"] for row in five_cell_context_input["cells"]],
        ensure_ascii=False,
    )
    for case_specific_name in (
        "Dell Technologies",
        "Micron Technology",
        "NVIDIA Corporation",
    ):
        assert case_specific_name not in serialized


def test_five_cell_context_is_cell_local_current_and_capacity_bounded(
    five_cell_context_input: dict[str, object],
) -> None:
    full_messages = compile_current_research_messages(five_cell_context_input)
    assert len(full_messages[1]["content"]) <= five_cell_context_input[
        "model_input_contract"
    ]["maximum_user_message_chars"]

    evidence_by_ref = {
        row["evidence_ref"]: row
        for row in five_cell_context_input["evidence_cards"]
    }
    for cell in five_cell_context_input["cells"]:
        local = json.loads(
            compile_current_research_messages(
                five_cell_context_input,
                required_cell_ids=[cell["cell_id"]],
            )[1]["content"]
        )
        assert [row["cell_id"] for row in local["cells"]] == [cell["cell_id"]]
        assert local["cells"][0]["role_method_pack"]["pack_id"] == cell[
            "role_method_pack"
        ]["pack_id"]
        assert [
            row["cell_id"]
            for row in local["research_context_injection_receipt"]["selection"]
        ] == [cell["cell_id"]]

        graph = cell["graph_context_pack"]
        assert graph["case_key"] == "DELL"
        assert graph["authority"] == {
            "compiled_from_current_case_reviewed_evidence_and_numeric_facts": True,
            "archived_graph_rows_used": False,
            "scope_or_context_edge_grants_fact_authority": False,
        }
        assert all(
            set(edge["evidence_refs"]).issubset(cell["allowed_evidence_refs"])
            and edge["grants_company_fact_or_causality"] is False
            for edge in graph["edges"]
        )
        expected_entities = {"DELL"} | {
            str(evidence_by_ref[ref]["evidence_owner_ticker"]).upper()
            for ref in cell["allowed_evidence_refs"]
        }
        assert {row["entity_id"] for row in graph["nodes"]}.issubset(
            expected_entities
        )


def test_five_cell_fake_judgment_consumes_all_methods_without_harness_authorship(
    five_cell_context_input: dict[str, object],
) -> None:
    payload = _json(FIVE_CELL_FAKE_PAYLOAD)
    validated = validate_current_research_output(
        payload,
        research_input=five_cell_context_input,
    )
    deliverable = compile_current_research_deliverable(
        research_input=five_cell_context_input,
        judgment_output=payload,
    )

    assert len(validated["cells"]) == 5
    assert all(
        len(row["context_consumption_receipt"]["consumed_method_step_refs"]) >= 4
        for row in validated["cells"]
    )
    assert deliverable["rendering_authority"][
        "harness_generated_research_conclusion"
    ] is False


@pytest.mark.parametrize(
    "cell_id",
    [
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    ],
)
def test_five_cell_method_consumption_mutations_fail_closed(
    five_cell_context_input: dict[str, object],
    cell_id: str,
) -> None:
    payload = deepcopy(_json(FIVE_CELL_FAKE_PAYLOAD))
    cell = next(row for row in payload["cells"] if row["cell_id"] == cell_id)
    cell["method_step_refs"] = cell["method_step_refs"][:3]
    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_method_consumption_invalid",
    ):
        validate_current_research_output(
            payload,
            research_input=five_cell_context_input,
        )

    payload = deepcopy(_json(FIVE_CELL_FAKE_PAYLOAD))
    cell = next(row for row in payload["cells"] if row["cell_id"] == cell_id)
    cell["method_step_refs"][0] = "METHOD::OTHER_CELL::BORROWED"
    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_method_consumption_invalid",
    ):
        validate_current_research_output(
            payload,
            research_input=five_cell_context_input,
        )


def test_five_cell_cross_case_graph_reference_fails_closed(
    five_cell_context_input: dict[str, object],
) -> None:
    payload = deepcopy(_json(FIVE_CELL_FAKE_PAYLOAD))
    payload["cells"][0]["graph_edge_refs"] = ["GRAPH::MU::BORROWED"]
    with pytest.raises(
        CurrentResearchConsumerError,
        match="research_consumer_graph_consumption_invalid",
    ):
        validate_current_research_output(
            payload,
            research_input=five_cell_context_input,
        )


def test_five_cell_context_runs_through_one_bounded_loop_without_fixed_nine_calls(
    five_cell_context_input: dict[str, object],
) -> None:
    runner = _bounded_zero_call_runner()
    kernel, route, planning, _, _ = runner._runtime_components()
    loop_policy = runner.load_bounded_finance_loop_policy(
        _json(
            ROOT
            / "configs/research/"
            "fin_ia_0_1_3_s3_bounded_finance_agent_loop_policy_v1_1.json"
        )
    )
    matrix = runner._run_fake_matrix(
        research_input=five_cell_context_input,
        kernel=kernel,
        route=route,
        planning=planning,
        policy=loop_policy,
        fake=_json(FIVE_CELL_FAKE_PAYLOAD),
    )

    assert matrix["single_cell"]["status"] == "completed_all_required_cells"
    assert matrix["single_cell"]["step_count"] == 3
    assert matrix["single_cell"]["tool_call_count"] == 4
    assert matrix["five_cell"]["status"] == "completed_all_required_cells"
    assert matrix["five_cell"]["step_count"] == 10
    assert matrix["five_cell"]["tool_call_count"] == 15


def test_five_cell_zero_call_runner_covers_method_and_graph_pollution(
    five_cell_context_input: dict[str, object],
) -> None:
    runner = _zero_call_runner()
    codes = runner._mutation_codes(
        research_input=five_cell_context_input,
        fake=_json(FIVE_CELL_FAKE_PAYLOAD),
    )
    assert codes[-2:] == [
        "research_consumer_method_consumption_invalid",
        "research_consumer_graph_consumption_invalid",
    ]
