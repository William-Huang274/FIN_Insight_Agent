from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_internal_candidate_ceiling import (  # noqa: E402
    S1InternalCandidateCeilingError,
    execute_bm25_request,
    execute_object_bm25_request,
    execute_sql_exact_request,
    milvus_lite_storage_exists,
    qualify_local_assets,
)
from sec_agent.s1_internal_query_facet_integration import (  # noqa: E402
    S1InternalQueryFacetError,
    compile_internal_query_facet_requests,
    load_internal_query_facet_policy,
    validate_internal_route_request,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "query_facet_integration_policy_v1_1.json"
)
SOURCE_PROOF_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_"
    "unified_query_facet_zero_call_proof_v1_0.json"
)


def _compiled() -> tuple[dict, tuple, tuple]:
    policy = load_internal_query_facet_policy(POLICY_PATH)
    source = json.loads(SOURCE_PROOF_PATH.read_text(encoding="utf-8"))
    bundles, requests = compile_internal_query_facet_requests(
        query_facet_proof=source,
        policy=policy,
    )
    return policy, bundles, requests


def _request(requests: tuple, *, route: str, case: str, owner: str):
    return next(
        item
        for item in requests
        if (item.route_id, item.case_key, item.evidence_owner_ticker)
        == (route, case, owner)
    )


def test_nvda_reporting_fy2027_projects_to_2026_document_index_year() -> None:
    policy, bundles, requests = _compiled()
    bundle_map = {bundle.bundle_id: bundle for bundle in bundles}
    sql = _request(requests, route="internal_sql_exact", case="NVDA", owner="NVDA")
    lexical = _request(requests, route="internal_bm25", case="NVDA", owner="NVDA")
    dense = _request(requests, route="internal_milvus_dense", case="NVDA", owner="NVDA")
    assert sql.typed_filters["reporting_fiscal_years"] == [2027]
    assert lexical.typed_filters["index_filing_calendar_years"] == [2026]
    assert dense.typed_filters["years"] == [2026]
    assert all("fiscal_years" not in item.typed_filters for item in (sql, lexical, dense))
    for item in (sql, lexical, dense):
        validate_internal_route_request(item, bundles=bundle_map, policy=policy)


def test_dell_mixed_reporting_years_collapse_to_one_index_calendar_year() -> None:
    _, _, requests = _compiled()
    request = _request(requests, route="internal_object_bm25", case="DELL", owner="DELL")
    assert request.typed_filters["reporting_fiscal_years"] == [2027, 2026]
    assert request.typed_filters["index_filing_calendar_years"] == [2026]


def test_candidate_executors_consume_route_specific_period_authority(tmp_path: Path) -> None:
    _, _, requests = _compiled()
    sql = _request(requests, route="internal_sql_exact", case="NVDA", owner="NVDA")
    import sqlite3

    database = tmp_path / "gold.sqlite"
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE gold_fact_signal_mart (gold_row_id TEXT,ticker TEXT,"
        "metric_family TEXT,metric_name TEXT,value TEXT,unit TEXT,period TEXT,"
        "fiscal_year TEXT,authority_mode TEXT,claim_boundary TEXT,citation_url TEXT,"
        "citation_span TEXT,evidence_ref TEXT,source_url TEXT,published_at TEXT,"
        "period_role TEXT,period_start TEXT,period_end TEXT,"
        "can_enter_evidence_bundle INTEGER,exact_value_authority INTEGER)"
    )
    connection.execute(
        "INSERT INTO gold_fact_signal_mart VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "nvda_fy2027",
            "NVDA",
            "revenue",
            "Revenue",
            "1",
            "USD",
            "Q1 FY2027",
            "2027",
            "exact",
            "boundary",
            "https://example.test/nvda",
            "span",
            "evidence",
            "https://example.test/nvda",
            "2026-05-20",
            "quarterly",
            "2026-01-01",
            "2026-04-30",
            1,
            1,
        ),
    )
    connection.commit()
    connection.close()
    assert execute_sql_exact_request(sql.as_dict(), database=database)["candidate_count"] == 1

    lexical = _request(requests, route="internal_bm25", case="NVDA", owner="NVDA")

    class Retriever:
        def __init__(self) -> None:
            self.filters: list[dict] = []

        def search(self, query: str, *, top_k: int, filters: dict) -> list[dict]:
            self.filters.append(filters)
            return []

    retriever = Retriever()
    execute_bm25_request(lexical.as_dict(), retriever=retriever)
    assert retriever.filters
    assert all(item["fiscal_year"] == [2026] for item in retriever.filters)


