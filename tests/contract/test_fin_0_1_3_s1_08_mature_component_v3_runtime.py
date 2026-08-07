from __future__ import annotations

import base64
from dataclasses import replace
from importlib.metadata import version
import json
from pathlib import Path

import pytest

from sec_agent.official_source_attempt_program import SourceResponse
from sec_agent.s1_08_candidate_generation_runtime import (
    DiscoveryCandidate,
    DiscoveryQuery,
    canonical_digest,
    compile_initial_queries,
    load_source_catalog,
    run_candidate_generation,
)
from sec_agent.s1_08_official_content_tools import (
    extract_publication_date,
    parse_feed_capture,
    parse_official_html_capture,
    parse_robots_capture,
    parse_sitemap_capture,
)
from sec_agent.s1_08_official_discovery_adapter import (
    CaptureFirstOfficialDiscoveryAdapter,
    _sec_submission_locators,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_V2 = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v2_0.json"
)
CATALOG_V3 = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
)
R2_OBJECT_ROOT = ROOT / (
    ".codex_runtime/fin013_s1_08_dell_current_search_r2/"
    "fin013_s1_08_dell_r2_admission_3de480abf1cfd6db5037/adapter/objects/"
    "fin-0.1.3/s1-08/current-source-discovery"
)


def _objective(case_key: str) -> str:
    return (
        f"Evaluate {case_key} current demand, value capture, counterevidence, "
        "supply constraints and market context."
    )


def _capture(name: str) -> tuple[str, str]:
    return f"capture/{name}", canonical_digest({"capture": name})


def _candidate(
    query: DiscoveryQuery,
    *,
    suffix: str,
    locator: str | None = None,
    entity_key: str | None = None,
    source_capture: tuple[str, str] | None = None,
    score: int = 80,
) -> DiscoveryCandidate:
    owner = entity_key or query.entity_keys[0]
    discovery_ref, discovery_digest = _capture(f"{suffix}/discovery")
    source_ref, source_digest = source_capture or _capture(f"{suffix}/source")
    parser_ref, parser_digest = _capture(f"{suffix}/parser")
    is_market = query.role_id == "market_expectation_context"
    source_family = (
        "market_context"
        if is_market
        else "regulatory_filing"
        if query.role_id == "regulatory_risk_and_financial_reconciliation"
        else "issuer_ir_document"
    )
    return DiscoveryCandidate(
        case_key=query.case_key,
        target_key=query.target_key,
        role_id=query.role_id,
        entity_key=owner,
        title=f"Official current evidence {suffix}",
        locator=(
            locator
            or (
                "current_market_snapshot"
                if is_market
                else f"https://example.com/{suffix}"
            )
        ),
        published_on="2026-08-06" if is_market else "2026-07-29",
        authority=(
            "non_authoritative_market_context"
            if is_market
            else "issuer_primary"
        ),
        discovery_capture_ref=discovery_ref,
        discovery_capture_digest=discovery_digest,
        source_capture_ref=source_ref,
        source_capture_digest=source_digest,
        parser_capture_ref=parser_ref,
        parser_capture_digest=parser_digest,
        evidence_slot_id=query.evidence_slot_id,
        source_family=source_family,
        content_quality_score=score,
        subject_entity=query.subject_entity,
        evidence_owner_entity=owner,
        ecosystem_role=query.allowed_source_owner_roles[0],
        claim_direction=query.claim_direction,
        publication_date_kind=(
            "as_of_date"
            if is_market
            else "filing_date"
            if source_family == "regulatory_filing"
            else "published_date"
        ),
        publication_date_source=(
            "governed_local_snapshot_as_of"
            if is_market
            else "SEC_submissions_filingDate"
            if source_family == "regulatory_filing"
            else "official_release_masthead"
        ),
        publication_date_confidence="high",
        publication_date_conflict_status="none",
    )


