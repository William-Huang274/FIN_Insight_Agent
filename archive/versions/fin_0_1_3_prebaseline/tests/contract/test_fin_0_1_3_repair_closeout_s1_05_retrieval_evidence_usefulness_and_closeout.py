from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.releases.materialize_fin_ia_0_1_3_repair_closeout_s1_04_graph import (
    _load_documents,
)
from scripts.releases.materialize_fin_ia_0_1_3_repair_closeout_s1_05 import (
    _graph_compatible_policy,
)
from sec_agent.retrieval_evidence_usefulness_program import (
    RetrievalEvidenceUsefulnessError,
    canonical_digest,
    compile_official_semantic_evidence_successor,
    compile_retrieval_evidence_usefulness_program,
    load_retrieval_evidence_usefulness_policy,
    validate_official_semantic_evidence_successor,
    validate_retrieval_evidence_usefulness_program,
)


POLICY_PATH = REPO_ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_retrieval_evidence_usefulness_policy_v1_0.json"
OFFICIAL_PATH = REPO_ROOT / "data/workbench_private/fin_0_1_3_s1_03/formal-current-proof-r4-result.json"
OFFICIAL_ROOT = REPO_ROOT / "data/workbench_private/fin_0_1_3_s1_03/formal-current-proof-r4"
MATERIAL_PATH = REPO_ROOT / "data/workbench_private/fin_0_1_3_s1_01_reopen/current_material_numeric_program_v1_1.json"
GRAPH_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_04_authoritative_relationship_graph_and_typed_empty_v1_0.json"
DECISION_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"
ACTIVE_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_active_test_suite_successor_v1_0.json"


@lru_cache(maxsize=1)
def _actual_inputs() -> tuple[dict, dict, dict, dict, dict]:
    policy = load_retrieval_evidence_usefulness_policy(POLICY_PATH)
    official = json.loads(OFFICIAL_PATH.read_text(encoding="utf-8"))["result"]
    material = json.loads(MATERIAL_PATH.read_text(encoding="utf-8"))["program_set"]
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))["graph_program"]
    documents = _load_documents(
        policy=_graph_compatible_policy(policy, graph),
        official_source_program=official,
        runtime_root=OFFICIAL_ROOT,
    )
    return policy, official, material, graph, documents


def _compile() -> tuple[dict, dict, tuple[dict, dict, dict, dict, dict]]:
    inputs = _actual_inputs()
    policy, official, material, graph, documents = inputs
    semantic = compile_official_semantic_evidence_successor(
        policy=policy,
        official_source_program=official,
        parsed_source_documents=documents,
    )
    program = compile_retrieval_evidence_usefulness_program(
        policy=policy,
        official_source_program=official,
        material_program_set=material,
        graph_program=graph,
        semantic_successor=semantic,
    )
    return semantic, program, inputs


def _reseal_semantic(successor: dict) -> None:
    for case in successor["cases"]:
        for row in case["slots"]:
            body = {
                key: value
                for key, value in row.items()
                if key != "successor_result_digest"
            }
            row["successor_result_digest"] = canonical_digest(body)
        case_body = {key: value for key, value in case.items() if key != "case_digest"}
        case["case_digest"] = canonical_digest(case_body)
    body = {
        key: value
        for key, value in successor.items()
        if key != "semantic_successor_digest"
    }
    successor["semantic_successor_digest"] = canonical_digest(body)


def _reseal_program(program: dict) -> None:
    for query in program["query_results"]:
        body = {key: value for key, value in query.items() if key != "query_digest"}
        query["query_digest"] = canonical_digest(body)
    body = {key: value for key, value in program.items() if key != "program_digest"}
    program["program_digest"] = canonical_digest(body)


def test_current_semantic_successor_rejects_three_keyword_only_surfaces() -> None:
    semantic, _program, inputs = _compile()
    policy, official, _material, _graph, documents = inputs
    validate_official_semantic_evidence_successor(
        semantic,
        policy=policy,
        official_source_program=official,
        parsed_source_documents=documents,
    )
    assert semantic["observed_counts"] == {
        "semantic_slots": 9,
        "accepted_useful": 7,
        "typed_gaps": 2,
        "network_calls": 0,
        "model_calls": 0,
    }
    rows = {
        (case["case_key"], row["slot_id"]): row
        for case in semantic["cases"]
        for row in case["slots"]
    }
    assert rows[("DELL", "current_issuer_demand_signal")]["status"] == (
        "typed_gap_after_usefulness_review"
    )
    assert rows[("NVDA", "current_issuer_counterevidence")]["status"] == (
        "typed_gap_after_usefulness_review"
    )
    assert "table of contents" not in rows[
        ("MU", "current_issuer_counterevidence")
    ]["statement"].lower()