def test_document_routes_partition_period_authority_by_form_semantics() -> None:
    _, _, requests = _compiled()
    lexical = _request(requests, route="internal_bm25", case="NVDA", owner="NVDA")

    class Retriever:
        def __init__(self) -> None:
            self.filters: list[dict] = []

        def search(self, query: str, *, top_k: int, filters: dict) -> list[dict]:
            self.filters.append(filters)
            return []

    retriever = Retriever()
    terminal = execute_bm25_request(
        lexical.as_dict(),
        retriever=retriever,
        temporal_filter_policy={
            "mode": "form_semantic_partition_v1",
            "reporting_period_forms": ["10-K", "10-Q", "20-F", "40-F"],
            "filing_calendar_event_forms": ["8-K", "6-K"],
        },
    )
    periodic = [
        item
        for item in retriever.filters
        if item["form_type"] == ["10-K", "10-Q", "20-F"]
    ]
    event = [
        item for item in retriever.filters if item["form_type"] == ["6-K", "8-K"]
    ]
    assert len(periodic) == len(lexical.query_texts)
    assert len(event) == len(lexical.query_texts)
    assert all(item["fiscal_year"] == [2027] for item in periodic)
    assert all(item["fiscal_year"] == [2026] for item in event)
    assert terminal["search_lane_count"] == len(lexical.query_texts) * 2
    assert {
        item["partition_id"] for item in terminal["temporal_filter_partitions"]
    } == {"periodic_reporting_fiscal_year", "event_filing_calendar_year"}


def test_document_route_unknown_form_semantics_fail_closed() -> None:
    _, _, requests = _compiled()
    lexical = _request(requests, route="internal_bm25", case="NVDA", owner="NVDA")
    body = lexical.as_dict()
    body["typed_filters"]["form_types"] = ["10-Q", "PRESS-RELEASE"]

    class Retriever:
        def search(self, query: str, *, top_k: int, filters: dict) -> list[dict]:
            raise AssertionError("unclassified forms must fail before retrieval")

    with pytest.raises(
        S1InternalCandidateCeilingError,
        match="internal_candidate_ceiling_temporal_form_unclassified:PRESS-RELEASE",
    ):
        execute_bm25_request(
            body,
            retriever=Retriever(),
            temporal_filter_policy={
                "mode": "form_semantic_partition_v1",
                "reporting_period_forms": ["10-K", "10-Q", "20-F", "40-F"],
                "filing_calendar_event_forms": ["8-K", "6-K"],
            },
        )


def test_object_candidate_recovers_bound_source_lineage() -> None:
    _, _, requests = _compiled()
    request = _request(
        requests,
        route="internal_object_bm25",
        case="NVDA",
        owner="NVDA",
    )

    class Retriever:
        def search(self, query: str, *, top_k: int, filters: dict) -> list[dict]:
            if filters["form_type"] != ["10-K", "10-Q", "20-F"]:
                return []
            record = {
                "object_id": "NVDA_2027_10Q_ITEM1A_BLOCK_0001_CLAIM_A",
                "object_type": "claim",
                "source_evidence_id": "NVDA_2027_10Q_ITEM1A_BLOCK_0001",
                "ticker": "NVDA",
                "fiscal_year": 2027,
                "form_type": "10-Q",
                "source_type": "10-Q",
                "source_tier": "primary_sec_filing",
                "preview": "Export controls and purchase commitments.",
            }
            return [
                {
                    "rank": 1,
                    "score": 4.0,
                    "object_id": record["object_id"],
                    "object_type": "claim",
                    "ticker": "NVDA",
                    "fiscal_year": 2027,
                    "preview": record["preview"],
                    "record": record,
                }
            ]

    terminal = execute_object_bm25_request(
        request.as_dict(),
        retriever=Retriever(),
        temporal_filter_policy={
            "mode": "form_semantic_partition_v1",
            "reporting_period_forms": ["10-K", "10-Q", "20-F", "40-F"],
            "filing_calendar_event_forms": ["8-K", "6-K"],
        },
        document_lineage_lookup={
            "by_accession": {},
            "by_ticker_year_form": {
                ("NVDA", 2027, "10-Q"): [
                    {
                        "ticker": "NVDA",
                        "form_type": "10-Q",
                        "fiscal_year": 2027,
                        "accession_number": "000104581026000052",
                        "source_url": "https://www.sec.gov/example/nvda-q1-fy2027",
                        "published_at": "2026-05-20",
                        "manifest_ref": "manifests/nvda.jsonl",
                    }
                ]
            },
        },
    )
    assert terminal["candidate_count"] == 1
    candidate = terminal["candidates"][0]
    assert candidate["published_at"] == "2026-05-20"
    assert candidate["source_url"] == "https://www.sec.gov/example/nvda-q1-fy2027"
    assert candidate["source_accession_number"] == "000104581026000052"
    assert candidate["lineage_resolution_method"] == (
        "unique_ticker_reporting_year_form"
    )


