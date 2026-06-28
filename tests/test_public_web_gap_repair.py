from __future__ import annotations

from typing import Any

from sec_agent.lead_supervision import build_lead_review_checkpoint, build_research_objective_contract, build_targeted_repair_plan
from sec_agent.langgraph_orchestrator import _lead_targeted_repair_context_claims, _state_with_lead_targeted_repair
from sec_agent.official_issuer_repair import execute_official_issuer_repair_plan


def test_targeted_repair_plan_classifies_web_gap_types_and_carries_probe_inputs() -> None:
    repair = _sample_repair_plan()
    by_type = {row["repair_type"]: row for row in repair["repairs"]}

    assert repair["validation"]["status"] == "pass"
    assert {"product_surface", "capital_ownership", "supply_chain"} <= set(by_type)
    assert by_type["product_surface"]["route"] == "official_product_surface_repair"
    assert by_type["product_surface"]["official_product_urls"] == ["https://www.asml.com/en/products"]
    assert by_type["product_surface"]["official_product_surfaces"] == ["EUV lithography systems"]
    assert by_type["capital_ownership"]["route"] == "capital_ownership_repair"
    assert by_type["capital_ownership"]["offering_urls"] == ["https://www.sec.gov/Archives/edgar/data/937966/sample-8k.htm"]
    assert by_type["supply_chain"]["route"] == "official_supply_chain_repair"
    assert by_type["supply_chain"]["supply_chain_urls"] == ["https://www.asml.com/en/company/suppliers"]


def test_scoped_public_web_repair_executes_multiple_gap_types_and_materializes_claims() -> None:
    repair = _sample_repair_plan()

    def fake_fetch(url: str) -> tuple[int, str, str]:
        if "asml.com/en/products" in url:
            return (
                200,
                "text/html",
                """
                <title>ASML products</title>
                <meta name='description' content='EUV lithography systems and DUV lithography systems.'>
                <h1>EUV lithography systems</h1>
                <p>The NXE:3800E platform supports high-volume EUV production with improved throughput.</p>
                <table>
                  <tr><th>Model</th><th>Specification</th></tr>
                  <tr><td>NXE:3800E</td><td>throughput platform context</td></tr>
                </table>
                """,
            )
        if "sec.gov/Archives" in url:
            return 200, "text/html", "<title>ASML 8-K</title>Offering and ownership context for parser targeting."
        if "asml.com/en/company/suppliers" in url:
            return 200, "text/html", "<title>ASML suppliers</title>Official supplier and partner context."
        raise AssertionError(url)

    execution = execute_official_issuer_repair_plan(repair, fetch=fake_fetch, max_probes_per_issuer=10)
    repair_types = {row.get("repair_type") for row in execution["context_rows"] if isinstance(row, dict)}
    claims = _lead_targeted_repair_context_claims(execution)
    claim_types = {row.get("claim_type") for row in claims}

    assert execution["status"] == "pass"
    assert execution["attempted_count"] >= 3
    assert {"product_surface", "capital_ownership", "supply_chain"} <= repair_types
    assert {"product_taxonomy_context", "capital_structure_or_ownership_context", "supply_chain_relationship_context"} <= claim_types
    assert all(row["exact_value_authority"] is False for row in execution["context_rows"])
    assert all(row["evidence_graph_status"] == "runtime_ready_context" for row in execution["context_rows"])
    product_rows = [row for row in execution["context_rows"] if row.get("repair_type") == "product_surface"]
    capital_rows = [row for row in execution["context_rows"] if row.get("repair_type") == "capital_ownership"]
    assert product_rows and {row["source_layer_id"] for row in product_rows} == {"L2"}
    assert capital_rows and {row["source_layer_id"] for row in capital_rows} <= {"L1", "L2"}
    assert all(row["can_support_company_exact_fact"] is False for row in execution["context_rows"])
    structured_rows = [
        row
        for row in execution["context_rows"]
        if row.get("structured_fact_status") == "bounded_context_fact_materialized"
    ]
    assert structured_rows
    assert all(row["source_specific_parser"] == "public_web_context_parser_v0_1" for row in structured_rows)
    assert any(row.get("structured_context_type") == "product_spec_context" for row in structured_rows)
    assert any("does not promote exact sales" in row["claim"] for row in claims if row["claim_type"] == "product_taxonomy_context")
    assert any("bounded parsed context includes" in row["claim"] for row in claims if row["claim_type"] == "product_taxonomy_context")
    assert any("exact amount" in row["claim"] for row in claims if row["claim_type"] == "capital_structure_or_ownership_context")


