from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.local_research_service import (
    LocalResearchPaths,
    P36LocalResearchService,
)


TENANT = "tenant-local-research"
PROJECT = "project-local-research"
ACTOR = "analyst-local-research"


class FakeObjectRetriever:
    def __init__(self, _path: str | Path) -> None:
        pass

    def search(self, query: str, top_k: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
        assert top_k == 3
        ticker = filters["ticker"]
        return [
            {
                "score": 9.5,
                "ticker": ticker,
                "section": "Exhibit 99.1 Earnings Release",
                "source_evidence_id": (
                    f"8K_EARNINGS::{ticker}::000104581026000051::LOCALTEST::BLOCK_0001"
                ),
                "record": {
                    "title": f"{ticker} bounded local source",
                    "source_type": "8-K",
                    "period_end": "2026-05-20",
                    "text_before": f"{ticker} source matched {query}.",
                },
            }
        ]


def _headers(*, permissions: str = "case:create,case:read,evidence:read") -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT,
        "X-Fin-Case-Project": PROJECT,
        "X-Fin-Case-Actor": ACTOR,
        "X-Fin-Case-Permissions": permissions,
        "X-Trace-Id": "trace-local-research",
    }


def _create_sources(tmp_path: Path) -> LocalResearchPaths:
    object_index = tmp_path / "object-index"
    object_index.mkdir()
    (object_index / "metadata.json").write_text(
        json.dumps({"schema_version": "test_object_fts_v1", "records": 1}),
        encoding="utf-8",
    )
    (object_index / "records.sqlite").touch()

    gold = tmp_path / "gold.sqlite"
    connection = sqlite3.connect(gold)
    connection.executescript(
        """
        CREATE TABLE gold_fact_signal_mart_metadata (key TEXT, value TEXT);
        INSERT INTO gold_fact_signal_mart_metadata VALUES
            ('schema_version', 'test_gold_v1');
        CREATE TABLE gold_fact_signal_mart (
            gold_row_id TEXT, ticker TEXT, metric_family TEXT, metric_name TEXT,
            value TEXT, unit TEXT, period TEXT, fiscal_year TEXT,
            authority_mode TEXT, claim_boundary TEXT, citation_url TEXT,
            citation_span TEXT, evidence_ref TEXT, source_url TEXT,
            can_enter_evidence_bundle INTEGER, exact_value_authority INTEGER
        );
        """
    )
    metric_values = {
        "revenue": "1000",
        "gross_profit": "700",
        "operating_income": "400",
    }
    for index, metric in enumerate(("revenue", "gross_profit", "operating_income"), 1):
        connection.execute(
            "INSERT INTO gold_fact_signal_mart VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"gold-{index}", "NVDA", metric, metric.replace("_", " ").title(),
                metric_values[metric], "USD", "FY2025-FY", "2025",
                "exact_company_fact_authority", "Consolidated company fact only.",
                "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json",
                f"Reported {metric}", f"evidence:{metric}", "", 1, 1,
            ),
        )
    connection.commit()
    connection.close()

    graph = tmp_path / "graph.sqlite"
    connection = sqlite3.connect(graph)
    connection.executescript(
        """
        CREATE TABLE research_graph_metadata (key TEXT, value TEXT);
        INSERT INTO research_graph_metadata VALUES
            ('schema_version', 'test_graph_v1');
        CREATE TABLE research_graph_nodes (
            graph_node_id TEXT, ticker TEXT, label TEXT
        );
        CREATE TABLE research_graph_edges (
            graph_edge_id TEXT, from_node_id TEXT, edge_type TEXT,
            authority_mode TEXT, source_role TEXT, claim_boundary TEXT,
            evidence_refs_json TEXT, can_enter_evidence_bundle INTEGER
        );
        CREATE TABLE research_graph_evidence_support (
            support_id TEXT, graph_edge_id TEXT, citation_url TEXT,
            citation_span TEXT, evidence_ref TEXT
        );
        """
    )
    roles = {
        "TSM": "supply_chain_official_relationship",
        "MU": "official_customer_order_or_deployment_event",
        "ASML": "supply_chain_official_relationship",
        "NVDA": "working_capital_liquidity",
    }
    for ticker, role in roles.items():
        edge_id = f"edge-{ticker.lower()}"
        connection.execute(
            "INSERT INTO research_graph_nodes VALUES (?,?,?)",
            (f"company:{ticker}", ticker, ticker),
        )
        connection.execute(
            "INSERT INTO research_graph_edges VALUES (?,?,?,?,?,?,?,?)",
            (
                edge_id, f"company:{ticker}", "HAS_BOUNDED_COUNTEREVIDENCE",
                "bounded_thesis_driver_authority", role,
                "Context only; does not prove a bottleneck or demand outcome.",
                json.dumps([f"evidence:{ticker}"]), 1,
            ),
        )
        connection.execute(
            "INSERT INTO research_graph_evidence_support VALUES (?,?,?,?,?)",
            (
                f"support-{ticker.lower()}", edge_id,
                f"https://example.com/{ticker.lower()}", f"Official {ticker} context",
                f"evidence:{ticker}",
            ),
        )
    connection.commit()
    connection.close()
    return LocalResearchPaths(object_index=object_index, gold_mart=gold, research_graph=graph)