def test_earnings_release_child_object_uses_exhibit_url_not_parent_8k() -> None:
    _, _, requests = _compiled()
    request = _request(
        requests,
        route="internal_object_bm25",
        case="DELL",
        owner="NVDA",
    )

    source_id = (
        "8K_EARNINGS::NVDA::000104581026000051::Q1FY27PRHTM::"
        "BLOCK_0003::CHUNK_0001"
    )

    class Retriever:
        def search(self, query: str, *, top_k: int, filters: dict) -> list[dict]:
            if set(filters["form_type"]) != {"8-K", "6-K"}:
                return []
            record = {
                "object_id": f"{source_id}_CLAIM_TEST",
                "object_type": "claim",
                "source_evidence_id": source_id,
                "ticker": "NVDA",
                "fiscal_year": 2026,
                "form_type": "8-K",
                "source_type": "8-K",
                "source_url": "https://www.sec.gov/example/parent-8k.htm",
                "preview": "Third-party manufacturing reliance.",
            }
            return [
                {
                    "rank": 1,
                    "score": 4.0,
                    "object_id": record["object_id"],
                    "object_type": "claim",
                    "ticker": "NVDA",
                    "fiscal_year": 2026,
                    "preview": record["preview"],
                    "record": record,
                }
            ]

    terminal = execute_object_bm25_request(
        request.as_dict(),
        retriever=Retriever(),
        temporal_filter_policy={
            "mode": "form_semantic_partition_v1",
            "reporting_period_forms": ["10-K", "10-Q", "20-F", "40-F"],
            "filing_calendar_event_forms": ["8-K", "6-K"],
        },
        document_lineage_lookup={
            "by_accession": {
                "000104581026000051": [
                    {
                        "ticker": "NVDA",
                        "form_type": "8-K",
                        "fiscal_year": 2026,
                        "accession_number": "000104581026000051",
                        "source_url": "https://www.sec.gov/example/parent-8k.htm",
                        "exhibit_url": "https://www.sec.gov/example/exhibit-99-1.htm",
                        "published_at": "2026-05-20",
                        "manifest_ref": "manifests/nvda-8k.jsonl",
                    }
                ]
            },
            "by_ticker_year_form": {},
        },
    )

    candidate = terminal["candidates"][0]
    assert candidate["source_url"] == (
        "https://www.sec.gov/example/exhibit-99-1.htm"
    )
    assert candidate["lineage_resolution_method"] == "exact_accession_exhibit"


def test_ambiguous_period_filter_mutation_fails_closed() -> None:
    policy, bundles, requests = _compiled()
    original = _request(requests, route="internal_bm25", case="NVDA", owner="NVDA")
    body = original.as_dict()
    body["typed_filters"]["fiscal_years"] = [2027]
    body.pop("request_id")
    body.pop("request_digest")
    digest = canonical_digest(body)
    mutated = replace(
        original,
        request_id=f"internal_route_request_{digest[:20]}",
        request_digest=digest,
        typed_filters=body["typed_filters"],
    )
    with pytest.raises(
        S1InternalQueryFacetError, match="internal_route_request_typed_filter_drift"
    ):
        validate_internal_route_request(
            mutated,
            bundles={bundle.bundle_id: bundle for bundle in bundles},
            policy=policy,
        )


def test_milvus_lite_directory_storage_is_a_valid_locator(tmp_path: Path) -> None:
    directory_db = tmp_path / "milvus_lite.db"
    directory_db.mkdir()
    assert milvus_lite_storage_exists(directory_db) is True
    assert milvus_lite_storage_exists(tmp_path / "missing.db") is False