def test_public_web_repair_parses_l3_market_proxy_table_without_exact_promotion() -> None:
    plan = {
        "schema_version": "finsight_targeted_repair_plan_v0_1",
        "status": "ready",
        "repairs": [
            {
                "repair_id": "repair:market_proxy:fixture",
                "dimension": "competition_and_market_position",
                "repair_type": "market_proxy",
                "route": "public_market_proxy_repair",
                "ticker": "AAPL",
                "web_search_allowed": True,
                "web_scope_policy_ids": ["official_statistics_or_industry_dataset_only"],
                "allowed_source_classes": ["public_market_proxy_snapshot"],
                "probe_urls": ["https://example.com/public-market-proxy"],
                "market_source_class": "public_market_proxy_snapshot",
                "not_found_gap": {"gap_type": "bounded_gap_after_public_market_proxy_probe"},
            }
        ],
    }

    def fake_fetch(url: str) -> tuple[int, str, str]:
        return (
            200,
            "text/html",
            """
            <title>Public market proxy</title>
            <table>
              <tr><th>Vendor</th><th>Rank</th><th>Share proxy</th></tr>
              <tr><td>AAPL</td><td>2</td><td>public ranking context only</td></tr>
            </table>
            """,
        )

    execution = execute_official_issuer_repair_plan(plan, fetch=fake_fetch, max_probes_per_issuer=3)
    structured_rows = [
        row
        for row in execution["context_rows"]
        if row.get("structured_fact_status") == "bounded_context_fact_materialized"
    ]

    assert execution["status"] == "pass"
    assert structured_rows
    assert {row["source_layer_id"] for row in structured_rows} == {"L3"}
    assert all(row["exact_value_authority"] is False for row in structured_rows)
    assert all(row["can_support_company_exact_fact"] is False for row in structured_rows)
    assert any(row["structured_context_type"] == "market_proxy_table_context" for row in structured_rows)
    claims = _lead_targeted_repair_context_claims(execution)
    assert any(row["claim_type"] == "market_or_competitive_context" for row in claims)


def test_targeted_repair_plan_preserves_l3_named_public_proxy_source_class() -> None:
    contract = build_research_objective_contract(
        query="分析 AAPL app 排名和开发者生态对产品竞争力的方向性信号",
        required_dimensions=["competition_and_market_position"],
    )
    checkpoint = build_lead_review_checkpoint(
        objective_contract=contract,
        gaps=[
            {
                "gap_id": "gap_app_store_proxy",
                "ticker": "AAPL",
                "analysis_dimension": "competition_and_market_position",
                "gap_type": "app_store_rank_or_review_proxy_missing",
                "app_store_urls": ["https://apps.apple.com/us/app/example/id1"],
                "market_source_class": "official_app_store_or_marketplace",
            }
        ],
        source_capability={"live_public_web_context": {"market": True}},
    )
    plan = build_targeted_repair_plan(checkpoint)
    repair = plan["repairs"][0]

    assert repair["route"] == "public_market_proxy_repair"
    assert repair["market_proxy_urls"] == ["https://apps.apple.com/us/app/example/id1"]
    assert repair["market_source_class"] == "official_app_store_or_marketplace"
    assert "official_app_store_or_marketplace" in repair["allowed_source_classes"]
    assert repair["claim_scope_boundary"].startswith("can support industry direction or market context")


