from __future__ import annotations

import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.official_source_attempt_program import (
    OfficialSourceAttemptError,
    SourceResponse,
)
from sec_agent.s1_08_candidate_generation_runtime import (
    DiscoveryCandidate,
    DiscoveryQuery,
    canonical_digest,
)
from sec_agent.s1_08_candidate_generation_runtime_v4 import (
    CACHE_LINEAGE_SCHEMA,
    CATALOG_SCHEMA_V4,
    CONTRACT_REF_V4,
    RESULT_SCHEMA_V4,
    compile_initial_queries_v4,
    load_source_catalog_v4,
    run_candidate_generation_v4,
)
from sec_agent.s1_08_official_discovery_adapter_v4 import (
    ProtectedFetchOfficialDiscoveryAdapterV4,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_V3 = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
)
CATALOG_V4 = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_08_current_source_catalog_protected_fetch_cache_policy_v4_0.json"
)
R3_RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_08_v3_dell_current_search_r3_result_v1_0.json"
)
R3_EVALUATION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_08_v3_dell_current_search_r3_source_quality_evaluation_v1_0.json"
)
V3_RUNTIME = ROOT / "src/sec_agent/s1_08_candidate_generation_runtime.py"
V3_ADAPTER = ROOT / "src/sec_agent/s1_08_official_discovery_adapter.py"
R3_CAPTURE_ROOT = ROOT / (
    ".codex_runtime/fin013_s1_08_v3_dell_current_search_r3/"
    "fin013_s1_08_dell_r3_admission_a3f1c96343823f83883b/adapter/objects/"
    "fin-0.1.3/s1-08/current-source-discovery"
)
IMMUTABLE_SHA256 = {
    CATALOG_V3: "90b2adf15d6e25c10a4f918b0ba8f5894684aaf6a0f478eec55a941d815ba851",
    R3_RESULT: "731885330176f1d3a428ed3cdf62315e34c345f457ba39b749d60802d9c6b1d5",
    R3_EVALUATION: "b8af0d6e6a573ce2365d544972bfb74bbdf6ba8927c4a29f1d33cae8a6b6c5f2",
    V3_RUNTIME: "441718f5818a4eace201af19cb7a10edbb2a373ad4603376337f43aecda15f42",
    V3_ADAPTER: "aa55bc8f60591fab12d20fc271e705908afb91df093a5a56d529f490774fc294",
}


def _objective(case_key: str) -> str:
    return (
        f"Evaluate {case_key} current demand, value capture, counterevidence, "
        "supply constraints and market context."
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _query(catalog: dict, *, role_id: str) -> DiscoveryQuery:
    return next(
        row
        for row in compile_initial_queries_v4(
            catalog=catalog,
            case_key="DELL",
            research_objective=_objective("DELL"),
        )
        if row.role_id == role_id
    )


class _DirectDocumentTransport:
    live_network = True

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        self.calls.append(url)
        if url == "https://investors.delltechnologies.com/":
            return SourceResponse(
                status_code=200,
                final_url=url,
                headers={"content-type": "text/html"},
                body=b"""<html><body><a data-date="2026-07-29"
                href="/earnings/q2-results">Dell earnings results revenue
                financial prepared remarks</a></body></html>""",
            )
        if url == "https://investors.delltechnologies.com/earnings/q2-results":
            return SourceResponse(
                status_code=200,
                final_url=url,
                headers={"content-type": "text/html"},
                body=b"""<html><body><h1>Dell earnings results</h1>
                <p>ROUND ROCK, Texas - July 29, 2026 - Dell Technologies
                reported financial revenue results and prepared remarks for its
                current infrastructure business, including demand and supply
                observations for enterprise customers.</p></body></html>""",
            )
        raise AssertionError(f"unexpected protected-fetch request: {url}")


class _StructuredTopologyTransport:
    live_network = True

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        self.calls.append(url)
        if url == "https://investors.delltechnologies.com/":
            return SourceResponse(
                status_code=200,
                final_url=url,
                headers={"content-type": "text/html"},
                body=b"<html><body>Dell investor relations landing</body></html>",
            )
        if url == "https://investors.delltechnologies.com/robots.txt":
            return SourceResponse(
                status_code=200,
                final_url=url,
                headers={"content-type": "text/plain"},
                body=(
                    b"User-agent: *\nSitemap: "
                    b"https://investors.delltechnologies.com/news-sitemap.xml\n"
                ),
            )
        if url == "https://investors.delltechnologies.com/news-sitemap.xml":
            return SourceResponse(
                status_code=200,
                final_url=url,
                headers={"content-type": "application/xml"},
                body=b"""<?xml version="1.0"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                  <url><loc>https://investors.delltechnologies.com/earnings/q2-results</loc>
                  <lastmod>2026-07-29</lastmod></url>
                </urlset>""",
            )
        if url == "https://investors.delltechnologies.com/earnings/q2-results":
            return SourceResponse(
                status_code=200,
                final_url=url,
                headers={"content-type": "text/html"},
                body=b"""<html><body><h1>Dell earnings results</h1>
                <p>ROUND ROCK, Texas - July 29, 2026 - Dell Technologies
                reported financial revenue, infrastructure demand and prepared
                remarks with supply observations for enterprise customers.</p>
                </body></html>""",
            )
        raise AssertionError(f"unexpected topology request: {url}")


class _SingleDocumentTransport:
    live_network = True

    def __init__(self, *, failure_code: str = "", parser_failure: bool = False) -> None:
        self.calls: list[str] = []
        self.failure_code = failure_code
        self.parser_failure = parser_failure

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        self.calls.append(url)
        if self.failure_code:
            raise OfficialSourceAttemptError(self.failure_code)
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": "text/html"},
            body=(
                b"<html></html>"
                if self.parser_failure
                else b"<html><body>July 29, 2026 Dell earnings financial "
                b"results revenue demand capacity and prepared remarks for "
                b"enterprise infrastructure customers with supply context.</body></html>"
            ),
        )