def test_local_research_preview_reads_three_real_lanes_without_case_mutation(tmp_path: Path) -> None:
    case_service = CaseService.for_fixture_root(tmp_path / "runtime", repo_root=REPO_ROOT)
    local_service = P36LocalResearchService(
        case_service,
        paths=_create_sources(tmp_path),
        object_retriever_factory=FakeObjectRetriever,
    )
    app = create_app(
        tmp_path / "workbench.sqlite",
        p02_case_service=case_service,
        p36_local_research_service=local_service,
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/cases",
            headers=_headers(),
            json={
                "query": "Assess P36 AI infrastructure demand and profit capture",
                "as_of": "2026-07-18T00:00:00Z",
                "language": "en",
                "source_policy_ref": "fixture:internal-only",
                "idempotency_key": "local-research-case",
            },
        )
        assert created.status_code == 202, created.text
        case_id = created.json()["case_id"]
        events_before = list(case_service._facade.store.list_events())

        first = client.get(
            f"/api/v1/cases/{case_id}/local-research-preview", headers=_headers()
        )
        second = client.get(
            f"/api/v1/cases/{case_id}/local-research-preview", headers=_headers()
        )

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        view = first.json()
        assert view["research_mode"] == "bounded_local_read_only"
        assert view["selected_cell_count"] == 10
        assert view["candidate_count"] == 15
        by_role = {cell["evidence_role"]: cell for cell in view["cells"]}
        assert set(by_role) == {
            "demand_signal", "revenue_capture", "thesis_counterevidence",
            "server_oem_orders", "server_oem_margin_cash",
            "advanced_packaging_capacity", "hbm_supply_pricing",
            "semicap_capex_cycle", "export_policy_risk", "customer_concentration",
        }
        assert by_role["demand_signal"]["retrieval_lane"] == "object_bm25"
        assert by_role["revenue_capture"]["retrieval_lane"] == "gold_fact_sql"
        assert by_role["thesis_counterevidence"]["retrieval_lane"] == "research_graph"
        assert all(
            candidate["writer_citable"] is False
            and candidate["promotion_status"] == "candidate_not_promoted"
            for cell in view["cells"]
            for candidate in cell["candidates"]
        )
        assert view["execution_counts"]["network_calls"] == 0
        assert view["execution_counts"]["model_calls"] == 0
        assert view["execution_counts"]["canonical_store_writes"] == 0
        assert list(case_service._facade.store.list_events()) == events_before

        analysis_first = client.get(
            f"/api/v1/cases/{case_id}/local-analysis-preview", headers=_headers()
        )
        analysis_second = client.get(
            f"/api/v1/cases/{case_id}/local-analysis-preview", headers=_headers()
        )
        assert analysis_first.status_code == analysis_second.status_code == 200
        assert analysis_first.json() == analysis_second.json()
        analysis = analysis_first.json()
        assert analysis["status"] == "internal_analysis_preview_ready"
        assert analysis["source_preview_digest"] == view["preview_digest"]
        assert analysis["numeric"]["status"] == "exact_local_facts_computed"
        assert {
            metric["metric"]: metric["value"]
            for metric in analysis["numeric"]["derived_metrics"]
        } == {"gross_margin": "70.00", "operating_margin": "40.00"}
        assert len(analysis["repairs"]) == 10
        assert len(analysis["judgments"]) == 10
        assert analysis["workpaper"]["senior_r2_status"] == "not_reviewed"
        assert len(analysis["writer"]["sections"]) == 10
        assert analysis["writer"]["source_access_calls"] == 0
        assert analysis["writer"]["release_admitted"] is False
        assert analysis["hard_boundaries"]["canonical_store_writes"] == 0
        assert list(case_service._facade.store.list_events()) == events_before

        denied = client.get(
            f"/api/v1/cases/{case_id}/local-research-preview",
            headers=_headers(permissions="case:read"),
        )
        assert denied.status_code == 403

        paths = client.get("/openapi.json").json()["paths"]
        assert paths[f"/api/v1/cases/{{case_id}}/local-research-preview"]["get"][
            "operationId"
        ] == "getP36LocalResearchPreview"
        assert paths[f"/api/v1/cases/{{case_id}}/local-analysis-preview"]["get"][
            "operationId"
        ] == "getP36LocalAnalysisPreview"
