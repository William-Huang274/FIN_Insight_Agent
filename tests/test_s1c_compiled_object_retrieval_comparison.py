from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
from scipy.sparse import csr_matrix


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.object_retrieval_comparison import (
    CandidateScore,
    dense_rank,
    eligible_object_indices,
    evaluate_route,
    load_compiled_objects,
    load_queries,
    map_reviewed_objects_to_compiled_successors,
    sparse_rank,
    union_candidate_ids,
)


def _object(object_id: str, source_id: str, *, ticker: str = "DELL") -> dict:
    return {
        "schema_version": "fin_ia_compiled_financial_object_view_v1_0",
        "compiled_object_id": object_id,
        "object_kind": "claim",
        "base_object_view": {
            "object_view_id": f"EOV::{object_id}",
            "source_record_id": source_id,
            "ticker": ticker,
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "publication_date": "2026-05-01",
            "fiscal_year": 2026,
            "surface_text": f"surface {object_id}",
        },
        "lineage_source_record_ids": [source_id],
        "model_text": f"AI server demand {object_id}",
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "evidence_promoted": False,
    }


def _query():
    payload = json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1c_requalified_qrels_v1_1.json"
        ).read_text(encoding="utf-8")
    )
    raw = dict(payload["qrels"][1])
    raw.update(
        {
            "evidence_owner_ticker": "DELL",
            "form_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "publication_date_lte": "2026-08-06",
            "reporting_fiscal_years": [2026],
            "target_current_source_record_ids": ["SRC-B"],
        }
    )
    payload["qrels"] = [raw]
    return load_queries(payload)[0]


def test_dense_and_sparse_rank_share_object_identity_and_hard_filters() -> None:
    objects = load_compiled_objects(
        [_object("OBJ-A", "SRC-A"), _object("OBJ-B", "SRC-B"), _object("OBJ-C", "SRC-C", ticker="MU")]
    )
    eligible, exclusions = eligible_object_indices(objects, _query())
    assert eligible.tolist() == [0, 1]
    assert exclusions["outside_evidence_owner_scope"] == 1
    dense = dense_rank(
        objects,
        eligible,
        np.asarray([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=np.float32),
        np.asarray([0.0, 1.0], dtype=np.float32),
        limit=2,
    )
    sparse = sparse_rank(
        objects,
        eligible,
        csr_matrix([[1.0, 0.0], [0.0, 2.0], [1.0, 1.0]]),
        csr_matrix([[0.0, 1.0]]),
        limit=2,
    )
    assert [row.compiled_object_id for row in dense] == ["OBJ-B", "OBJ-A"]
    assert [row.compiled_object_id for row in sparse] == ["OBJ-B", "OBJ-A"]


def test_route_evaluation_separates_source_and_reviewed_object_success() -> None:
    objects = load_compiled_objects([_object("OBJ-A", "SRC-TARGET"), _object("OBJ-B", "SRC-TARGET")])
    by_id = {row["compiled_object_id"]: row for row in objects}
    result = evaluate_route(
        [CandidateScore("OBJ-A", 2.0), CandidateScore("OBJ-B", 1.0)],
        by_id,
        target_source_record_ids=["SRC-TARGET"],
        reviewed_positive_object_ids=["OBJ-B"],
        top_k=1,
    )
    assert result["source_record_target_in_top_k"] is True
    assert result["reviewed_object_target_in_top_k"] is False


def test_multi_route_union_is_deterministic_and_bounded() -> None:
    union = union_candidate_ids(
        [
            [CandidateScore("OBJ-A", 2.0), CandidateScore("OBJ-B", 1.0)],
            [CandidateScore("OBJ-C", 2.0), CandidateScore("OBJ-B", 1.0)],
        ],
        maximum=2,
    )
    assert union == ("OBJ-A", "OBJ-C")


def test_whole_table_review_is_not_silently_projected_to_metric_rows() -> None:
    objects = load_compiled_objects([_object("OBJ-CLAIM", "SRC-1")])
    review_set = {
        "object_views": [
            {
                "object_view_id": "EOV::CLAIM",
                "object_form": "claim",
                "source_record_id": "SRC-1",
                "surface_text": "surface OBJ-CLAIM",
            },
            {
                "object_view_id": "EOV::TABLE",
                "object_form": "metric_table",
                "source_record_id": "SRC-1",
                "surface_text": "whole table",
            },
        ],
        "query_relations": [
            {
                "qrel_id": "Q1",
                "object_view_id": "EOV::CLAIM",
                "relevance_judgement": "positive",
            },
            {
                "qrel_id": "Q1",
                "object_view_id": "EOV::TABLE",
                "relevance_judgement": "positive",
            },
        ],
    }
    mapping = map_reviewed_objects_to_compiled_successors(objects, review_set)
    assert mapping["mapping_count"] == 1
    assert mapping["unmapped_count"] == 1
    assert mapping["positive_compiled_object_ids_by_query"] == {"Q1": ["OBJ-CLAIM"]}
    assert mapping["whole_table_projection_forbidden"] is True


def test_tracked_result_is_compact_digest_bound_and_keeps_database_boundary() -> None:
    path = (
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1c_compiled_object_retriever_comparison_result_v1_0.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    unsigned = {key: value for key, value in payload.items() if key != "result_digest"}
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert payload["schema_version"].endswith("_summary_v1_0")
    assert hashlib.sha256(encoded).hexdigest() == payload["result_digest"]
    assert payload["storage"]["full_result_ref"].startswith(
        "data/workbench_private/"
    )
    assert payload["storage"]["tracked_summary_excludes_candidate_excerpts"] is True
    for query in payload["primary_full_corpus_comparison"]["queries"]:
        for route in query["routes"].values():
            assert "candidates" not in route
    assert payload["database_lane"] == {
        "company_financial_fact_mart_built": False,
        "owning_stage": "S2",
        "ranking_model_granted_numeric_authority": False,
        "status": "typed_fact_store_unavailable",
    }
    assert payload["authority"]["numeric_fact_authority"] is False


def test_tracked_text_binding_is_stable_across_crlf_checkout(tmp_path: Path) -> None:
    script_path = (
        ROOT
        / "scripts/data_retrieval/run_s1c_compiled_object_retriever_comparison.py"
    )
    spec = importlib.util.spec_from_file_location("s1c_compiled_compare_runner", script_path)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    lf_path = tmp_path / "lf.json"
    crlf_path = tmp_path / "crlf.json"
    lf_path.write_bytes(b'{"value":1}\n')
    crlf_path.write_bytes(b'{"value":1}\r\n')

    assert runner._sha256_lf_text(lf_path) == runner._sha256_lf_text(crlf_path)
    assert runner._sha256(lf_path) != runner._sha256(crlf_path)