def _capture(name: str) -> tuple[str, str]:
    return f"capture/{name}", canonical_digest({"capture": name})


def _candidate(query: DiscoveryQuery, *, mutation: str = "") -> DiscoveryCandidate:
    owner = query.entity_keys[0]
    discovery_ref, discovery_digest = _capture(
        f"{query.case_key}/{query.role_id}/discovery"
    )
    source_ref, source_digest = _capture(f"{query.case_key}/{query.role_id}/source")
    parser_ref, parser_digest = _capture(f"{query.case_key}/{query.role_id}/parser")
    is_market = query.role_id == "market_expectation_context"
    is_regulatory = query.role_id == "regulatory_risk_and_financial_reconciliation"
    row = DiscoveryCandidate(
        case_key=query.case_key,
        target_key=query.target_key,
        role_id=query.role_id,
        entity_key=owner,
        title=f"{query.case_key} official current {query.role_id}",
        locator=(
            "current_market_snapshot"
            if is_market
            else f"https://example.com/{query.case_key}/{query.role_id}"
        ),
        published_on="2026-08-06" if is_market else "2026-07-29",
        authority=(
            "non_authoritative_market_context"
            if is_market
            else "regulatory_primary"
            if is_regulatory
            else "issuer_primary"
            if owner == query.case_key
            else "industry_primary"
        ),
        discovery_capture_ref=discovery_ref,
        discovery_capture_digest=discovery_digest,
        source_capture_ref=source_ref,
        source_capture_digest=source_digest,
        parser_capture_ref=parser_ref,
        parser_capture_digest=parser_digest,
        evidence_slot_id=query.evidence_slot_id,
        source_family=(
            "market_context"
            if is_market
            else "regulatory_filing"
            if is_regulatory
            else "issuer_ir_document"
        ),
        content_quality_score=90,
        subject_entity=query.subject_entity,
        evidence_owner_entity=owner,
        ecosystem_role=query.allowed_source_owner_roles[0],
        claim_direction=query.claim_direction,
        publication_date_kind=(
            "as_of_date" if is_market else "filing_date" if is_regulatory else "published_date"
        ),
        publication_date_source=(
            "governed_local_snapshot_as_of"
            if is_market
            else "SEC_submissions_filingDate"
            if is_regulatory
            else "official_release_masthead"
        ),
        publication_date_confidence="high",
        publication_date_conflict_status="none",
    )
    if mutation == "identity" and query.role_id == "issuer_results_and_management_commentary":
        row = replace(row, case_key="MU")
    elif mutation == "currentness" and query.role_id == "issuer_results_and_management_commentary":
        row = replace(row, published_on="2026-08-07")
    elif mutation == "relationship" and query.role_id == "issuer_results_and_management_commentary":
        row = replace(row, subject_entity="MU")
    elif mutation == "numeric" and query.role_id == "issuer_results_and_management_commentary":
        row = replace(row, authority="exact_numeric_authority")
    elif mutation == "lineage" and query.role_id == "issuer_results_and_management_commentary":
        row = replace(row, parser_capture_digest="bad")
    return row