def test_public_web_repair_expands_github_url_to_developer_ecosystem_api_context() -> None:
    plan = {
        "schema_version": "finsight_targeted_repair_plan_v0_1",
        "status": "ready",
        "repairs": [
            {
                "repair_id": "repair:developer:github",
                "dimension": "competition_and_market_position",
                "repair_type": "market_proxy",
                "route": "public_market_proxy_repair",
                "ticker": "MSFT",
                "web_search_allowed": True,
                "web_scope_policy_ids": ["official_statistics_or_industry_dataset_only"],
                "allowed_source_classes": ["developer_ecosystem_snapshot"],
                "probe_urls": ["https://github.com/microsoft/vscode"],
                "market_source_class": "developer_ecosystem_snapshot",
                "not_found_gap": {"gap_type": "bounded_gap_after_public_market_proxy_probe"},
            }
        ],
    }
    called_urls: list[str] = []

    def fake_fetch(url: str) -> tuple[int, str, str]:
        called_urls.append(url)
        assert url == "https://api.github.com/repos/microsoft/vscode"
        return (
            200,
            "application/json",
            '{"full_name":"microsoft/vscode","stargazers_count":180000,"forks_count":32000,"pushed_at":"2026-06-01T00:00:00Z"}',
        )

    execution = execute_official_issuer_repair_plan(plan, fetch=fake_fetch, max_probes_per_issuer=1)
    structured_rows = [
        row
        for row in execution["context_rows"]
        if row.get("structured_fact_status") == "bounded_context_fact_materialized"
    ]

    assert called_urls == ["https://api.github.com/repos/microsoft/vscode"]
    assert structured_rows
    assert {row["source_layer_id"] for row in structured_rows} == {"L3"}
    assert any(row["structured_context_type"] == "developer_ecosystem_context" for row in structured_rows)
    assert all(row["exact_value_authority"] is False for row in structured_rows)


def test_public_web_repair_expands_app_store_url_to_lookup_proxy_context() -> None:
    plan = {
        "schema_version": "finsight_targeted_repair_plan_v0_1",
        "status": "ready",
        "repairs": [
            {
                "repair_id": "repair:appstore:fixture",
                "dimension": "competition_and_market_position",
                "repair_type": "market_proxy",
                "route": "public_market_proxy_repair",
                "ticker": "AAPL",
                "web_search_allowed": True,
                "web_scope_policy_ids": ["official_statistics_or_industry_dataset_only"],
                "allowed_source_classes": ["official_app_store_or_marketplace"],
                "probe_urls": ["https://apps.apple.com/us/app/example/id123456789"],
                "market_source_class": "official_app_store_or_marketplace",
                "not_found_gap": {"gap_type": "bounded_gap_after_public_market_proxy_probe"},
            }
        ],
    }
    called_urls: list[str] = []

    def fake_fetch(url: str) -> tuple[int, str, str]:
        called_urls.append(url)
        assert url == "https://itunes.apple.com/lookup?id=123456789"
        return (
            200,
            "application/json",
            '{"resultCount":1,"results":[{"trackName":"Example App","averageUserRating":4.6,"userRatingCount":12000,"version":"5.4","currentVersionReleaseDate":"2026-05-01T00:00:00Z"}]}',
        )

    execution = execute_official_issuer_repair_plan(plan, fetch=fake_fetch, max_probes_per_issuer=1)
    structured_rows = [
        row
        for row in execution["context_rows"]
        if row.get("structured_fact_status") == "bounded_context_fact_materialized"
    ]

    assert called_urls == ["https://itunes.apple.com/lookup?id=123456789"]
    assert structured_rows
    assert {row["source_layer_id"] for row in structured_rows} == {"L3"}
    assert any(row["structured_context_type"] == "app_store_marketplace_context" for row in structured_rows)
    assert all(row["exact_value_authority"] is False for row in structured_rows)