def test_nine_queries_recall_all_required_candidates_with_honest_gaps() -> None:
    semantic, program, inputs = _compile()
    policy, official, material, graph, _documents = inputs
    validate_retrieval_evidence_usefulness_program(
        program,
        policy=policy,
        official_source_program=official,
        material_program_set=material,
        graph_program=graph,
        semantic_successor=semantic,
    )
    assert program["observed_counts"]["queries"] == 9
    assert program["observed_counts"]["terminal_queries"] == 9
    assert program["observed_counts"]["required_candidates"] == 26
    assert program["observed_counts"]["recalled_required_candidates"] == 26
    assert program["observed_counts"]["typed_gap_records"] == 2
    assert program["observed_counts"]["false_promotions"] == 0
    assert all(
        row["selected_candidate_count"] <= row["candidate_ceiling"]
        for row in program["query_results"]
    )


def test_source_diversity_and_graph_financial_boundary_are_explicit() -> None:
    _semantic, program, _inputs = _compile()
    for query in program["query_results"]:
        if query["selected_candidate_count"] > 1 and query["source_url_count"] < 2:
            assert query["source_diversity_exception"]
        for candidate in query["selected_candidates"]:
            if candidate["relationship_fact_only"]:
                assert candidate["financial_fact_authority"] is False
    value_queries = [
        row
        for row in program["query_results"]
        if row["cell_id"] == "value_and_profit_capture"
    ]
    assert all(row["source_url_count"] >= 2 for row in value_queries)


def test_resealed_semantic_and_cross_case_candidate_mutations_fail_closed() -> None:
    semantic, program, inputs = _compile()
    policy, official, material, graph, documents = inputs
    semantic_mutation = deepcopy(semantic)
    row = next(
        row
        for case in semantic_mutation["cases"]
        for row in case["slots"]
        if row.get("status") == "accepted_useful_current_official_evidence"
    )
    row["statement"] = "Table of Contents Risk Factors"
    _reseal_semantic(semantic_mutation)
    with pytest.raises(
        RetrievalEvidenceUsefulnessError, match="semantic_successor_content_invalid"
    ):
        validate_official_semantic_evidence_successor(
            semantic_mutation,
            policy=policy,
            official_source_program=official,
            parsed_source_documents=documents,
        )

    program_mutation = deepcopy(program)
    candidate = next(
        row
        for query in program_mutation["query_results"]
        for row in query["selected_candidates"]
    )
    candidate["case_key"] = "CROSS_CASE"
    candidate_body = {
        key: value
        for key, value in candidate.items()
        if key not in {"candidate_id", "candidate_digest"}
    }
    candidate["candidate_digest"] = canonical_digest(candidate_body)
    candidate["candidate_id"] = (
        f"fin013_retrieval_candidate_{candidate['candidate_digest'][:24]}"
    )
    _reseal_program(program_mutation)
    with pytest.raises(
        RetrievalEvidenceUsefulnessError,
        match="retrieval_usefulness_query_results_invalid",
    ):
        validate_retrieval_evidence_usefulness_program(
            program_mutation,
            policy=policy,
            official_source_program=official,
            material_program_set=material,
            graph_program=graph,
            semantic_successor=semantic,
        )


def test_candidate_ceiling_and_graph_financial_mutations_stop_compilation() -> None:
    semantic, _program, inputs = _compile()
    policy, official, material, graph, _documents = inputs
    low_ceiling = deepcopy(policy)
    low_ceiling["candidate_ceiling_per_query"] = 5
    with pytest.raises(
        RetrievalEvidenceUsefulnessError,
        match="retrieval_usefulness_candidate_ceiling_exceeded",
    ):
        compile_retrieval_evidence_usefulness_program(
            policy=low_ceiling,
            official_source_program=official,
            material_program_set=material,
            graph_program=graph,
            semantic_successor=semantic,
        )

    bad_graph = deepcopy(graph)
    edge = next(
        edge for case in bad_graph["case_graphs"] for edge in case["edges"]
    )
    edge["financial_fact_authority"] = True
    with pytest.raises(
        RetrievalEvidenceUsefulnessError, match="graph_candidate_financial_promotion"
    ):
        compile_retrieval_evidence_usefulness_program(
            policy=policy,
            official_source_program=official,
            material_program_set=material,
            graph_program=bad_graph,
            semantic_successor=semantic,
        )


def test_materialized_closeout_and_active_suite_are_digest_bound() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    digest = decision.pop("record_digest")
    assert digest == canonical_digest(decision)
    assert decision["acceptance"]["S1"] == "pass_closed"
    assert decision["acceptance"]["query_terminal_coverage"] == "9/9"
    assert decision["acceptance"]["required_slot_recall"] == "26/26"
    assert decision["stage_boundary"]["S2"] == "next_not_started"
    assert decision["stage_boundary"]["model_or_full_chain"] is False

    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    suite_digest = active.pop("suite_digest")
    assert suite_digest == canonical_digest(active)
    assert active["decision_sha256"] == hashlib.sha256(DECISION_PATH.read_bytes()).hexdigest()
    assert active["stage_boundary"]["S1"] == "pass_closed"
