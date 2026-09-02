from __future__ import annotations

import copy
import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    REPO_ROOT
    / "scripts"
    / "qualification"
    / "run_dell_structured_rag_slice_qualification.py"
)
SPEC = importlib.util.spec_from_file_location("dell_structured_rag_qualification", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def _text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _span_rows(*rows: tuple[str, list[str], str]) -> list[dict[str, object]]:
    return [
        {
            "span_index": index,
            "span_kind": kind,
            "source_block_ids": block_ids,
            "content_sha256": _text_sha(content),
            "content": content,
        }
        for index, (kind, block_ids, content) in enumerate(rows)
    ]


def _node(node_id: str, *, route: str = "dell_q1") -> dict[str, object]:
    return {
        "node_id": node_id,
        "issuer_id": "DELL",
        "fiscal_period": "FY2027_Q1",
        "route_id": route,
        "source_role": "issuer_management_disclosure",
        "lane": "prose_leaf",
        "content": f"content for {node_id}",
    }


def test_mixed_table_chunk_retains_only_its_non_table_blocks_with_lineage() -> None:
    route_id = "micron_release"
    raw_sha = "a" * 64
    section_content = "Narrative about customer agreements\n\n| Metric | Value |"
    narrative = "Narrative about customer agreements"
    mixed_fragment = "about customer agreements"
    standalone = "Standalone prose"
    table = "| Metric | Value |\n| --- | --- |\n| Revenue | 10 |"
    authority = {
        "candidate_is_not_evidence": True,
        "numeric_authority": False,
        "citation_eligible": False,
    }
    common = {
        "parent_document_id": "DOC::1",
        "parent_section_id": "SECTION::1",
        "route_id": route_id,
        "raw_body_sha256": raw_sha,
        **authority,
    }
    corpus = {
        "documents": [
            {
                "document_id": "DOC::1",
                "route_id": route_id,
                "raw_body_sha256": raw_sha,
                "company": "Micron",
                "issuer_id": "MICRON",
                "ticker": "MU",
                "fiscal_period": "FY2026_Q3",
                "period_end": "2026-05-28",
                "publication_date": "2026-06-24",
                "source_role": "supplier_management_disclosure",
                "stable_url": "https://example.test/micron",
                "title": "Micron release",
                "document_kind": "html",
            }
        ],
        "sections": [
            {
                **{
                    key: value
                    for key, value in common.items()
                    if key != "parent_section_id"
                },
                "section_id": "SECTION::1",
                "section_path": ["Results"],
                "content": section_content,
                "content_sha256": _text_sha(section_content),
                "page_start": None,
                "page_end": None,
            }
        ],
        "blocks": [
            {
                **common,
                "block_id": "BLOCK::P1",
                "block_kind": "p",
                "block_index": 0,
                "content": narrative,
                "content_sha256": _text_sha(narrative),
            },
            {
                **common,
                "block_id": "BLOCK::T1",
                "block_kind": "table",
                "block_index": 1,
                "content": table,
                "content_sha256": _text_sha(table),
                "table_id": "TABLE::1",
                "table_row_count": 2,
                "table_column_count": 2,
            },
            {
                **common,
                "block_id": "BLOCK::P2",
                "block_kind": "p",
                "block_index": 2,
                "content": standalone,
                "content_sha256": _text_sha(standalone),
            },
        ],
        "chunks": [
            {
                **common,
                "chunk_id": "CHUNK::MIXED",
                "contains_table": True,
                "block_ids": ["BLOCK::P1", "BLOCK::T1"],
                "text": f"{mixed_fragment}\n\n{table}",
                "text_sha256": _text_sha(f"{mixed_fragment}\n\n{table}"),
                "retrieval_spans": (
                    mixed_spans := _span_rows(
                        ("p", ["BLOCK::P1"], mixed_fragment),
                        ("table", ["BLOCK::T1"], table),
                    )
                ),
                "retrieval_span_count": len(mixed_spans),
                "retrieval_spans_sha256": runner.canonical_digest(mixed_spans),
                "retrieval_span_text_sha256": _text_sha(
                    "\n".join(row["content"] for row in mixed_spans)
                ),
                "section_chunk_index": 0,
            },
            {
                **common,
                "chunk_id": "CHUNK::MIXED-OVERLAP",
                "contains_table": True,
                "block_ids": ["BLOCK::P1", "BLOCK::T1"],
                "text": f"{mixed_fragment}\n\n{table}",
                "text_sha256": _text_sha(f"{mixed_fragment}\n\n{table}"),
                "retrieval_spans": mixed_spans,
                "retrieval_span_count": len(mixed_spans),
                "retrieval_spans_sha256": runner.canonical_digest(mixed_spans),
                "retrieval_span_text_sha256": _text_sha(
                    "\n".join(row["content"] for row in mixed_spans)
                ),
                "section_chunk_index": 1,
            },
            {
                **common,
                "chunk_id": "CHUNK::PROSE",
                "contains_table": False,
                "block_ids": ["BLOCK::P2"],
                "text": standalone,
                "text_sha256": _text_sha(standalone),
                "retrieval_spans": (
                    prose_spans := _span_rows(
                        ("p", ["BLOCK::P2"], standalone),
                    )
                ),
                "retrieval_span_count": len(prose_spans),
                "retrieval_spans_sha256": runner.canonical_digest(prose_spans),
                "retrieval_span_text_sha256": _text_sha(standalone),
                "section_chunk_index": 2,
            },
        ],
    }

    first = runner.build_retrieval_nodes(corpus)
    second = runner.build_retrieval_nodes(corpus)
    mixed = next(row for row in first["prose"] if row["node_kind"] == "mixed_prose_span")

    assert mixed["node_id"].startswith("MIXEDPROSE::")
    assert mixed["node_id"] == next(
        row["node_id"]
        for row in second["prose"]
        if row["node_kind"] == "mixed_prose_span"
    )
    assert mixed["content"] == mixed_fragment
    assert narrative not in mixed["content"]
    assert table not in mixed["content"]
    assert mixed["source_chunk_id"] == "CHUNK::MIXED"
    assert mixed["source_chunk_ids"] == ["CHUNK::MIXED", "CHUNK::MIXED-OVERLAP"]
    assert mixed["source_block_ids"] == ["BLOCK::P1"]
    assert mixed["parent_document_id"] == "DOC::1"
    assert mixed["parent_section_id"] == "SECTION::1"
    assert first["parents"][0]["parent_section_id"] == "SECTION::1"
    assert first["parents"][0]["section_path"] == ["Results"]
    assert [row["node_id"] for row in first["tables"]] == ["BLOCK::T1"]
    assert [row["node_id"] for row in first["prose"] if row["node_kind"] == "chunk"] == [
        "CHUNK::PROSE"
    ]
    assert first["coverage"]["table_containing_chunk_count"] == 2
    assert first["coverage"]["mixed_prose_source_chunk_count"] == 2
    assert first["coverage"]["mixed_prose_leaf_count"] == 1
    assert first["coverage"]["mixed_prose_raw_span_run_count"] == 2
    assert first["coverage"]["mixed_prose_deduplicated_run_count"] == 1
    assert first["coverage"]["mixed_prose_raw_span_character_count"] == 2 * len(
        mixed_fragment
    )
    assert first["coverage"]["mixed_prose_candidate_character_count"] == len(
        mixed_fragment
    )
    assert first["coverage"]["table_or_image_only_chunk_count"] == 0
    assert first["coverage"]["mixed_non_table_unique_block_count"] == 1
    assert first["coverage"]["mixed_non_table_exclusive_block_count"] == 1
    assert first["coverage"]["mixed_non_table_exclusive_character_count"] == len(
        narrative
    )

    cross_lineage = copy.deepcopy(corpus)
    cross_lineage["blocks"][1]["parent_section_id"] = "SECTION::OTHER"
    with pytest.raises(runner.QualificationError, match="chunk_block_lineage_drift"):
        runner.build_retrieval_nodes(cross_lineage)

    flag_drift = copy.deepcopy(corpus)
    flag_drift["chunks"][0]["contains_table"] = False
    with pytest.raises(runner.QualificationError, match="chunk_contains_table_span_drift"):
        runner.build_retrieval_nodes(flag_drift)


def test_retrieval_scope_filters_local_metadata_but_never_external_diagnostics() -> None:
    rows = [
        {
            **_node("DELL-Q1"),
            "issuer_id": "DELL",
            "fiscal_period": "FY2027_Q1",
            "source_role": "issuer_management_disclosure",
        },
        {
            **_node("DELL-Q2"),
            "issuer_id": "DELL",
            "fiscal_period": "FY2027_Q2",
            "source_role": "issuer_management_disclosure",
        },
        {
            **_node("HPE-Q2"),
            "issuer_id": "HPE",
            "fiscal_period": "FY2026_Q2",
            "source_role": "peer_financial_disclosure",
        },
    ]
    scope = {
        "issuer_ids": ["DELL"],
        "fiscal_periods": ["FY2027_Q2"],
        "source_roles": ["issuer_management_disclosure"],
    }

    local = runner._eligible_nodes_for_query(
        rows,
        {"expected_route": "local", "retrieval_scope": scope},
    )
    external = runner._eligible_nodes_for_query(
        rows,
        {"expected_route": "external", "retrieval_scope": scope},
    )

    assert [row["node_id"] for row in local] == ["DELL-Q2"]
    assert [row["node_id"] for row in external] == [
        "DELL-Q1",
        "DELL-Q2",
        "HPE-Q2",
    ]


def test_qrels_reject_nested_answer_or_supporting_span() -> None:
    assert runner._forbidden_qrel_key_present(
        {"queries": [{"metadata": {"supporting_span": "leaked text"}}]}
    )
    assert runner._forbidden_qrel_key_present(
        {"queries": [{"metadata": {"expected_answer": "leaked answer"}}]}
    )


def test_load_qrels_validates_gold_metadata_contract(tmp_path: Path) -> None:
    artifact_path = tmp_path / "documents.jsonl"
    artifact_path.write_text("{}\n", encoding="utf-8")
    artifact_digest = runner.sha256_file(artifact_path)
    payload = {
        "schema_version": runner.QRELS_SCHEMA,
        "corpus_artifacts": {"documents.jsonl": artifact_digest},
        "queries": [
            {
                "query_id": "Q1",
                "question_zh": "问题",
                "retrieval_query_en": "Dell Q1 revenue",
                "expected_route": "local",
                "critical": True,
                "gold_node_ids": ["GOLD"],
                "acceptable_alternate_node_ids": ["ALT"],
                "direct_alternate_node_ids": ["ALT"],
                "derivable_node_ids": [],
                "partial_node_ids": [],
                "hard_negative_node_ids": ["NEG"],
                "retrieval_scope": {
                    "issuer_ids": ["DELL"],
                    "fiscal_periods": ["FY2027_Q1"],
                    "source_roles": ["issuer_management_disclosure"],
                },
                "must_match": {
                    "issuer": "DELL",
                    "period": "FY2027_Q1",
                    "routes": ["dell_q1", "dell_q1_transcript"],
                    "source_role": "issuer_management_disclosure",
                },
            }
        ],
    }
    qrels_path = tmp_path / "qrels.json"
    qrels_path.write_text(json.dumps(payload), encoding="utf-8")
    nodes = {
        "GOLD": _node("GOLD"),
        "ALT": _node("ALT", route="dell_q1_transcript"),
        "NEG": {**_node("NEG"), "fiscal_period": "FY2027_Q2"},
    }

    loaded = runner.load_qrels(
        qrels_path,
        node_index=nodes,
        corpus_artifacts={
            "documents.jsonl": {"sha256": artifact_digest},
            "result.json": {"sha256": "a" * 64},
        },
    )

    assert loaded["queries"][0]["gold_requirement"] == "any"


def test_load_qrels_rejects_gold_route_contract_drift(tmp_path: Path) -> None:
    artifact_path = tmp_path / "documents.jsonl"
    artifact_path.write_text("{}\n", encoding="utf-8")
    digest = runner.sha256_file(artifact_path)
    qrels_path = tmp_path / "qrels.json"
    qrels_path.write_text(
        json.dumps(
            {
                "schema_version": runner.QRELS_SCHEMA,
                "corpus_artifacts": {"documents.jsonl": digest},
                "queries": [
                    {
                        "query_id": "Q1",
                        "question_zh": "问题",
                        "retrieval_query_en": "Dell Q1 revenue",
                        "expected_route": "local",
                        "gold_node_ids": ["GOLD"],
                        "acceptable_alternate_node_ids": [],
                        "direct_alternate_node_ids": [],
                        "derivable_node_ids": [],
                        "partial_node_ids": [],
                        "hard_negative_node_ids": [],
                        "retrieval_scope": {
                            "issuer_ids": ["DELL"],
                            "fiscal_periods": ["FY2027_Q1"],
                            "source_roles": ["issuer_management_disclosure"],
                        },
                        "must_match": {
                            "issuer": "DELL",
                            "period": "FY2027_Q1",
                            "route": "wrong_route",
                            "source_role": "issuer_management_disclosure",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(runner.QualificationError, match="qrel_route_contract_drift"):
        runner.load_qrels(
            qrels_path,
            node_index={"GOLD": _node("GOLD")},
            corpus_artifacts={"documents.jsonl": {"sha256": digest}},
        )


def test_all_gold_requirement_accepts_transcript_neighbor_delivery() -> None:
    query = {
        "query_id": "Q1",
        "expected_route": "local",
        "critical": True,
        "gold_requirement": "all",
        "gold_node_ids": ["PAGE5", "PAGE6"],
        "acceptable_alternate_node_ids": [],
        "hard_negative_node_ids": ["WRONG"],
    }
    result = {
        "Q1": {
            "ranking": [
                {"rank": 1, "node_id": "PAGE5"},
                {"rank": 2, "node_id": "WRONG"},
                {"rank": 3, "node_id": "OTHER"},
                {"rank": 4, "node_id": "PAGE6"},
            ],
            "delivery": [
                {
                    "rank": 1,
                    "node_id": "PAGE5",
                    "expanded_context_node_ids": ["PAGE5", "PAGE6"],
                }
            ],
        }
    }

    metrics = runner.evaluate_route(
        route_results=result,
        queries=[query],
        cutoffs=[1, 5],
    )

    assert metrics["critical_required_facet_miss_count_at_1"] == 0
    assert metrics["required_facet_satisfaction_rate_at_1"] == 1.0
    assert metrics["critical_anchor_required_facet_miss_count_at_1"] == 1
    assert metrics["anchor_required_facet_satisfaction_rate_at_1"] == 0.0
    assert metrics["delivered_hard_negative_count_at_5"] == 1


def test_transcript_delivery_expands_adjacent_chunks_not_whole_pages() -> None:
    rows = [
        {
            **_node(f"N{index}", route="dell_transcript"),
            "page_start": page,
            "section_chunk_index": chunk,
        }
        for index, (page, chunk) in enumerate(
            [(4, 0), (4, 1), (5, 0), (5, 1), (6, 0), (6, 1)], start=1
        )
    ]

    expanded = runner._expanded_context_ids(rows[3], prose_nodes=rows, radius=1)

    assert expanded == ["N3", "N4", "N5"]


def test_derivable_and_partial_nodes_are_visible_but_do_not_count_as_direct_hits() -> None:
    query = {
        "query_id": "Q1",
        "question_zh": "问题",
        "retrieval_query_en": "query",
        "expected_route": "local",
        "critical": True,
        "gold_requirement": "any",
        "gold_node_ids": ["GOLD"],
        "acceptable_alternate_node_ids": ["DIRECT"],
        "direct_alternate_node_ids": ["DIRECT"],
        "derivable_node_ids": ["DERIVABLE"],
        "partial_node_ids": ["PARTIAL"],
        "hard_negative_node_ids": [],
        "retrieval_scope": {
            "issuer_ids": ["DELL"],
            "fiscal_periods": ["FY2027_Q1"],
            "source_roles": ["issuer_management_disclosure"],
        },
    }
    route = {
        "Q1": {
            "ranking": [
                {"rank": 1, "node_id": "DERIVABLE"},
                {"rank": 2, "node_id": "PARTIAL"},
                {"rank": 3, "node_id": "OTHER"},
                {"rank": 4, "node_id": "DIRECT"},
                {"rank": 5, "node_id": "GOLD"},
            ],
            "delivery": [],
        }
    }

    metrics = runner.evaluate_route(
        route_results=route,
        queries=[query],
        cutoffs=[2, 5],
    )
    review = runner.render_human_review(
        queries=[query],
        routes={"bm25": route},
        node_index={
            node_id: _node(node_id)
            for node_id in ("DERIVABLE", "PARTIAL", "OTHER", "DIRECT", "GOLD")
        },
    )

    assert metrics["hit_rate_at_2"] == 0.0
    assert metrics["hit_rate_at_5"] == 1.0
    assert metrics["derivable_count_at_2"] == 1
    assert metrics["partial_count_at_2"] == 1
    assert "DERIVABLE-NOT-DIRECT" in review
    assert "PARTIAL-NOT-DIRECT" in review
    assert "DIRECT-ALT" in review


def test_hybrid_rrf_is_deterministic_and_respects_weight() -> None:
    receipt = {
        "expected_route": "local",
        "answer_free_retrieval_scope": {
            "issuer_ids": ["DELL"],
            "fiscal_periods": ["FY2027_Q1"],
            "source_roles": ["issuer_management_disclosure"],
        },
        "scope_applied": True,
    }
    candidate_counts = {"leaf_all": 2, "parent": 1, "prose": 2, "table": 0}
    bm25 = {
        "Q1": {
            "ranking": [
                {"rank": 1, "node_id": "LEX", "score": 10.0},
                {"rank": 2, "node_id": "SEM", "score": 9.0},
            ],
            "retrieval_scope_receipt": receipt,
            "eligible_candidate_counts": candidate_counts,
        }
    }
    dense = {
        "Q1": {
            "ranking": [
                {"rank": 1, "node_id": "SEM", "score": 0.9},
                {"rank": 2, "node_id": "LEX", "score": 0.8},
            ],
            "retrieval_scope_receipt": receipt,
            "eligible_candidate_counts": candidate_counts,
        }
    }
    policy = {
        "retrieval": {
            "hybrid": {
                "rrf_constant": 60,
                "source_depth": 100,
                "bm25_weight": 3.0,
                "dense_weight": 1.0,
            }
        }
    }

    first = runner.run_hybrid(bm25=bm25, dense=dense, policy=policy)
    second = runner.run_hybrid(bm25=bm25, dense=dense, policy=policy)

    assert first == second
    assert first["Q1"]["ranking"][0]["node_id"] == "LEX"

    parent_drift = copy.deepcopy(dense)
    parent_drift["Q1"]["eligible_candidate_counts"]["parent"] = 2
    with pytest.raises(runner.QualificationError, match="hybrid_retrieval_scope_drift"):
        runner.run_hybrid(bm25=bm25, dense=parent_drift, policy=policy)


def test_external_query_review_shows_local_substitution_diagnostics() -> None:
    nodes = {f"N{i}": _node(f"N{i}") for i in range(1, 12)}
    query = {
        "query_id": "E1",
        "question_zh": "外部问题",
        "retrieval_query_en": "external current fact",
        "expected_route": "external",
        "critical": True,
        "gold_requirement": "any",
        "gold_node_ids": [],
        "acceptable_alternate_node_ids": [],
        "hard_negative_node_ids": [],
    }
    routes = {
        "bm25": {
            "E1": {
                "ranking": [
                    {"rank": index, "node_id": f"N{index}", "score": 1.0 / index}
                    for index in range(1, 12)
                ]
            }
        }
    }

    review = runner.render_human_review(
        queries=[query], routes=routes, node_index=nodes
    )

    assert review.count("LOCAL-SUBSTITUTION-DIAGNOSTIC") == 10
    assert "must not be treated as an answer" in review