def test_public_web_repair_parses_channel_offer_jsonld_without_sell_through_authority() -> None:
    plan = _l3_market_proxy_plan(
        source_class="channel_pricing_snapshot",
        url="https://reseller.example.com/product/server-gpu",
        ticker="NVDA",
    )

    def fake_fetch(url: str) -> tuple[int, str, str]:
        return (
            200,
            "text/html",
            """
            <html><head><script type="application/ld+json">
            {"@context":"https://schema.org","@type":"Product","name":"GPU Server X","sku":"GPU-SERVER-X",
             "offers":{"@type":"Offer","price":"12999","priceCurrency":"USD","availability":"https://schema.org/InStock"},
             "aggregateRating":{"@type":"AggregateRating","ratingValue":"4.7","reviewCount":"132"}}
            </script></head><body>GPU Server X channel offer.</body></html>
            """,
        )

    execution = execute_official_issuer_repair_plan(plan, fetch=fake_fetch, max_probes_per_issuer=1)
    structured_rows = _structured_rows(execution)

    assert structured_rows
    assert {row["source_layer_id"] for row in structured_rows} == {"L3"}
    assert any(row["structured_context_type"] == "channel_offer_context" for row in structured_rows)
    assert any(row["structured_context_type"] == "platform_review_ranking_context" for row in structured_rows)
    assert all(row["exact_value_authority"] is False for row in structured_rows)
    assert all("sell-through" in row["structured_context_summary"] or row["structured_context_type"] != "channel_offer_context" for row in structured_rows)


def test_public_web_repair_parses_job_posting_jsonld_as_hiring_proxy() -> None:
    plan = _l3_market_proxy_plan(
        source_class="job_posting_snapshot",
        url="https://jobs.example.com/ai-infra-engineer",
        ticker="MSFT",
    )

    def fake_fetch(url: str) -> tuple[int, str, str]:
        return (
            200,
            "text/html",
            """
            <script type="application/ld+json">
            {"@context":"https://schema.org","@type":"JobPosting","title":"Principal AI Infrastructure Engineer",
             "datePosted":"2026-06-01","jobLocation":{"@type":"Place","address":{"addressLocality":"Redmond","addressRegion":"WA","addressCountry":"US"}}}
            </script>
            """,
        )

    execution = execute_official_issuer_repair_plan(plan, fetch=fake_fetch, max_probes_per_issuer=1)
    structured_rows = _structured_rows(execution)

    assert structured_rows
    assert {row["source_layer_id"] for row in structured_rows} == {"L3"}
    assert any(row["structured_context_type"] == "hiring_signal_context" for row in structured_rows)
    assert all(row["exact_value_authority"] is False for row in structured_rows)


def test_public_web_repair_parses_tender_jsonld_as_public_order_lead_only() -> None:
    plan = _l3_market_proxy_plan(
        source_class="public_tender_or_contract_portal",
        url="https://procurement.example.gov/tender/123",
        ticker="DELL",
    )

    def fake_fetch(url: str) -> tuple[int, str, str]:
        return (
            200,
            "text/html",
            """
            <script type="application/ld+json">
            {"@context":"https://schema.org","@type":"CreativeWork","name":"AI server procurement tender",
             "identifier":"TENDER-123","datePublished":"2026-05-20","description":"Public tender award notice for AI servers."}
            </script>
            """,
        )

    execution = execute_official_issuer_repair_plan(plan, fetch=fake_fetch, max_probes_per_issuer=1)
    structured_rows = _structured_rows(execution)

    assert structured_rows
    assert {row["source_layer_id"] for row in structured_rows} == {"L3"}
    assert any(row["structured_context_type"] == "public_tender_contract_context" for row in structured_rows)
    assert all(row["exact_value_authority"] is False for row in structured_rows)
    assert any("not total company order or revenue authority" in row["structured_context_summary"] for row in structured_rows)