def test_milvus_qualification_loads_collection_before_ticker_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bm25 = tmp_path / "bm25"
    objects = tmp_path / "objects"
    deps = tmp_path / "deps"
    model = tmp_path / "model"
    db = tmp_path / "milvus.db"
    for directory in (bm25, objects, deps, model, db):
        directory.mkdir()
    (bm25 / "bm25.pkl").write_bytes(b"x")
    (bm25 / "records.jsonl").write_text("", encoding="utf-8")
    (bm25 / "metadata.json").write_text('{"records": 1}', encoding="utf-8")
    (objects / "records.sqlite").write_bytes(b"x")
    (objects / "metadata.json").write_text('{"records": 1}', encoding="utf-8")
    (model / "config.json").write_text('{"hidden_size": 1024}', encoding="utf-8")

    gold = tmp_path / "gold.sqlite"
    graph = tmp_path / "graph.sqlite"
    import sqlite3

    connection = sqlite3.connect(gold)
    connection.execute("CREATE TABLE gold_fact_signal_mart (id TEXT)")
    connection.commit()
    connection.close()
    connection = sqlite3.connect(graph)
    connection.execute("CREATE TABLE research_graph_nodes (id TEXT)")
    connection.execute("CREATE TABLE research_graph_edges (id TEXT)")
    connection.execute("CREATE TABLE research_graph_evidence_support (id TEXT)")
    connection.commit()
    connection.close()

    runtime = tmp_path / "milvus.json"
    runtime.write_text(
        json.dumps(
            {
                "db_path": db.as_posix(),
                "embedding_model": model.as_posix(),
                "collection_name": "collection",
                "vector_count": 5,
            }
        ),
        encoding="utf-8",
    )

    events: list[str] = []

    class FakeClient:
        def __init__(self, *, uri: str) -> None:
            assert uri == str(db)

        def list_collections(self) -> list[str]:
            return ["collection"]

        def describe_collection(self, name: str) -> dict:
            assert name == "collection"
            fields = [
                {"name": item, "params": {"dim": 1024} if item == "embedding" else {}}
                for item in (
                    "vector_id",
                    "embedding",
                    "evidence_id",
                    "ticker",
                    "fiscal_year",
                    "form_type",
                    "source_tier",
                    "vector_kind",
                    "object_type",
                    "preview",
                )
            ]
            return {"fields": fields}

        def get_collection_stats(self, name: str) -> dict:
            assert name == "collection"
            return {"row_count": 5}

        def load_collection(self, *, collection_name: str) -> None:
            assert collection_name == "collection"
            events.append("load")

        def query(self, **_: object) -> list[dict]:
            assert events == ["load"]
            events.append("query")
            events.pop()
            return [{"ticker": "x"}]

        def release_collection(self, *, collection_name: str) -> None:
            assert collection_name == "collection"
            events.append("release")

    class FakeModule:
        MilvusClient = FakeClient

    monkeypatch.setitem(sys.modules, "pymilvus", FakeModule())
    policy = {
        "local_assets": {
            "bm25_index_dir": bm25.relative_to(tmp_path).as_posix(),
            "object_bm25_index_dir": objects.relative_to(tmp_path).as_posix(),
            "gold_sqlite": gold.relative_to(tmp_path).as_posix(),
            "relationship_graph_sqlite": graph.relative_to(tmp_path).as_posix(),
            "milvus_dependencies_dir": deps.as_posix(),
            "local_embedding_model_candidates": [model.as_posix()],
        },
        "immutable_inputs": {"milvus_runtime_ref": runtime.relative_to(tmp_path).as_posix()},
        "resource_qualification": {
            "required_milvus_fields": [
                "vector_id",
                "embedding",
                "evidence_id",
                "ticker",
                "fiscal_year",
                "form_type",
                "source_tier",
                "vector_kind",
                "object_type",
                "preview",
            ],
            "expected_embedding_dim": 1024,
        },
    }
    checks = qualify_local_assets(policy=policy, repo_root=tmp_path)
    assert checks["milvus_dense"]["status"] == "qualified"
    assert checks["milvus_dense"]["db_storage_kind"] == "directory"
    assert checks["milvus_dense"]["ticker_presence"] == {
        "DELL": True,
        "MSFT": True,
        "MU": True,
        "NVDA": True,
        "TSM": True,
    }
    assert events == ["load", "release"]
