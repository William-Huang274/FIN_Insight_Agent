from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.authoritative_relationship_graph_program import (
    AuthoritativeRelationshipGraphError,
    canonical_digest,
    compile_authoritative_relationship_graph_program,
    load_authoritative_relationship_graph_policy,
    validate_authoritative_relationship_graph_program,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = (
    REPO_ROOT
    / "configs/runtime/fin_ia_0_1_3_repair_closeout_authoritative_relationship_graph_policy_v1_0.json"
)
DECISION_PATH = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_04_authoritative_relationship_graph_and_typed_empty_v1_0.json"
)
ACTIVE_PATH = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_04_active_test_suite_successor_v1_0.json"
)


def _policy() -> dict:
    return load_authoritative_relationship_graph_policy(POLICY_PATH)


def _official_program(policy: dict) -> dict:
    cases = []
    for case_key, profile in sorted(policy["case_profiles"].items()):
        route_id = profile["source_route_id"]
        cases.append(
            {
                "case_key": case_key,
                "route_results": [
                    {
                        "route_id": route_id,
                        "status": "captured",
                        "response_capture": {
                            "object_key": f"capture/{case_key}.json",
                            "digest": f"capture_digest_{case_key}",
                        },
                        "parser": {
                            "status": "parsed",
                            "adapter": "fixture_text_v1",
                            "text_sha256": f"text_digest_{case_key}",
                        },
                    }
                ],
            }
        )
    return {
        "program_digest": "official_fixture_program_digest",
        "case_results": cases,
    }


def _documents(policy: dict) -> dict[str, dict]:
    text = {
        "DELL": "Dell disclosed relationships with unnamed customers and suppliers only.",
        "MU": (
            "We face intense competition in the semiconductor memory and storage markets "
            "from a number of companies, including Samsung Electronics Co., Ltd.; SK hynix Inc."
        ),
        "NVDA": (
            "Announced a multiyear, multigenerational strategic partnership with Meta spanning "
            "on-premises, cloud and AI infrastructure, including the large-scale deployment of "
            "NVIDIA CPUs, networking and millions of NVIDIA Blackwell and Rubin GPUs. "
            "cloud providers Amazon Web Services (AWS), Google Cloud, Microsoft Azure and Oracle "
            "Cloud Infrastructure will be among the first to deploy Vera Rubin-based instances."
        ),
    }
    result = {}
    for case_key, profile in policy["case_profiles"].items():
        result[case_key] = {
            "route_id": profile["source_route_id"],
            "source_url": f"https://official.example/{case_key}",
            "source_capture_ref": f"capture/{case_key}.json",
            "source_capture_digest": f"capture_digest_{case_key}",
            "parser_adapter": "fixture_text_v1",
            "parser_text_digest": f"text_digest_{case_key}",
            "text": text[case_key],
        }
    return result


def _dates() -> dict[str, dict[str, str]]:
    return {
        "DELL": {
            "published_at": "2026-03-16",
            "authority_ref": "dell_annual",
            "authority_digest": "dell_annual_digest",
        },
        "MU": {
            "published_at": "2025-10-03",
            "authority_ref": "mu_annual",
            "authority_digest": "mu_annual_digest",
        },
        "NVDA": {
            "published_at": "2026-02-25",
            "authority_ref": "nvda_annual",
            "authority_digest": "nvda_annual_digest",
        },
    }


def _compile() -> tuple[dict, dict, dict]:
    policy = _policy()
    official = _official_program(policy)
    program = compile_authoritative_relationship_graph_program(
        policy=policy,
        official_source_program=official,
        parsed_source_documents=_documents(policy),
        date_authorities=_dates(),
    )
    return program, policy, official


def _reseal(program: dict) -> None:
    for graph in program["case_graphs"]:
        for edge in graph["edges"]:
            body = {
                key: value
                for key, value in edge.items()
                if key not in {"edge_id", "edge_digest"}
            }
            edge["edge_digest"] = canonical_digest(body)
            edge["edge_id"] = f"fin013_graph_edge_{edge['edge_digest'][:24]}"
        graph_body = {
            key: value for key, value in graph.items() if key != "case_graph_digest"
        }
        graph["case_graph_digest"] = canonical_digest(graph_body)
    body = {key: value for key, value in program.items() if key != "program_digest"}
    program["program_digest"] = canonical_digest(body)


def test_current_graph_compiles_seven_authoritative_edges_and_one_honest_empty() -> None:
    program, policy, official = _compile()
    validate_authoritative_relationship_graph_program(
        program,
        policy=policy,
        official_source_program=official,
        date_authorities=_dates(),
    )
    assert program["observed_counts"] == {
        "cases": 3,
        "approved_edges": 7,
        "typed_empty_cases": 1,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "business_runs": 0,
    }
    graphs = {row["case_key"]: row for row in program["case_graphs"]}
    assert graphs["DELL"]["status"] == (
        "typed_empty_no_approved_current_relationship_evidence"
    )
    assert graphs["DELL"]["typed_empty"]["source_exhaustion_proven"] is False
    assert {row["edge_type"] for row in graphs["MU"]["edges"]} == {
        "competitive_landscape"
    }
    assert {row["edge_type"] for row in graphs["NVDA"]["edges"]} == {
        "strategic_partnership",
        "official_deployment_event",
    }
    assert all(row["financial_fact_authority"] is False for row in graphs["NVDA"]["edges"])