def test_public_web_repair_blocks_untrusted_mainstream_news_domain_before_fetch() -> None:
    plan = _l3_market_proxy_plan(
        source_class="mainstream_financial_news_article",
        url="https://randomblog.example.com/ai-server-demand",
        ticker="NVDA",
    )
    called_urls: list[str] = []

    def fake_fetch(url: str) -> tuple[int, str, str]:
        called_urls.append(url)
        return 200, "text/html", "<title>Untrusted news</title>"

    execution = execute_official_issuer_repair_plan(plan, fetch=fake_fetch, max_probes_per_issuer=1)

    assert called_urls == []
    assert execution["status"] == "bounded_gap"
    assert execution["attempted_count"] == 0
    assert execution["source_gaps"][0]["attempted_source_classes"] == []


def test_public_web_repair_parses_trusted_news_article_as_l2_context() -> None:
    plan = _l3_market_proxy_plan(
        source_class="mainstream_financial_news_article",
        url="https://www.reuters.com/technology/ai-server-demand-example-2026-06-01/",
        ticker="NVDA",
    )

    def fake_fetch(url: str) -> tuple[int, str, str]:
        return (
            200,
            "text/html",
            """
            <html><head>
              <title>AI server suppliers report demand context</title>
              <meta property="article:published_time" content="2026-06-01T12:00:00Z">
              <meta name="description" content="Industry sources reported stronger AI server demand and supply constraints.">
            </head><body>
              <p>Reuters reported that AI server demand remained elevated, while suppliers said component availability stayed tight.</p>
              <p>The article discussed customer demand and competitive positioning but did not provide issuer product revenue.</p>
            </body></html>
            """,
        )

    execution = execute_official_issuer_repair_plan(plan, fetch=fake_fetch, max_probes_per_issuer=1)
    structured_rows = _structured_rows(execution)

    assert execution["status"] == "pass"
    assert structured_rows
    assert {row["source_layer_id"] for row in structured_rows} == {"L2"}
    assert any(row["structured_context_type"] == "trusted_news_event_context" for row in structured_rows)
    assert all(row["exact_value_authority"] is False for row in structured_rows)
    assert any("no issuer exact financial or product KPI authority" in row["structured_context_summary"] for row in structured_rows)
    news_rows = [row for row in structured_rows if row["structured_context_type"] == "trusted_news_event_context"]
    assert news_rows[0]["issuer_binding_status"] == "repair_plan_ticker_bound_unverified_in_snapshot"
    assert news_rows[0]["entity_binding"]["source_entity_role"] == "trusted_event_or_industry_context"
    assert "does not promote" in news_rows[0]["entity_binding_claim_boundary"]


