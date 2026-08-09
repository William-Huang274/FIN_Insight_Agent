from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_candidate_ceiling import (  # noqa: E402
    RUN_SCOPE,
    canonical_observation_digest,
    deterministic_round_robin_dedupe,
    execute_bm25_request,
    execute_graph_request,
    execute_sql_exact_request,
    load_bound_integration_proof,
    load_internal_candidate_ceiling_policy,
    resolve_document_lineage,
)


POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_internal_candidate_ceiling_policy_v1_0.json"
)


def _policy_and_proof() -> tuple[dict, dict]:
    policy = load_internal_candidate_ceiling_policy(POLICY_PATH, repo_root=ROOT)
    return policy, load_bound_integration_proof(policy, repo_root=ROOT)


def _request(proof: dict, route: str, case: str, slot: str, owner: str) -> dict:
    return next(
        item
        for item in proof["requests"]
        if (
            item["route_id"],
            item["case_key"],
            item["evidence_slot_id"],
            item["evidence_owner_ticker"],
        )
        == (route, case, slot, owner)
    )


def test_policy_binds_historical_scopes_and_owner_accepted_ranking_is_current() -> None:
    policy, proof = _policy_and_proof()
    assert policy["run_scope"] == RUN_SCOPE
    assert proof["physical_request_count"] == 90
    historical = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    assert historical["status"] == "blocked"
    refresh = run_project_os_preflight(
        ROOT, run_scope="S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"
    )
    assert refresh["status"] == "pass"
    current = run_project_os_preflight(
        ROOT, run_scope="S1_INTERNAL_CURRENT_OFFICIAL_SOURCE_ACQUISITION"
    )
    assert current["status"] == "blocked"
    assert (
        run_project_os_preflight(
            ROOT, run_scope="S1_INTERNAL_BGE_FUSION_AND_RERANK_EVALUATION"
        )["status"]
        == "pass"
    )


def test_round_robin_dedupe_is_stable_and_does_not_let_one_query_take_budget() -> None:
    rows = deterministic_round_robin_dedupe(
        [[{"id": "a"}, {"id": "b"}], [{"id": "a"}, {"id": "c"}]],
        key_fn=lambda item: item["id"],
        budget=3,
    )
    assert [item[0]["id"] for item in rows] == ["a", "c", "b"]
    assert rows[0][1] == (0, 1)


def test_complete_record_embedded_lineage_prevents_stale_manifest_fallback() -> None:
    lineage = resolve_document_lineage(
        {
            "ticker": "MU",
            "fiscal_year": 2026,
            "form_type": "8-K",
            "published_at": "2026-06-24",
            "source_url": "https://www.sec.gov/current",
            "accession_number": "0000723125-26-000013",
        },
        lookup={
            "by_accession": {},
            "by_ticker_year_form": {
                ("MU", 2026, "8-K"): [
                    {
                        "source_url": "https://www.sec.gov/stale",
                        "published_at": "2026-03-18",
                        "accession_number": "0000723125-26-000004",
                    }
                ]
            },
        },
    )
    assert lineage["source_url"] == "https://www.sec.gov/current"
    assert lineage["resolution_method"] == "record_embedded_lineage"


