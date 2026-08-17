from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from retrieval.contracts import load_evidence_request, load_financial_research_kernel
from retrieval.query_plan import compile_query_facet_plan_for_request
from retrieval.retrieval_need import RetrievalNeedError, compile_retrieval_needs


ROOT = Path(__file__).resolve().parents[1]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _first_atom() -> tuple[object, object, object, dict]:
    kernel = load_financial_research_kernel(
        _json("configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_1.json")
    )
    atom = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_vs3_runtime_query_atom_eval_v1_2.json"
    )["atoms"][1]
    request = load_evidence_request(atom["request"], kernel)
    lane = compile_query_facet_plan_for_request(kernel, request).lanes[0]
    policy = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_vs3_retrieval_need_compiler_policy_v1_0.json"
    )
    return kernel, request, lane, policy


def test_retrieval_need_splits_metric_and_product_without_changing_constraints() -> None:
    _, request, lane, policy = _first_atom()
    result = compile_retrieval_needs(request=request, lane=lane, policy=policy)

    assert len(result.needs) <= policy["maximum_needs_per_lane"]
    assert any(row.need_kind == "metric_product" for row in result.needs)
    assert any(row.intent_terms == ("revenue",) for row in result.needs)
    assert any(row.intent_terms == ("operating income",) for row in result.needs)
    assert {row.evidence_owner_ticker for row in result.needs} == {"DELL"}
    assert {row.relationship_direction for row in result.needs} == {
        "subject_self_disclosure"
    }
    assert len({row.constraint_digest for row in result.needs}) == 1
    assert all("COBJ::" not in row.lexical_query for row in result.needs)


def test_retrieval_need_is_deterministic_under_label_mutation() -> None:
    _, request, lane, policy = _first_atom()
    first = compile_retrieval_needs(request=request, lane=lane, policy=policy)
    second = compile_retrieval_needs(request=request, lane=lane, policy=policy)
    assert first.as_dict() == second.as_dict()


def test_retrieval_need_rejects_gold_or_url_leakage() -> None:
    _, request, lane, policy = _first_atom()
    mutated = replace(request, product_intents=("https://example.com/gold",))
    with pytest.raises(RetrievalNeedError, match="gold_or_url_leakage"):
        compile_retrieval_needs(
            request=mutated,
            lane=lane,
            policy=policy,
        )


def test_retrieval_need_v11_adds_typed_alias_groups_and_removes_proxy_cues() -> None:
    _, request, lane, _ = _first_atom()
    policy = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_vs3_retrieval_need_compiler_policy_v1_1.json"
    )
    ontology = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_0.json"
    )
    result = compile_retrieval_needs(
        request=request,
        lane=lane,
        policy=policy,
        intent_ontology=ontology,
    )

    combined = next(row for row in result.needs if row.need_kind == "metric_product")
    assert "AI server" in combined.intent_alias_groups[1]
    assert all("gross margin" not in row.role_cues for row in result.needs)


def test_retrieval_need_v11_cash_metric_aliases_exclude_free_cash_flow_cue() -> None:
    kernel = load_financial_research_kernel(
        _json("configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_3.json")
    )
    atom = next(
        row
        for row in _json(
            "configs/retrieval/fin_ia_0_1_3_s1_vs3_runtime_query_atom_eval_v1_4.json"
        )["atoms"]
        if row["atom_id"] == "S1C_ATOM_16_NVDA_CASH_GENERATION"
    )
    request = load_evidence_request(atom["request"], kernel)
    lane = compile_query_facet_plan_for_request(kernel, request).lanes[0]
    policy = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_vs3_retrieval_need_compiler_policy_v1_1.json"
    )
    ontology = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_0.json"
    )
    result = compile_retrieval_needs(
        request=request,
        lane=lane,
        policy=policy,
        intent_ontology=ontology,
    )
    metric = next(row for row in result.needs if row.need_kind == "metric")
    assert "net cash provided by operating activities" in metric.intent_alias_groups[0]
    assert "free cash flow" not in metric.role_cues