def test_public_web_repair_parses_supplier_customer_official_news_as_l2_context() -> None:
    plan = {
        "schema_version": "finsight_targeted_repair_plan_v0_1",
        "status": "ready",
        "repairs": [
            {
                "repair_id": "repair:supply-news:fixture",
                "dimension": "competition_and_market_position",
                "repair_type": "supply_chain",
                "route": "official_supply_chain_repair",
                "ticker": "DELL",
                "web_search_allowed": True,
                "web_scope_policy_ids": ["official_company_partner_supplier_customer_only"],
                "allowed_source_classes": ["supplier_customer_official_news"],
                "supply_chain_urls": ["https://partner.example.com/news/dell-ai-server-contract"],
                "supply_source_class": "supplier_customer_official_news",
                "not_found_gap": {"gap_type": "bounded_gap_after_official_supply_chain_probe"},
            }
        ],
    }

    def fake_fetch(url: str) -> tuple[int, str, str]:
        return (
            200,
            "text/html",
            """
            <html><head>
              <title>Partner announces customer deployment with Dell</title>
              <meta name="date" content="2026-05-20">
              <meta name="description" content="Official partner news describes a customer AI server deployment.">
            </head><body>
              <p>The official partner announcement described Dell as a supplier for a customer AI server deployment contract.</p>
              <p>This is relationship context and does not disclose shipment volume or allocation.</p>
            </body></html>
            """,
        )

    execution = execute_official_issuer_repair_plan(plan, fetch=fake_fetch, max_probes_per_issuer=1)
    structured_rows = _structured_rows(execution)

    assert execution["status"] == "pass"
    assert structured_rows
    assert {row["source_layer_id"] for row in structured_rows} == {"L2"}
    assert any(row["structured_context_type"] == "official_supply_chain_news_context" for row in structured_rows)
    assert all(row["exact_value_authority"] is False for row in structured_rows)
    assert any("no shipment, revenue, allocation, or order-volume authority" in row["structured_context_summary"] for row in structured_rows)
    supply_rows = [row for row in structured_rows if row["structured_context_type"] == "official_supply_chain_news_context"]
    assert supply_rows[0]["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert supply_rows[0]["counterparty_binding_status"] == "relationship_context_candidate"
    assert supply_rows[0]["entity_binding"]["source_entity_role"] == "supplier_customer_or_partner_context"


def test_scoped_public_web_repair_blocks_disallowed_domain_before_fetch() -> None:
    repair = {
        "schema_version": "finsight_targeted_repair_plan_v0_1",
        "status": "ready",
        "repairs": [
            {
                "repair_id": "repair:product:blocked",
                "dimension": "product_and_production",
                "repair_type": "product_surface",
                "route": "official_product_surface_repair",
                "ticker": "ASML",
                "web_search_allowed": True,
                "web_scope_policy_ids": ["official_product_surface_only"],
                "allowed_source_classes": ["company_product_page"],
                "official_product_urls": ["https://reddit.com/r/semiconductors"],
                "not_found_gap": {"gap_type": "bounded_gap_after_official_product_surface_probe"},
            }
        ],
    }
    called_urls: list[str] = []

    def fake_fetch(url: str) -> tuple[int, str, str]:
        called_urls.append(url)
        return 200, "text/html", "<title>blocked</title>"

    execution = execute_official_issuer_repair_plan(repair, fetch=fake_fetch)

    assert called_urls == []
    assert execution["status"] == "bounded_gap"
    assert execution["attempted_count"] == 0
    assert execution["source_gaps"][0]["gap_type"] == "bounded_gap_after_official_product_surface_probe"


def test_lead_targeted_repair_state_writes_context_claims_and_gap_register(monkeypatch) -> None:
    execution = {
        "schema_version": "finsight_public_web_gap_repair_execution_v0_2",
        "status": "pass",
        "attempted_count": 1,
        "success_count": 1,
        "bounded_gap_count": 1,
        "context_rows": [
            {
                "evidence_ref": "repair_ev_product",
                "source_family": "live_public_web_context",
                "retrieval_route": "live_public_web_context",
                "source_class": "company_product_page",
                "repair_type": "product_surface",
                "analysis_dimension": "product_and_production",
                "claim_types": ["official_product_surface", "product_taxonomy_context", "product_spec_context"],
                "ticker": "ASML",
                "product_family": "EUV lithography systems",
                "metric_leads": ["net bookings", "backlog"],
                "context_only": True,
                "exact_value_authority": False,
                "claim_boundary": "official product surface context only; no exact product KPI promotion",
            }
        ],
        "source_gaps": [
            {
                "gap_id": "gap_market_tracker",
                "gap_type": "commercial_tracker_gap",
                "source_family": "commercial_market_tracker",
                "analysis_dimension": "competition_and_market_position",
            }
        ],
        "tool_observations": [
            {
                "route_id": "product_surface",
                "tool_name": "web_evidence_snapshot",
                "status": "ok",
                "arguments": {"ticker": "ASML", "source_class": "company_product_page"},
                "row_count": 1,
                "source_gap_count": 1,
                "runtime_summary": {"elapsed_ms": 5},
                "boundary": {"status": "pass"},
            }
        ],
        "artifact_refs": [{"artifact_id": "repair_artifact", "row_count": 1}],
        "official_context_summaries": [],
    }
    monkeypatch.setattr("sec_agent.langgraph_orchestrator.execute_official_issuer_repair_plan", lambda repair_plan: execution)

    state: dict[str, Any] = {
        "run_id": "repair_state_smoke",
        "targeted_repair_plan": {"status": "ready", "repairs": [{"repair_id": "repair:product:1"}]},
        "lead_review_checkpoint": {"memo_directive": {}, "dimension_reviews": []},
        "research_objective_contract": {"memo_intent": "investment_research_memo"},
        "tool_call_ledger": {"budget": {}},
        "fundamental_statement_pack": {},
    }
    selected_judgment = {"supported_claims": [], "judgment_state": {"dimension_judgments": []}}

    out = _state_with_lead_targeted_repair(state, selected_judgment)

    assert out["context_rows"][0]["evidence_ref"] == "repair_ev_product"
    assert out["bounded_gap_register"]["gap_count"] == 1
    assert out["verified_judgment_plan"]["lead_targeted_repair_claims"]
    assert out["lead_review_checkpoint"]["lead_targeted_repair_execution"]["status"] == "pass"


def _sample_repair_plan() -> dict[str, Any]:
    contract = build_research_objective_contract(
        query="分析 ASML 的产品、融资和供应链证据缺口",
        required_dimensions=["product_and_production", "capital_and_financing", "competition_and_market_position"],
    )
    checkpoint = build_lead_review_checkpoint(
        objective_contract=contract,
        gaps=[
            {
                "gap_id": "gap_product_surface",
                "ticker": "ASML",
                "analysis_dimension": "product_and_production",
                "gap_type": "product_surface_missing",
                "official_product_urls": ["https://www.asml.com/en/products"],
                "company_domains": ["asml.com"],
                "official_product_surfaces": ["EUV lithography systems"],
                "official_metric_leads": ["net bookings", "backlog"],
            },
            {
                "gap_id": "gap_capital_ownership",
                "ticker": "ASML",
                "analysis_dimension": "capital_and_financing",
                "gap_type": "13f_ownership_or_offering_context_missing",
                "offering_urls": ["https://www.sec.gov/Archives/edgar/data/937966/sample-8k.htm"],
            },
            {
                "gap_id": "gap_supply_chain",
                "ticker": "ASML",
                "analysis_dimension": "competition_and_market_position",
                "gap_type": "supplier_customer_relationship_context_missing",
                "supply_chain_urls": ["https://www.asml.com/en/company/suppliers"],
                "company_domains": ["asml.com"],
            },
        ],
        source_capability={"live_public_web_context": {"product": True, "capital": True, "market": True}},
    )
    return build_targeted_repair_plan(checkpoint)


def _l3_market_proxy_plan(*, source_class: str, url: str, ticker: str) -> dict[str, Any]:
    return {
        "schema_version": "finsight_targeted_repair_plan_v0_1",
        "status": "ready",
        "repairs": [
            {
                "repair_id": f"repair:l3:{source_class}",
                "dimension": "competition_and_market_position",
                "repair_type": "market_proxy",
                "route": "public_market_proxy_repair",
                "ticker": ticker,
                "web_search_allowed": True,
                "web_scope_policy_ids": ["official_statistics_or_industry_dataset_only"],
                "allowed_source_classes": [source_class],
                "probe_urls": [url],
                "market_source_class": source_class,
                "not_found_gap": {"gap_type": "bounded_gap_after_public_market_proxy_probe"},
            }
        ],
    }


def _structured_rows(execution: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in execution.get("context_rows") or []
        if isinstance(row, dict) and row.get("structured_fact_status") == "bounded_context_fact_materialized"
    ]