def _create_gold_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE gold_fact_signal_mart (
          gold_row_id TEXT,ticker TEXT,metric_family TEXT,metric_name TEXT,
          value TEXT,unit TEXT,period TEXT,fiscal_year TEXT,authority_mode TEXT,
          claim_boundary TEXT,citation_url TEXT,citation_span TEXT,evidence_ref TEXT,
          source_url TEXT,published_at TEXT,period_role TEXT,period_start TEXT,
          period_end TEXT,can_enter_evidence_bundle INTEGER,exact_value_authority INTEGER
        )
        """
    )
    connection.execute(
        "INSERT INTO gold_fact_signal_mart VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "gold_old",
            "DELL",
            "revenue",
            "Revenue",
            "100",
            "USD",
            "FY2025-FY",
            "2025",
            "exact_company_fact_authority",
            "consolidated only",
            "https://example.test/fact",
            "FY2025 revenue 100",
            "evidence_old",
            "https://example.test/fact",
            "2025-03-01",
            "annual",
            "2024-01-01",
            "2025-01-01",
            1,
            1,
        ),
    )
    connection.commit()
    connection.close()


def test_sql_exact_keeps_period_strict_and_reports_latest_available_year(
    tmp_path: Path,
) -> None:
    _, proof = _policy_and_proof()
    request = _request(
        proof,
        "internal_sql_exact",
        "DELL",
        "issuer_results_and_management_commentary",
        "DELL",
    )
    database = tmp_path / "gold.sqlite"
    _create_gold_db(database)
    terminal = execute_sql_exact_request(request, database=database)
    assert terminal["candidate_count"] == 0
    gap = terminal["typed_gaps"][0]
    assert gap["gap_code"] == "internal_exact_period_coverage_absent"
    assert gap["detail"]["latest_available_fiscal_year"] == 2025


class _FakeBM25:
    def __init__(self) -> None:
        self.filters: list[dict] = []

    def search(self, query: str, *, top_k: int, filters: dict) -> list[dict]:
        self.filters.append(filters)
        suffix = "one" if len(self.filters) == 1 else "two"
        return [
            {
                "rank": 1,
                "score": 2.0,
                "evidence_id": f"msft_{suffix}",
                "ticker": "MSFT",
                "fiscal_year": 2026,
                "record": {
                    "evidence_id": f"msft_{suffix}",
                    "ticker": "MSFT",
                    "fiscal_year": 2026,
                    "source_type": "10-Q",
                    "source_tier": "primary_sec_filing",
                    "publication_date": "2026-04-30",
                    "source_url": "https://example.test/msft",
                    "text": f"Microsoft capacity evidence {suffix}",
                },
            }
        ]


def test_bm25_uses_evidence_owner_filters_and_round_robin_candidates() -> None:
    _, proof = _policy_and_proof()
    request = _request(
        proof,
        "internal_bm25",
        "DELL",
        "customer_demand_and_deployment_validation",
        "MSFT",
    )
    retriever = _FakeBM25()
    terminal = execute_bm25_request(request, retriever=retriever)
    assert terminal["candidate_count"] == 2
    assert all(filters["ticker"] == "MSFT" for filters in retriever.filters)
    assert {item["ticker"] for item in terminal["candidates"]} == {"MSFT"}
    assert {item["source_key"] for item in terminal["candidates"]} == {
        "msft_one",
        "msft_two",
    }


def _create_graph_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE research_graph_nodes (
          graph_node_id TEXT PRIMARY KEY,ticker TEXT,label TEXT
        );
        CREATE TABLE research_graph_edges (
          graph_edge_id TEXT PRIMARY KEY,from_node_id TEXT,to_node_id TEXT,
          edge_type TEXT,authority_mode TEXT,can_enter_evidence_bundle INTEGER,
          confidence REAL,source_role TEXT,claim_boundary TEXT
        );
        CREATE TABLE research_graph_evidence_support (
          support_id TEXT PRIMARY KEY,graph_edge_id TEXT,can_enter_evidence_bundle INTEGER,
          citation_url TEXT,citation_span TEXT,evidence_ref TEXT
        );
        """
    )
    connection.executemany(
        "INSERT INTO research_graph_nodes VALUES (?,?,?)",
        [("company:TSM", "TSM", "TSMC"), ("fact:1", "", "CoWoS capacity")],
    )
    connection.executemany(
        "INSERT INTO research_graph_edges VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (
                "edge_allowed",
                "company:TSM",
                "fact:1",
                "HAS_PRODUCT_KPI_FACT",
                "bounded",
                1,
                1.0,
                "company_disclosed_product_kpi",
                "Capacity disclosure only",
            ),
            (
                "edge_forbidden_role",
                "company:TSM",
                "fact:1",
                "HAS_MARKET_SIGNAL",
                "bounded",
                1,
                1.0,
                "market_liquidity_driver",
                "Market row",
            ),
        ],
    )
    connection.execute(
        "INSERT INTO research_graph_evidence_support VALUES (?,?,?,?,?,?)",
        (
            "support_1",
            "edge_allowed",
            1,
            "https://example.test/tsm",
            "TSMC disclosed CoWoS capacity",
            "evidence_tsm",
        ),
    )
    connection.commit()
    connection.close()


def test_graph_filters_owner_and_allowed_role_without_claiming_period_match(
    tmp_path: Path,
) -> None:
    _, proof = _policy_and_proof()
    request = _request(
        proof,
        "internal_relationship_graph",
        "NVDA",
        "supply_chain_capacity_and_counterevidence",
        "TSM",
    )
    database = tmp_path / "graph.sqlite"
    _create_graph_db(database)
    terminal = execute_graph_request(request, database=database)
    assert terminal["candidate_count"] == 1
    candidate = terminal["candidates"][0]
    assert candidate["source_key"] == "edge_allowed"
    assert candidate["evidence_owner_ticker"] == "TSM"
    assert candidate["period_match_state"] == "unavailable_in_graph_index"
    assert candidate["strict_period_filter_applied"] is False


def test_observation_digest_excludes_elapsed_but_not_candidate_content() -> None:
    left = {"status": "x", "elapsed_ms": 1.0, "rows": [{"elapsed_ms": 2.0, "id": "a"}]}
    right = {"status": "x", "elapsed_ms": 9.0, "rows": [{"elapsed_ms": 8.0, "id": "a"}]}
    assert canonical_observation_digest(left) == canonical_observation_digest(right)
    right["rows"][0]["id"] = "b"
    assert canonical_observation_digest(left) != canonical_observation_digest(right)