class _V4FullFakeAdapter:
    def __init__(self, *, mutation: str = "") -> None:
        self.mutation = mutation
        self.network_calls = 0
        self.document_fetches = 0
        self.qualified_locator_fetch_opportunities = 0
        self.pre_request_local_stop_cross_attempt_cache_entries = 0
        self.receipts: list[dict] = []
        self.checkpoint_refs: list[dict] = []
        self.cache_lineage: list[dict] = []
        self._state: dict = {}

    def prepare_attempt(
        self,
        *,
        query: DiscoveryQuery,
        network_call_allowance: int,
        maximum_document_fetches: int,
        protected_document_fetches: int,
    ) -> None:
        self._state = {
            "query_digest": query.query_digest,
            "network_call_allowance": network_call_allowance,
            "network_calls_started": 0,
            "discovery_call_ceiling": network_call_allowance - protected_document_fetches,
            "discovery_calls_started": 0,
            "protected_document_fetch_allowance": protected_document_fetches,
            "document_fetch_ceiling": maximum_document_fetches,
            "document_fetches_started": 0,
        }

    def current_attempt_budget_state(self) -> dict:
        return dict(self._state)

    def discover(self, query: DiscoveryQuery) -> tuple[DiscoveryCandidate, ...]:
        if query.role_id != "market_expectation_context":
            if self._state["network_call_allowance"] < 2:
                return ()
            self.network_calls += 2
            self.document_fetches += 1
            self.qualified_locator_fetch_opportunities += 1
            self._state.update(
                {
                    "network_calls_started": 2,
                    "discovery_calls_started": 1,
                    "document_fetches_started": 1,
                }
            )
            self.cache_lineage.append(
                {
                    "schema_version": CACHE_LINEAGE_SCHEMA,
                    "event": "cache_write",
                    "cache_scope": "cross_attempt_document_cache",
                    "remote_outcome_kind": "captured_remote_success",
                    "parser_outcome_kind": "parser_succeeded",
                }
            )
        return (_candidate(query, mutation=self.mutation),)

    def persist_candidate_checkpoint(self, snapshot) -> None:
        self.checkpoint_refs.append(
            {
                "object_key": f"checkpoint/{len(self.checkpoint_refs)}",
                "digest": canonical_digest(snapshot),
            }
        )


class _V4PermutationAdapter(_V4FullFakeAdapter):
    def __init__(self, *, reverse: bool) -> None:
        super().__init__()
        self.reverse = reverse

    def discover(self, query: DiscoveryQuery) -> tuple[DiscoveryCandidate, ...]:
        rows = list(super().discover(query))
        if query.role_id != "issuer_results_and_management_commentary":
            return tuple(rows)
        first = replace(
            rows[0],
            locator="https://example.com/a",
            source_capture_ref="capture/source/a",
            source_capture_digest=canonical_digest({"source": "a"}),
        )
        second = replace(
            rows[0],
            locator="https://example.com/b",
            source_capture_ref="capture/source/b",
            source_capture_digest=canonical_digest({"source": "b"}),
        )
        ordered = [first, second]
        if self.reverse:
            ordered.reverse()
        return tuple(ordered)


def test_v4_is_a_true_successor_and_all_v3_r3_evidence_is_byte_stable() -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    assert catalog["schema_version"] == CATALOG_SCHEMA_V4
    assert catalog["contract_ref"] == CONTRACT_REF_V4
    assert catalog["budgets"]["replacement_network_call_ceiling"] == 16
    assert catalog["budgets"]["protected_document_fetch"] == {
        "minimum_opportunities_per_eligible_attempt": 1,
        "discovery_must_leave_protected_capacity": True,
        "all_real_requests_share_global_ceiling": True,
        "pre_request_local_stop_cross_attempt_cacheable": False,
        "cache_lineage_schema": CACHE_LINEAGE_SCHEMA,
    }
    assert {path: _sha256(path) for path in IMMUTABLE_SHA256} == IMMUTABLE_SHA256