class _RoundRobinAdapter:
    def __init__(self, *, reverse_issuer_candidates: bool = False) -> None:
        self.network_calls = 0
        self.receipts: list[dict] = []
        self.prepared: list[dict] = []
        self._allowance = 0
        self.reverse_issuer_candidates = reverse_issuer_candidates

    def prepare_attempt(
        self,
        *,
        query: DiscoveryQuery,
        network_call_allowance: int,
        maximum_document_fetches: int,
    ) -> None:
        self._allowance = network_call_allowance
        self.prepared.append(
            {
                "role_id": query.role_id,
                "revision": query.revision,
                "allowance": network_call_allowance,
                "maximum_document_fetches": maximum_document_fetches,
            }
        )

    def discover(self, query: DiscoveryQuery) -> tuple[DiscoveryCandidate, ...]:
        if query.role_id != "market_expectation_context":
            if self._allowance <= 0:
                return ()
            self.network_calls += 1
        if query.role_id == "issuer_results_and_management_commentary":
            rows = [
                _candidate(
                    query,
                    suffix=f"{query.case_key}/issuer/a",
                    locator="https://example.com/a",
                    score=80,
                ),
                _candidate(
                    query,
                    suffix=f"{query.case_key}/issuer/b",
                    locator="https://example.com/b",
                    score=80,
                ),
            ]
            if self.reverse_issuer_candidates:
                rows.reverse()
            return tuple(rows)
        return (
            _candidate(
                query,
                suffix=f"{query.case_key}/{query.role_id}/{query.revision}",
            ),
        )


class _SharedSourceAdapter(_RoundRobinAdapter):
    def discover(self, query: DiscoveryQuery) -> tuple[DiscoveryCandidate, ...]:
        if query.role_id != "market_expectation_context":
            if self._allowance <= 0:
                return ()
            self.network_calls += 1
        if query.role_id in {
            "issuer_results_and_management_commentary",
            "regulatory_risk_and_financial_reconciliation",
        }:
            shared = _capture(f"{query.case_key}/shared/source")
            return (
                _candidate(
                    query,
                    suffix=f"{query.case_key}/{query.role_id}",
                    locator="https://example.com/shared-report",
                    source_capture=shared,
                ),
            )
        return (
            _candidate(query, suffix=f"{query.case_key}/{query.role_id}"),
        )


def test_mature_component_versions_are_pinned_to_selected_major_lines() -> None:
    assert version("feedparser").startswith("6.")
    assert version("trafilatura").startswith("2.")


def test_v2_queries_remain_free_of_v3_relationship_contract_fields() -> None:
    catalog = load_source_catalog(CATALOG_V2)
    queries = compile_initial_queries(
        catalog=catalog,
        case_key="DELL",
        research_objective=_objective("DELL"),
    )
    serialized = json.dumps([row.as_dict() for row in queries], sort_keys=True)
    for field in (
        "subject_entity",
        "claim_direction",
        "allowed_source_owner_roles",
        "slot_budget_group",
    ):
        assert field not in serialized


@pytest.mark.parametrize("case_key", ["DELL", "MU", "NVDA"])
def test_v3_three_case_round_robin_full_fake_has_no_slot_starvation(
    case_key: str,
) -> None:
    catalog = load_source_catalog(CATALOG_V3)
    adapter = _RoundRobinAdapter()
    result = run_candidate_generation(
        catalog=catalog,
        case_key=case_key,
        research_objective=_objective(case_key),
        adapter=adapter,
    )
    assert result["terminal_status"] == "complete"
    assert result["typed_gaps"] == []
    assert result["observed_counts"]["accepted_candidates"] == 5
    assert result["observed_counts"]["network_calls"] == 4
    assert result["quality_metrics"]["slot_starvation_count"] == 0
    assert result["slot_budget_summary"]["first_attempt_order"] == [
        "issuer_results_and_management_commentary",
        "regulatory_risk_and_financial_reconciliation",
        "customer_demand_and_deployment_validation",
        "supply_chain_capacity_and_counterevidence",
        "market_expectation_context",
    ]
    assert all(row["maximum_document_fetches"] == 2 for row in adapter.prepared)
    assert result["observed_counts"]["model_calls"] == 0
    assert result["observed_counts"]["provider_calls"] == 0


def test_candidate_permutation_is_stable_and_unique_attempt_ceiling_is_enforced() -> None:
    catalog = load_source_catalog(CATALOG_V3)
    forward = _RoundRobinAdapter(reverse_issuer_candidates=False)
    reverse = _RoundRobinAdapter(reverse_issuer_candidates=True)
    first = run_candidate_generation(
        catalog=catalog,
        case_key="DELL",
        research_objective=_objective("DELL"),
        adapter=forward,
    )
    second = run_candidate_generation(
        catalog=catalog,
        case_key="DELL",
        research_objective=_objective("DELL"),
        adapter=reverse,
    )
    first_issuer = next(
        row
        for row in first["accepted_candidates"]
        if row["role_id"] == "issuer_results_and_management_commentary"
    )
    second_issuer = next(
        row
        for row in second["accepted_candidates"]
        if row["role_id"] == "issuer_results_and_management_commentary"
    )
    assert first_issuer["locator"] == second_issuer["locator"] == "https://example.com/a"
    assert any(
        "accepted_unique_document_attempt_ceiling_reached" in row["reason_codes"]
        for row in second["rejected_candidates"]
    )