def test_cross_case_entity_and_false_empty_mutations_fail_closed() -> None:
    program, policy, official = _compile()
    crossed = deepcopy(program)
    mu = next(row for row in crossed["case_graphs"] if row["case_key"] == "MU")
    mu["edges"][0]["source_case_key"] = "NVDA"
    _reseal(crossed)
    with pytest.raises(AuthoritativeRelationshipGraphError, match="relationship_edge_invalid"):
        validate_authoritative_relationship_graph_program(
            crossed,
            policy=policy,
            official_source_program=official,
            date_authorities=_dates(),
        )

    false_empty = deepcopy(program)
    nvda = next(row for row in false_empty["case_graphs"] if row["case_key"] == "NVDA")
    nvda["edges"] = []
    nvda["approved_edge_count"] = 0
    nvda["status"] = "typed_empty_no_approved_current_relationship_evidence"
    nvda["typed_empty"] = {
        "case_key": "NVDA",
        "status": "typed_empty_no_approved_current_relationship_evidence",
        "reason": "mutated",
        "inspected_source_capture_digest": "capture_digest_NVDA",
        "source_exhaustion_proven": False,
        "invented_edge_count": 0,
    }
    empty_body = dict(nvda["typed_empty"])
    nvda["typed_empty"]["typed_empty_digest"] = canonical_digest(empty_body)
    false_empty["observed_counts"]["approved_edges"] = 2
    false_empty["observed_counts"]["typed_empty_cases"] = 2
    _reseal(false_empty)
    with pytest.raises(
        AuthoritativeRelationshipGraphError, match="relationship_case_rule_coverage_invalid"
    ):
        validate_authoritative_relationship_graph_program(
            false_empty,
            policy=policy,
            official_source_program=official,
            date_authorities=_dates(),
        )


def test_missing_or_future_date_and_capture_drift_fail_before_graph_promotion() -> None:
    policy = _policy()
    official = _official_program(policy)
    dates = _dates()
    dates["NVDA"]["published_at"] = "2026-08-01"
    with pytest.raises(
        AuthoritativeRelationshipGraphError, match="relationship_graph_date_authority_invalid"
    ):
        compile_authoritative_relationship_graph_program(
            policy=policy,
            official_source_program=official,
            parsed_source_documents=_documents(policy),
            date_authorities=dates,
        )

    documents = _documents(policy)
    documents["MU"]["source_capture_digest"] = "wrong_digest"
    with pytest.raises(
        AuthoritativeRelationshipGraphError, match="relationship_graph_source_binding_invalid"
    ):
        compile_authoritative_relationship_graph_program(
            policy=policy,
            official_source_program=official,
            parsed_source_documents=documents,
            date_authorities=_dates(),
        )


def test_wrong_target_registry_and_missing_required_statement_fail_closed() -> None:
    policy = _policy()
    official = _official_program(policy)
    wrong_target = deepcopy(policy)
    wrong_target["entity_registry"]["META"]["name"] = "Unrelated Entity"
    with pytest.raises(
        AuthoritativeRelationshipGraphError,
        match="relationship_graph_target_not_explicit_in_statement",
    ):
        compile_authoritative_relationship_graph_program(
            policy=wrong_target,
            official_source_program=official,
            parsed_source_documents=_documents(policy),
            date_authorities=_dates(),
        )

    missing = _documents(policy)
    missing["NVDA"]["text"] = "NVIDIA released financial results."
    with pytest.raises(
        AuthoritativeRelationshipGraphError,
        match="relationship_graph_required_rule_not_matched",
    ):
        compile_authoritative_relationship_graph_program(
            policy=policy,
            official_source_program=official,
            parsed_source_documents=missing,
            date_authorities=_dates(),
        )


def test_resealed_node_and_source_lineage_mutations_fail_closed() -> None:
    program, policy, official = _compile()
    node_mutation = deepcopy(program)
    nvda = next(row for row in node_mutation["case_graphs"] if row["case_key"] == "NVDA")
    nvda["nodes"][1]["ticker"] = "WRONG"
    _reseal(node_mutation)
    with pytest.raises(
        AuthoritativeRelationshipGraphError, match="relationship_case_nodes_invalid"
    ):
        validate_authoritative_relationship_graph_program(
            node_mutation,
            policy=policy,
            official_source_program=official,
            date_authorities=_dates(),
        )

    source_mutation = deepcopy(program)
    mu = next(row for row in source_mutation["case_graphs"] if row["case_key"] == "MU")
    mu["inspected_source"]["parser_adapter"] = "mutated_parser"
    for edge in mu["edges"]:
        edge["parser_adapter"] = "mutated_parser"
    _reseal(source_mutation)
    with pytest.raises(
        AuthoritativeRelationshipGraphError,
        match="relationship_case_source_binding_invalid",
    ):
        validate_authoritative_relationship_graph_program(
            source_mutation,
            policy=policy,
            official_source_program=official,
            date_authorities=_dates(),
        )


def test_materialized_release_and_active_suite_are_digest_bound() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    record_digest = decision.pop("record_digest")
    assert record_digest == canonical_digest(decision)
    graph = decision["graph_program"]
    assert graph["observed_counts"]["approved_edges"] == 7
    assert graph["observed_counts"]["typed_empty_cases"] == 1
    assert decision["stage_boundary"]["S1_05_retrieval_usefulness"] == "next_not_started"
    assert decision["stage_boundary"]["model_or_full_chain"] is False

    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    suite_digest = active.pop("suite_digest")
    assert suite_digest == canonical_digest(active)
    assert active["decision_sha256"] == hashlib.sha256(DECISION_PATH.read_bytes()).hexdigest()
    assert active["stage_boundary"]["S1_05"] == "next"