@pytest.mark.parametrize("allowance", [2, 3, 4])
def test_qualified_locator_gets_document_fetch_under_allowance_permutations(
    tmp_path: Path, allowance: int
) -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    query = replace(
        _query(catalog, role_id="issuer_results_and_management_commentary"),
        route_ids=("issuer_ir_discovery",),
    )
    transport = _DirectDocumentTransport()
    adapter = ProtectedFetchOfficialDiscoveryAdapterV4(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=16,
        document_ceiling_per_query=2,
    )
    adapter.prepare_attempt(
        query=query,
        network_call_allowance=allowance,
        maximum_document_fetches=2,
        protected_document_fetches=1,
    )
    candidates = adapter.discover(query)
    assert len(candidates) == 1
    assert transport.calls == [
        "https://investors.delltechnologies.com/",
        "https://investors.delltechnologies.com/earnings/q2-results",
    ]
    assert adapter.document_fetches == 1
    assert adapter.qualified_locator_fetch_opportunities == 1
    assert adapter.current_attempt_budget_state()["network_calls_started"] == 2


def test_landing_robots_sitemap_document_topology_preserves_one_document_call(
    tmp_path: Path,
) -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    query = replace(
        _query(catalog, role_id="issuer_results_and_management_commentary"),
        route_ids=("issuer_ir_discovery", "official_ir_feed_discovery"),
    )
    transport = _StructuredTopologyTransport()
    adapter = ProtectedFetchOfficialDiscoveryAdapterV4(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=16,
        document_ceiling_per_query=2,
    )
    adapter.prepare_attempt(
        query=query,
        network_call_allowance=4,
        maximum_document_fetches=2,
        protected_document_fetches=1,
    )
    assert len(adapter.discover(query)) == 1
    assert transport.calls == [
        "https://investors.delltechnologies.com/",
        "https://investors.delltechnologies.com/robots.txt",
        "https://investors.delltechnologies.com/news-sitemap.xml",
        "https://investors.delltechnologies.com/earnings/q2-results",
    ]
    state = adapter.current_attempt_budget_state()
    assert state["discovery_calls_started"] == 3
    assert state["document_fetches_started"] == 1
    assert state["network_calls_started"] == 4


def test_landing_local_stop_does_not_poison_successor_attempt(
    tmp_path: Path,
) -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    query = replace(
        _query(catalog, role_id="issuer_results_and_management_commentary"),
        route_ids=("issuer_ir_discovery",),
    )
    transport = _DirectDocumentTransport()
    adapter = ProtectedFetchOfficialDiscoveryAdapterV4(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=16,
    )
    adapter.prepare_attempt(
        query=query,
        network_call_allowance=1,
        maximum_document_fetches=2,
        protected_document_fetches=1,
    )
    assert adapter.discover(query) == ()
    assert transport.calls == []
    assert adapter._landing_cache == {}

    successor = replace(query, query_digest=canonical_digest({"landing": 2}))
    adapter.prepare_attempt(
        query=successor,
        network_call_allowance=2,
        maximum_document_fetches=2,
        protected_document_fetches=1,
    )
    assert len(adapter.discover(successor)) == 1
    assert transport.calls == [
        "https://investors.delltechnologies.com/",
        "https://investors.delltechnologies.com/earnings/q2-results",
    ]
    assert any(
        row.get("cache_kind") == "landing_discovery_cache"
        and row["event"] == "not_cached"
        for row in adapter.cache_lineage
    )


