from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import load_financial_research_kernel
from retrieval.query_atom_shadow import (
    QueryAtomShadowError,
    apply_query_atom_label_adjudications,
    aggregate_evidence_role_metrics,
    aggregate_query_atom_results,
    compile_atom_lane,
    evaluate_controlled_evidence_roles,
    evaluate_controlled_reranker,
    evaluate_query_atom,
    label_eligibility_rows,
    load_query_atoms,
)
from retrieval.route_compiler import load_query_object_fact_route_policy


def _runtime_contracts():
    kernel_payload = json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_1.json"
        ).read_text(encoding="utf-8")
    )
    kernel = load_financial_research_kernel(kernel_payload)
    policy = load_query_object_fact_route_policy(
        json.loads(
            (
                ROOT
                / "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_1.json"
            ).read_text(encoding="utf-8")
        ),
        kernel,
    )
    return kernel, policy


def _payload() -> dict:
    return {
        "schema_version": "fin_ia_s1c_runtime_query_atom_eval_v1_0",
        "policy": {
            "compile_request_before_label_join": True,
            "one_facet_and_one_owner_per_atom": True,
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
        },
        "atoms": [
            {
                "atom_id": "DELL_DOWNSTREAM_MSFT",
                "request": {
                    "schema_version": "fin_ia_evidence_request_v1_0",
                    "request_id": "REQ-DELL-DOWNSTREAM-MSFT",
                    "cell_id": "CELL-DELL-DOWNSTREAM-MSFT",
                    "requester_role": "research_lead",
                    "evidence_domain": "financial_research",
                    "case_key": "DELL",
                    "subject_ticker": "DELL",
                    "research_as_of": "2026-08-06",
                    "target_entities": ["MSFT"],
                    "requested_facet_ids": ["downstream_demand_context"],
                    "metric_intents": [],
                    "product_intents": ["AI infrastructure"],
                    "period": {
                        "start_date": None,
                        "end_date": "2026-08-06",
                        "fiscal_years": [2026],
                    },
                    "granularity": "quarter_and_fiscal_year",
                    "unit": "reported_source_unit",
                    "acceptable_sources": ["10-Q"],
                    "acceptable_proxy": False,
                    "forbidden_proxy": ["unbound supplier attribution"],
                    "stop_condition": "return candidates or typed gap",
                    "clarification_policy": "return_typed_gap",
                },
                "labels": {
                    "positive_object_ids": ["OBJ-POS"],
                    "hard_negative_object_ids": ["OBJ-NEG"],
                    "unjudged_object_ids": [],
                    "expected_roles_by_object_id": {
                        "OBJ-POS": ["direct_demand_signal"],
                        "OBJ-NEG": ["generic_or_boilerplate"],
                    },
                },
            }
        ],
    }


def _object(object_id: str, ticker: str, text: str) -> dict:
    return {
        "schema_version": "fin_ia_compiled_financial_object_view_v1_0",
        "compiled_object_id": object_id,
        "object_kind": "claim",
        "base_object_view": {
            "source_record_id": f"SRC::{object_id}",
            "ticker": ticker,
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "publication_date": "2026-04-29",
            "fiscal_year": 2026,
            "section": "Item 2. Management Discussion",
            "subsection": "Results",
            "surface_text": text,
        },
        "lineage_source_record_ids": [f"SRC::{object_id}"],
        "model_text": text,
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "evidence_promoted": False,
    }


def test_query_atom_compiles_before_labels_and_filters_wrong_owner() -> None:
    kernel, policy = _runtime_contracts()
    atom = load_query_atoms(_payload())[0]
    _, lane = compile_atom_lane(atom, kernel)
    objects = (
        _object("OBJ-POS", "MSFT", "Customer demand and AI infrastructure deployments increased."),
        _object("OBJ-NEG", "MSFT", "Microsoft provides a broad portfolio of solutions."),
        _object("OBJ-WRONG", "MU", "AI infrastructure demand increased."),
    )
    result = evaluate_query_atom(
        atom=atom,
        lane=lane,
        route_policy=policy,
        objects=objects,
        document_embeddings=np.asarray(
            [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]], dtype=np.float32
        ),
        query_embedding=np.asarray([1.0, 0.0], dtype=np.float32),
        reranker_scorers={
            "fixed_test": lambda pairs: [
                2.0 if "Customer demand" in document else 1.0
                for _, document in pairs
            ]
        },
        first_stage_limit=8,
        candidate_union_limit=8,
        top_k=2,
    )
    assert result["evidence_owner_ticker"] == "MSFT"
    assert result["eligible_object_count"] == 2
    assert result["exclusion_counts"]["outside_evidence_owner_scope"] == 1
    assert "OBJ-WRONG" not in result["candidate_union_ids"]
    assert result["rerankers"]["fixed_test"]["positive_target_in_top_k"] is True
    assert result["candidate_not_evidence"] is True
    assert result["numeric_authority"] is False
    summary = aggregate_query_atom_results([result])
    assert summary["rerankers"]["fixed_test"]["pairwise_accuracy"] == 1.0