def test_same_canonical_source_bound_to_two_roles_counts_once() -> None:
    result = run_candidate_generation(
        catalog=load_source_catalog(CATALOG_V3),
        case_key="DELL",
        research_objective=_objective("DELL"),
        adapter=_SharedSourceAdapter(),
    )
    assert result["quality_metrics"]["role_bindings_with_candidate"] == 5
    assert result["quality_metrics"]["accepted_unique_source_documents"] == 3
    assert result["quality_metrics"]["governed_local_source_bindings"] == 1


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing_subject", "relationship_binding_mismatch"),
        ("wrong_owner", "relationship_binding_mismatch"),
        ("untyped_date", "typed_publication_date_binding_invalid"),
    ],
)
def test_v3_relationship_and_date_mutations_fail_closed(
    mutation: str, expected_code: str
) -> None:
    catalog = load_source_catalog(CATALOG_V3)

    class _MutationAdapter(_RoundRobinAdapter):
        def discover(self, query: DiscoveryQuery) -> tuple[DiscoveryCandidate, ...]:
            if query.role_id != "market_expectation_context":
                if self._allowance <= 0:
                    return ()
                self.network_calls += 1
            row = _candidate(query, suffix=f"mutation/{query.role_id}/{query.revision}")
            if query.role_id == "issuer_results_and_management_commentary":
                if mutation == "missing_subject":
                    row = replace(row, subject_entity="")
                elif mutation == "wrong_owner":
                    row = replace(row, evidence_owner_entity="MSFT")
                elif mutation == "untyped_date":
                    row = replace(
                        row,
                        publication_date_source="trafilatura_inferred_date",
                        publication_date_confidence="low",
                    )
            return (row,)

    result = run_candidate_generation(
        catalog=catalog,
        case_key="DELL",
        research_objective=_objective("DELL"),
        adapter=_MutationAdapter(),
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


def test_fin_date_adjudicator_rejects_reporting_period_and_selects_release_masthead() -> None:
    html = """
    <html><body>
      <p>Revenue for the quarter ended June 30, 2026 was reported.</p>
      <p>REDMOND, Wash. — July 29, 2026 — Microsoft today announced results.</p>
    </body></html>
    """
    decision = extract_publication_date(
        html_text=html,
        final_url="https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release",
        headers={},
        as_of="2026-08-06",
        capture_ref="capture/release",
        capture_digest=canonical_digest({"capture": "release"}),
        trafilatura_date="2026-06-30",
    )
    assert decision.date_value == "2026-07-29"
    assert decision.date_source == "official_release_masthead"
    assert decision.date_confidence == "high"
    assert decision.conflict_status == "none"
    assert any(
        row.date_value == "2026-06-30"
        and row.date_kind == "reporting_period_end"
        and row.date_confidence == "rejected"
        for row in decision.candidates
    )


def test_low_confidence_library_date_cannot_become_financial_date_authority() -> None:
    decision = extract_publication_date(
        html_text="<html><body>Results and financial commentary.</body></html>",
        final_url="https://example.com/results",
        headers={},
        as_of="2026-08-06",
        capture_ref="capture/untyped",
        capture_digest=canonical_digest({"capture": "untyped"}),
        trafilatura_date="2026-07-01",
    )
    assert decision.date_value == ""
    assert decision.conflict_status == "publication_date_unproven"


def test_conflicting_high_authority_publication_dates_fail_closed() -> None:
    decision = extract_publication_date(
        html_text="""
        <html><head>
          <meta property="article:published_time" content="2026-07-29" />
          <script type="application/ld+json">{"datePublished":"2026-07-30"}</script>
        </head><body>Official results</body></html>
        """,
        final_url="https://example.com/results",
        headers={},
        as_of="2026-08-06",
        capture_ref="capture/conflict",
        capture_digest=canonical_digest({"capture": "conflict"}),
    )
    assert decision.date_value == ""
    assert decision.conflict_status == "publication_date_conflict"


def test_feed_sitemap_and_robots_parse_saved_bytes_without_network() -> None:
    feed_rows = parse_feed_capture(
        body=b"""<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Quarterly results</title><link>https://investor.example.com/results/q2</link>
        <pubDate>Wed, 29 Jul 2026 12:00:00 GMT</pubDate></item>
        <item><title>Cross domain</title><link>https://evil.example.net/result</link></item>
        </channel></rss>""",
        base_url="https://investor.example.com/feed.xml",
        allowed_hosts=("investor.example.com",),
    )
    assert [(row.url, row.published_on) for row in feed_rows] == [
        ("https://investor.example.com/results/q2", "2026-07-29")
    ]
    assert parse_feed_capture(
        body=b"not a feed",
        base_url="https://investor.example.com/feed.xml",
        allowed_hosts=("investor.example.com",),
    ) == ()

    sitemap_rows = parse_sitemap_capture(
        body=b"""<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://investor.example.com/results/q2</loc><lastmod>2026-07-30</lastmod></url>
          <url><loc>https://evil.example.net/result</loc></url>
        </urlset>""",
        base_url="https://investor.example.com/sitemap.xml",
        allowed_hosts=("investor.example.com",),
    )
    assert len(sitemap_rows) == 1
    assert sitemap_rows[0].published_on == ""
    assert sitemap_rows[0].date_kind == "modified_date"
    assert sitemap_rows[0].endpoint_kind == "document"

    index_rows = parse_sitemap_capture(
        body=b"""<?xml version="1.0"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://investor.example.com/news-sitemap.xml</loc></sitemap>
        </sitemapindex>""",
        base_url="https://investor.example.com/sitemap.xml",
        allowed_hosts=("investor.example.com",),
    )
    assert index_rows[0].endpoint_kind == "sitemap"
    robots_rows = parse_robots_capture(
        body=b"User-agent: *\nSitemap: https://investor.example.com/sitemap.xml\n",
        base_url="https://investor.example.com/robots.txt",
        allowed_hosts=("investor.example.com",),
    )
    assert [row.url for row in robots_rows] == [
        "https://investor.example.com/sitemap.xml"
    ]


def test_sec_submission_discovery_includes_foreign_issuer_20f_and_6k() -> None:
    response = SourceResponse(
        status_code=200,
        final_url="https://data.sec.gov/submissions/CIK0001046179.json",
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "cik": "0001046179",
                "filings": {
                    "recent": {
                        "accessionNumber": [
                            "0001046179-26-000001",
                            "0001046179-26-000002",
                            "0001046179-26-000003",
                        ],
                        "filingDate": ["2026-04-18", "2026-07-18", "2026-07-19"],
                        "form": ["20-F", "6-K", "424B5"],
                        "primaryDocument": ["tsm-20f.htm", "tsm-6k.htm", "prospectus.htm"],
                    }
                },
            }
        ).encode(),
    )
    rows = _sec_submission_locators(
        response,
        {"object_key": "capture/sec", "digest": canonical_digest({"sec": 1})},
    )
    assert {row.form_type for row in rows} == {"20-F", "6-K"}
    assert all(row.date_kind == "filing_date" for row in rows)