def test_nested_structured_local_stop_does_not_cache_partial_landing(
    tmp_path: Path,
) -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    query = replace(
        _query(catalog, role_id="issuer_results_and_management_commentary"),
        route_ids=("issuer_ir_discovery", "official_ir_feed_discovery"),
    )
    transport = _StructuredTopologyTransport()
    adapter = ProtectedFetchOfficialDiscoveryAdapterV4(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=16,
    )
    adapter.prepare_attempt(
        query=query,
        network_call_allowance=2,
        maximum_document_fetches=2,
        protected_document_fetches=1,
    )
    assert adapter.discover(query) == ()
    assert transport.calls == ["https://investors.delltechnologies.com/"]
    assert adapter._landing_cache == {}
    assert adapter._structured_cache == {}

    successor = replace(query, query_digest=canonical_digest({"structured": 2}))
    adapter.prepare_attempt(
        query=successor,
        network_call_allowance=4,
        maximum_document_fetches=2,
        protected_document_fetches=1,
    )
    assert len(adapter.discover(successor)) == 1
    assert transport.calls == [
        "https://investors.delltechnologies.com/",
        "https://investors.delltechnologies.com/",
        "https://investors.delltechnologies.com/robots.txt",
        "https://investors.delltechnologies.com/news-sitemap.xml",
        "https://investors.delltechnologies.com/earnings/q2-results",
    ]
    cache_kinds = {
        row.get("cache_kind")
        for row in adapter.cache_lineage
        if row["event"] == "not_cached"
    }
    assert cache_kinds == {
        "landing_discovery_cache",
        "structured_discovery_cache",
    }


def test_pre_request_stop_is_attempt_local_and_cannot_poison_later_slot(
    tmp_path: Path,
) -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    query = _query(catalog, role_id="issuer_results_and_management_commentary")
    url = "https://investors.delltechnologies.com/earnings/q2-results"
    transport = _SingleDocumentTransport()
    adapter = ProtectedFetchOfficialDiscoveryAdapterV4(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=16,
    )
    adapter.prepare_attempt(
        query=query,
        network_call_allowance=0,
        maximum_document_fetches=2,
        protected_document_fetches=0,
    )
    first = adapter._fetch_and_parse(url, query=query)
    assert first[0] is None
    assert first[1]["status"] == "local_stop"
    assert transport.calls == []
    assert adapter._document_cache_v4 == {}

    second_query = replace(query, query_digest=canonical_digest({"successor": 2}))
    adapter.prepare_attempt(
        query=second_query,
        network_call_allowance=1,
        maximum_document_fetches=2,
        protected_document_fetches=1,
    )
    second = adapter._fetch_and_parse(url, query=second_query)
    assert second[0] is not None
    assert second[1]["status"] == "captured"
    assert transport.calls == [url]
    assert adapter.pre_request_local_stop_cross_attempt_cache_entries == 0
    assert [row["event"] for row in adapter.cache_lineage] == [
        "not_cached",
        "cache_write",
    ]
    assert adapter.cache_lineage[0]["cache_scope"] == "attempt_local_noncacheable"


def test_captured_remote_failure_is_typed_and_reused_without_retry(
    tmp_path: Path,
) -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    query = _query(catalog, role_id="issuer_results_and_management_commentary")
    url = "https://investors.delltechnologies.com/earnings/q2-results"
    transport = _SingleDocumentTransport(
        failure_code="official_source_transport_failed"
    )
    adapter = ProtectedFetchOfficialDiscoveryAdapterV4(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=16,
    )
    for ordinal in (1, 2):
        current = replace(query, query_digest=canonical_digest({"attempt": ordinal}))
        adapter.prepare_attempt(
            query=current,
            network_call_allowance=1,
            maximum_document_fetches=2,
            protected_document_fetches=1,
        )
        assert adapter._fetch_and_parse(url, query=current)[0] is None
    assert transport.calls == [url]
    assert [row["event"] for row in adapter.cache_lineage] == [
        "cache_write",
        "cache_hit",
    ]
    assert all(
        row["remote_outcome_kind"] == "captured_remote_failure"
        and row["parser_outcome_kind"] == "not_run"
        for row in adapter.cache_lineage
    )


def test_parser_failure_has_distinct_typed_lineage_and_is_not_reparsed(
    tmp_path: Path,
) -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    query = _query(catalog, role_id="issuer_results_and_management_commentary")
    url = "https://investors.delltechnologies.com/earnings/q2-results"
    transport = _SingleDocumentTransport(parser_failure=True)
    adapter = ProtectedFetchOfficialDiscoveryAdapterV4(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=16,
    )
    for ordinal in (1, 2):
        current = replace(query, query_digest=canonical_digest({"parser": ordinal}))
        adapter.prepare_attempt(
            query=current,
            network_call_allowance=1,
            maximum_document_fetches=2,
            protected_document_fetches=1,
        )
        response, attempt, parser_ref, _ = adapter._fetch_and_parse(
            url, query=current
        )
        assert response is not None
        assert attempt["status"] == "captured"
        assert parser_ref is None
    assert transport.calls == [url]
    assert [row["event"] for row in adapter.cache_lineage] == [
        "cache_write",
        "cache_hit",
    ]
    assert all(
        row["remote_outcome_kind"] == "captured_remote_success"
        and row["parser_outcome_kind"] == "parser_failed"
        for row in adapter.cache_lineage
    )