def test_query_atom_rejects_mixed_facet_or_owner_request() -> None:
    payload = _payload()
    payload["atoms"][0]["request"]["requested_facet_ids"] = [
        "reported_results",
        "guidance_and_outlook",
    ]
    with pytest.raises(QueryAtomShadowError, match="query_atom_eval_not_atomic"):
        load_query_atoms(payload)


def test_query_atom_rejects_label_overlap() -> None:
    payload = _payload()
    payload["atoms"][0]["labels"]["hard_negative_object_ids"] = ["OBJ-POS"]
    with pytest.raises(QueryAtomShadowError, match="query_atom_eval_label_overlap"):
        load_query_atoms(payload)


def test_qrel_adjudication_adds_reviewed_positive_without_rewriting_base() -> None:
    atoms = load_query_atoms(_payload())
    result = apply_query_atom_label_adjudications(
        atoms,
        {
            "schema_version": "fin_ia_query_atom_label_adjudication_v1_0",
            "authority": {
                "candidate_is_not_evidence": True,
                "numeric_authority": False,
                "owner_acceptance": False,
            },
            "adjudications": [
                {
                    "atom_id": "DELL_DOWNSTREAM_MSFT",
                    "add_positive_object_ids": ["OBJ-NEW"],
                    "expected_roles_by_object_id": {
                        "OBJ-NEW": ["direct_demand_signal"]
                    },
                }
            ],
        },
    )

    assert atoms[0].positive_object_ids == ("OBJ-POS",)
    assert result[0].positive_object_ids == ("OBJ-POS", "OBJ-NEW")
    assert result[0].expected_roles_by_object_id["OBJ-NEW"] == (
        "direct_demand_signal",
    )


def test_qrel_adjudication_rejects_existing_label_reclassification() -> None:
    atoms = load_query_atoms(_payload())
    with pytest.raises(QueryAtomShadowError, match="label_overlap"):
        apply_query_atom_label_adjudications(
            atoms,
            {
                "schema_version": "fin_ia_query_atom_label_adjudication_v1_0",
                "authority": {
                    "candidate_is_not_evidence": True,
                    "numeric_authority": False,
                    "owner_acceptance": False,
                },
                "adjudications": [
                    {
                        "atom_id": "DELL_DOWNSTREAM_MSFT",
                        "add_positive_object_ids": ["OBJ-NEG"],
                        "expected_roles_by_object_id": {
                            "OBJ-NEG": ["direct_demand_signal"]
                        },
                    }
                ],
            },
        )


def test_controlled_pool_isolates_reranker_and_role_without_changing_candidates() -> None:
    kernel, policy = _runtime_contracts()
    atom = load_query_atoms(_payload())[0]
    _, lane = compile_atom_lane(atom, kernel)
    objects = (
        _object(
            "OBJ-POS",
            "MSFT",
            "Customer demand and AI infrastructure deployments increased.",
        ),
        _object(
            "OBJ-NEG",
            "MSFT",
            "Microsoft provides a broad portfolio of unrelated solutions.",
        ),
    )
    audit = label_eligibility_rows(
        objects,
        atom=atom,
        lane=lane,
        route_policy=policy,
    )
    assert all(row["eligible"] for row in audit)
    ranking = evaluate_controlled_reranker(
        atom=atom,
        object_ids=["OBJ-POS", "OBJ-NEG"],
        scores=[3.0, -1.0],
        top_k=2,
    )
    assert ranking["pairwise_wins"] == 1
    assert ranking["pairwise_comparisons"] == 1
    assert ranking["candidate_not_evidence"] is True
    roles = evaluate_controlled_evidence_roles(
        atom=atom,
        lane=lane,
        objects=objects,
        controlled_object_ids=["OBJ-POS", "OBJ-NEG"],
    )
    assert roles["metrics"]["positive_count"] == 1
    assert roles["metrics"]["hard_negative_count"] == 1
    assert roles["candidate_not_evidence"] is True
    assert aggregate_evidence_role_metrics(roles["rows"]) == roles["metrics"]


def test_label_eligibility_keeps_wrong_owner_out_of_diagnostic_pool() -> None:
    kernel, policy = _runtime_contracts()
    atom = load_query_atoms(_payload())[0]
    _, lane = compile_atom_lane(atom, kernel)
    objects = (
        _object("OBJ-POS", "MSFT", "Customer demand increased."),
        _object("OBJ-NEG", "MU", "Microsoft provides a broad portfolio."),
    )
    audit = {
        row["compiled_object_id"]: row
        for row in label_eligibility_rows(
            objects,
            atom=atom,
            lane=lane,
            route_policy=policy,
        )
    }
    assert audit["OBJ-POS"]["eligible"] is True
    assert audit["OBJ-NEG"]["eligible"] is False
    assert audit["OBJ-NEG"]["exclusion_reason"] == "outside_evidence_owner_scope"