class _RelationshipTransport:
    live_network = False

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        self.calls.append(url)
        if url != "https://www.microsoft.com/en-us/investor/":
            raise AssertionError(f"relationship gate should prevent document fetch: {url}")
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": "text/html"},
            body=b"""<html><body><a data-date="2026-07-29"
            href="/en-us/customers/contoso-ai-infrastructure">
            Customer AI infrastructure capacity deployment and capital expenditure
            </a></body></html>""",
        )


def test_nested_customer_story_is_rejected_before_document_fetch(tmp_path: Path) -> None:
    catalog = load_source_catalog(CATALOG_V3)
    query = next(
        row
        for row in compile_initial_queries(
            catalog=catalog,
            case_key="DELL",
            research_objective=_objective("DELL"),
        )
        if row.role_id == "customer_demand_and_deployment_validation"
    )
    query = replace(query, route_ids=("issuer_ir_discovery",))
    transport = _RelationshipTransport()
    adapter = CaptureFirstOfficialDiscoveryAdapter(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=4,
        document_ceiling_per_query=2,
    )
    assert adapter.discover(query) == ()
    assert transport.calls == ["https://www.microsoft.com/en-us/investor/"]
    assert any(
        "nested_customer_relationship_direction_invalid" in row.get("reason_codes", [])
        for row in adapter.receipts
    )