@pytest.mark.parametrize(
    "failure_code",
    ["source_request_cancelled_before_start", "source_local_timeout_before_start"],
)
def test_cancel_or_local_timeout_before_request_is_never_cross_attempt_cached(
    tmp_path: Path, monkeypatch, failure_code: str
) -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    query = _query(catalog, role_id="issuer_results_and_management_commentary")
    url = "https://investors.delltechnologies.com/earnings/q2-results"
    adapter = ProtectedFetchOfficialDiscoveryAdapterV4(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=_SingleDocumentTransport(),
        network_call_ceiling=16,
    )
    monkeypatch.setattr(
        adapter,
        "_fetch",
        lambda **_: (
            None,
            {
                "status": "local_stop",
                "failure_code": failure_code,
                "request_capture": {},
                "response_capture": {},
                "request_started": False,
                "cache_scope": "attempt_local_noncacheable",
            },
        ),
    )
    assert adapter._fetch_and_parse(url, query=query)[0] is None
    assert adapter._document_cache_v4 == {}
    assert adapter.cache_lineage[-1] == {
        "schema_version": CACHE_LINEAGE_SCHEMA,
        "event": "not_cached",
        "cache_scope": "attempt_local_noncacheable",
        "locator_digest": canonical_digest(url),
        "remote_outcome_kind": "pre_request_local_stop",
        "parser_outcome_kind": "not_run",
        "origin_query_digest": query.query_digest,
        "origin_evidence_slot_id": query.evidence_slot_id,
        "failure_code": failure_code,
        "request_started": False,
    }


@pytest.mark.parametrize("case_key", ["DELL", "MU", "NVDA"])
def test_v4_three_case_full_fake_closes_slots_with_fixed_global_ceiling(
    case_key: str,
) -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    adapter = _V4FullFakeAdapter()
    result = run_candidate_generation_v4(
        catalog=catalog,
        case_key=case_key,
        research_objective=_objective(case_key),
        adapter=adapter,
    )
    assert result["schema_version"] == RESULT_SCHEMA_V4
    assert result["contract_ref"] == CONTRACT_REF_V4
    assert result["terminal_status"] == "complete"
    assert result["typed_gaps"] == []
    assert result["observed_counts"]["network_calls"] == 8
    assert result["observed_counts"]["network_calls"] <= 16
    assert result["observed_counts"]["accepted_candidates"] == 5
    assert result["quality_metrics"]["slot_starvation_count"] == 0
    assert result["quality_metrics"][
        "pre_request_local_stop_cross_attempt_cache_entries"
    ] == 0
    assert all(
        row["protected_document_fetch_allowance"] == 1
        for row in result["attempts"]
        if row["slot_budget_group"] != "market_context"
    )
    assert result["adapter_cache_lineage"]


def test_v4_locator_permutation_keeps_deterministic_candidate_selection() -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    results = [
        run_candidate_generation_v4(
            catalog=catalog,
            case_key="DELL",
            research_objective=_objective("DELL"),
            adapter=_V4PermutationAdapter(reverse=reverse),
        )
        for reverse in (False, True)
    ]
    selected = [
        next(
            row
            for row in result["accepted_candidates"]
            if row["role_id"] == "issuer_results_and_management_commentary"
        )["locator"]
        for result in results
    ]
    assert selected == ["https://example.com/a", "https://example.com/a"]
    assert all(
        any(
            "accepted_unique_document_attempt_ceiling_reached" in row["reason_codes"]
            for row in result["rejected_candidates"]
        )
        for result in results
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("identity", "cross_case_candidate"),
        ("currentness", "candidate_after_as_of"),
        ("relationship", "relationship_binding_mismatch"),
        ("numeric", "source_authority_binding_invalid"),
        ("lineage", "capture_first_lineage_invalid"),
    ],
)
def test_v4_identity_currentness_relationship_numeric_and_lineage_mutations_fail_closed(
    mutation: str, expected_code: str
) -> None:
    catalog = load_source_catalog_v4(CATALOG_V4)
    result = run_candidate_generation_v4(
        catalog=catalog,
        case_key="DELL",
        research_objective=_objective("DELL"),
        adapter=_V4FullFakeAdapter(mutation=mutation),
    )
    reason_codes = {
        code
        for row in result["rejected_candidates"]
        for code in row["reason_codes"]
    }
    assert expected_code in reason_codes
    assert any(
        row["evidence_slot_id"] == "issuer_results_and_management_commentary"
        for row in result["typed_gaps"]
    )


@pytest.mark.requires_local_data
def test_immutable_r3_capture_replay_reaches_document_after_natural_route_topology(
    tmp_path: Path,
) -> None:
    if not R3_CAPTURE_ROOT.exists():
        pytest.skip("immutable R3 capture store unavailable")
    request_by_digest: dict[str, dict] = {}
    outcome_by_request_digest: dict[str, dict] = {}
    for path in R3_CAPTURE_ROOT.rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("capture_kind") == "source_request":
            request_by_digest[path.stem] = payload
        elif payload.get("capture_kind") in {
            "source_response",
            "source_transport_failure",
        }:
            outcome_by_request_digest[str(payload["request_capture_digest"])] = payload
    replay_by_url = {
        str(request["url"]): outcome_by_request_digest[digest]
        for digest, request in request_by_digest.items()
        if digest in outcome_by_request_digest
    }
    assert len(request_by_digest) == 13
    assert len(outcome_by_request_digest) == 13

    class _R3CaptureTopologyReplayTransport:
        live_network = True

        def __init__(self) -> None:
            self.calls: list[str] = []
            self.synthetic_document_calls: list[str] = []

        def fetch(
            self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling
        ):
            self.calls.append(url)
            captured = replay_by_url.get(url)
            if captured is not None:
                if captured["capture_kind"] == "source_transport_failure":
                    raise OfficialSourceAttemptError(str(captured["failure_code"]))
                return SourceResponse(
                    status_code=int(captured["status_code"]),
                    final_url=str(captured["final_url"]),
                    headers=dict(captured.get("headers") or {}),
                    body=base64.b64decode(captured["body_base64"]),
                    redirect_chain=tuple(captured.get("redirect_chain") or ()),
                )
            self.synthetic_document_calls.append(url)
            return SourceResponse(
                status_code=200,
                final_url=url,
                headers={"content-type": "text/html"},
                body=b"""<html><body><h1>Microsoft infrastructure update</h1>
                <p>REDMOND, Wash. - July 29, 2026 - Microsoft Azure described
                AI infrastructure and data center capacity deployment, customer
                demand and capital expenditure metrics for current operations.
                This official update includes more than enough substantive text
                for the bounded replay parser.</p></body></html>""",
            )

    catalog = load_source_catalog_v4(CATALOG_V4)
    query = _query(
        catalog, role_id="customer_demand_and_deployment_validation"
    )
    transport = _R3CaptureTopologyReplayTransport()
    adapter = ProtectedFetchOfficialDiscoveryAdapterV4(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=16,
        document_ceiling_per_query=2,
    )
    adapter.prepare_attempt(
        query=query,
        network_call_allowance=4,
        maximum_document_fetches=2,
        protected_document_fetches=1,
    )
    adapter.discover(query)
    assert transport.calls[0] == "https://www.microsoft.com/en-us/investor/"
    assert all(url in replay_by_url for url in transport.calls[:-1])
    assert len(transport.synthetic_document_calls) == 1
    assert adapter.document_fetches == 1
    assert adapter.qualified_locator_fetch_opportunities >= 1
    assert adapter.current_attempt_budget_state() == {
        "query_digest": query.query_digest,
        "network_call_allowance": 4,
        "network_calls_started": 4,
        "discovery_call_ceiling": 3,
        "discovery_calls_started": 3,
        "protected_document_fetch_allowance": 1,
        "document_fetch_ceiling": 2,
        "document_fetches_started": 1,
    }
    assert adapter.pre_request_local_stop_cross_attempt_cache_entries == 0