class _DocumentCeilingTransport:
    live_network = False

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        self.calls.append(url)
        if url == "https://investors.delltechnologies.com/":
            links = "".join(
                f'<a data-date="2026-07-29" href="/earnings/{letter}">'
                f'Dell earnings results revenue {letter}</a>'
                for letter in ("a", "b", "c")
            )
            return SourceResponse(
                status_code=200,
                final_url=url,
                headers={"content-type": "text/html"},
                body=f"<html><body>{links}</body></html>".encode(),
            )
        if url in {
            "https://investors.delltechnologies.com/earnings/a",
            "https://investors.delltechnologies.com/earnings/b",
        }:
            return SourceResponse(
                status_code=200,
                final_url=url,
                headers={"content-type": "text/html"},
                body=b"<html><body>thin</body></html>",
            )
        raise AssertionError(f"document ceiling should stop before: {url}")


def test_document_fetch_ceiling_is_real_not_only_an_acceptance_ceiling(
    tmp_path: Path,
) -> None:
    catalog = load_source_catalog(CATALOG_V3)
    query = next(
        row
        for row in compile_initial_queries(
            catalog=catalog,
            case_key="DELL",
            research_objective=_objective("DELL"),
        )
        if row.role_id == "issuer_results_and_management_commentary"
    )
    query = replace(query, route_ids=("issuer_ir_discovery",))
    transport = _DocumentCeilingTransport()
    adapter = CaptureFirstOfficialDiscoveryAdapter(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=5,
        document_ceiling_per_query=10,
    )
    adapter.prepare_attempt(
        query=query,
        network_call_allowance=4,
        maximum_document_fetches=2,
    )
    assert adapter.discover(query) == ()
    assert adapter.document_fetches == 2
    assert transport.calls == [
        "https://investors.delltechnologies.com/",
        "https://investors.delltechnologies.com/earnings/a",
        "https://investors.delltechnologies.com/earnings/b",
    ]
    assert any(
        row.get("code") == "document_fetch_ceiling_reached"
        for row in adapter.receipts
    )


@pytest.mark.requires_local_data
def test_actual_immutable_dell_r2_microsoft_captures_recover_financial_dates() -> None:
    cases = (
        (
            "1b16c1d89b47e5c20f1ef20ee021f1c166fb938ca94faf0d2bd87c2326c1294c",
            "94e5a8f806f03fa13a2d94107b6a32a6bfe6a10090eb41adc5f84ba3fb5f7b8a",
            "2026-07-29",
            "official_event_heading",
        ),
        (
            "7306f99976f05c7bca0574148d0c12ed6e4bac55a3f71f22237960b6973062cb",
            "9bcb8759d663b50b91245b5f2bc4f8e0362bccf9aa83fe83fceb155621aa0995",
            "2026-07-29",
            "official_release_masthead",
        ),
    )
    if not R2_OBJECT_ROOT.exists():
        pytest.skip("immutable local DELL R2 capture store is unavailable")
    parsed_rows = []
    for object_digest, body_digest, expected_date, expected_source in cases:
        path = (
            R2_OBJECT_ROOT
            / object_digest[:2]
            / object_digest[2:4]
            / f"{object_digest}.json"
        )
        if not path.exists():
            pytest.skip(f"immutable local capture missing: {object_digest}")
        capture = json.loads(path.read_text(encoding="utf-8"))
        assert capture["body_sha256"] == body_digest
        parsed = parse_official_html_capture(
            body=base64.b64decode(capture["body_base64"]),
            final_url=capture["final_url"],
            headers=capture["headers"],
            as_of="2026-08-06",
            capture_ref=str(path.relative_to(ROOT)).replace("\\", "/"),
            capture_digest=object_digest,
        )
        assert parsed.publication_date.date_value == expected_date
        assert parsed.publication_date.date_source == expected_source
        assert parsed.publication_date.conflict_status == "none"
        parsed_rows.append(parsed)
    assert any(
        row.date_value == "2026-06-30"
        and row.date_kind == "reporting_period_end"
        for row in parsed_rows[1].publication_date.candidates
    )
