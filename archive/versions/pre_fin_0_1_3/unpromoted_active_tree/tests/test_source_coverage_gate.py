from __future__ import annotations

from sec_agent.source_coverage_gate import (
    build_source_coverage_gate,
    build_source_coverage_matrix,
    normalize_industry_schema,
)


def test_source_coverage_gate_exposes_registry_gaps_for_unready_sources() -> None:
    payload = build_source_coverage_gate(
        industry_schema="semicap",
        phase="registry",
        source_layer_capability={
            "rows": [
                _source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True),
                _source("mainstream_financial_news", "L2", "runtime_ready_context"),
                _source("supplier_customer_official_news", "L2", "runtime_ready_context"),
                _source("company_product_pages", "L2", "structured_not_promoted", can_structure=True),
                _source("developer_ecosystem_github_npm_pypi_huggingface", "L3", "not_registered"),
            ]
        },
        generated_at="2026-06-16T00:00:00Z",
    )

    assert payload["industry_schema"] == "semiconductors_hardware"
    assert payload["status"] == "gap"
    gaps = {gap["requirement_id"]: gap["gap_type"] for gap in payload["gaps"]}
    assert gaps["official_product_surface"] == "source_parser_or_mapping_not_runtime_ready"
    assert gaps["developer_ecosystem_proxy"] == "source_not_registered_or_blocked"
    assert payload["validation"]["status"] == "pass"


def test_source_coverage_gate_runtime_case_requires_observed_parser_bound_and_visible_rows() -> None:
    capability = {
        "rows": [
            _source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True),
            _source("company_product_pages", "L2", "runtime_ready_context"),
            _source("mainstream_financial_news", "L2", "runtime_ready_context"),
            _source("fred_api", "L2", "runtime_ready_context"),
        ]
    }
    observed_rows = [
        _parsed_row("sec_edgar_apis", source_layer_id="L1", structured_context_type="financial_statement_fact"),
        _parsed_row(
            "company_product_pages",
            source_layer_id="L2",
            source_class="company_product_page",
            structured_context_type="product_spec_context",
            issuer_binding_status="company_domain_bound",
            product_binding_status="product_mentioned_in_snapshot",
        ),
        _parsed_row(
            "mainstream_financial_news",
            source_layer_id="L2",
            source_class="mainstream_financial_news_article",
            structured_context_type="trusted_news_event_context",
        ),
        _parsed_row("fred_api", source_layer_id="L2", structured_context_type="macro_driver_context"),
    ]
    visible_rows = {
        "fundamental_analyst": [observed_rows[0]],
        "product_technology_analyst": [observed_rows[1]],
        "market_valuation_analyst": [observed_rows[2], observed_rows[3]],
        "risk_counterevidence_analyst": [observed_rows[2]],
        "industry_supply_chain_analyst": [observed_rows[3]],
        "capital_ownership_macro_analyst": [observed_rows[3]],
    }

    payload = build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="runtime_case",
        source_layer_capability=capability,
        observed_rows=observed_rows,
        specialist_visible_rows=visible_rows,
        generated_at="2026-06-16T00:00:00Z",
    )

    assert payload["status"] == "pass"
    assert payload["summary"]["pass_requirement_count"] == 4

    missing_visible = build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="runtime_case",
        source_layer_capability=capability,
        observed_rows=observed_rows,
        specialist_visible_rows={"fundamental_analyst": [observed_rows[0]]},
        generated_at="2026-06-16T00:00:00Z",
    )
    assert missing_visible["status"] == "gap"
    assert any(gap["gap_type"] == "runtime_case_specialist_visibility_missing" for gap in missing_visible["gaps"])


def test_source_coverage_gate_runtime_case_observed_parser_rows_can_satisfy_registry_gap() -> None:
    product_row = _parsed_row(
        "company_product_pages",
        source_layer_id="L2",
        source_class="company_product_page",
        structured_context_type="product_spec_context",
        issuer_binding_status="company_domain_bound",
        product_binding_status="product_mentioned_in_snapshot",
    )
    payload = build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="runtime_case",
        source_layer_capability={
            "rows": [
                _source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True),
                _source("company_product_pages", "L2", "structured_not_promoted", can_structure=True),
                _source("mainstream_financial_news", "L2", "runtime_ready_context"),
                _source("fred_api", "L2", "runtime_ready_context"),
            ]
        },
        observed_rows=[
            _parsed_row("sec_edgar_apis", source_layer_id="L1", structured_context_type="financial_statement_fact"),
            product_row,
            _parsed_row("mainstream_financial_news", source_layer_id="L2", structured_context_type="trusted_news_event_context"),
            _parsed_row("fred_api", source_layer_id="L2", structured_context_type="macro_driver_context"),
        ],
        specialist_visible_rows={
            "fundamental_analyst": [_parsed_row("sec_edgar_apis", source_layer_id="L1", structured_context_type="financial_statement_fact")],
            "product_technology_analyst": [product_row],
            "market_valuation_analyst": [_parsed_row("mainstream_financial_news", source_layer_id="L2", structured_context_type="trusted_news_event_context")],
            "risk_counterevidence_analyst": [_parsed_row("mainstream_financial_news", source_layer_id="L2", structured_context_type="trusted_news_event_context")],
            "industry_supply_chain_analyst": [_parsed_row("fred_api", source_layer_id="L2", structured_context_type="macro_driver_context")],
            "capital_ownership_macro_analyst": [_parsed_row("fred_api", source_layer_id="L2", structured_context_type="macro_driver_context")],
        },
        generated_at="2026-06-16T00:00:00Z",
    )

    official = next(row for row in payload["requirements"] if row["requirement_id"] == "official_product_surface")
    assert official["status"] == "pass"
    assert official["ready_source_count"] == 0
    assert official["effective_ready_source_count"] == 1


def test_source_coverage_gate_entity_binding_requires_all_declared_kinds() -> None:
    product_only = _parsed_row(
        "company_product_pages",
        source_layer_id="L2",
        source_class="company_product_page",
        structured_context_type="product_spec_context",
        issuer_binding_status="not_bound",
        product_binding_status="product_mentioned_in_snapshot",
    )
    payload = build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="runtime_case",
        source_layer_capability={
            "rows": [
                _source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True),
                _source("company_product_pages", "L2", "runtime_ready_context"),
                _source("mainstream_financial_news", "L2", "runtime_ready_context"),
                _source("fred_api", "L2", "runtime_ready_context"),
            ]
        },
        observed_rows=[
            _parsed_row("sec_edgar_apis", source_layer_id="L1", structured_context_type="financial_statement_fact"),
            product_only,
            _parsed_row("mainstream_financial_news", source_layer_id="L2", structured_context_type="trusted_news_event_context"),
            _parsed_row("fred_api", source_layer_id="L2", structured_context_type="macro_driver_context"),
        ],
        specialist_visible_rows={
            "fundamental_analyst": [_parsed_row("sec_edgar_apis", source_layer_id="L1", structured_context_type="financial_statement_fact")],
            "product_technology_analyst": [product_only],
            "market_valuation_analyst": [_parsed_row("mainstream_financial_news", source_layer_id="L2", structured_context_type="trusted_news_event_context")],
            "risk_counterevidence_analyst": [_parsed_row("mainstream_financial_news", source_layer_id="L2", structured_context_type="trusted_news_event_context")],
            "industry_supply_chain_analyst": [_parsed_row("fred_api", source_layer_id="L2", structured_context_type="macro_driver_context")],
            "capital_ownership_macro_analyst": [_parsed_row("fred_api", source_layer_id="L2", structured_context_type="macro_driver_context")],
        },
        generated_at="2026-06-16T00:00:00Z",
    )
    official = next(row for row in payload["requirements"] if row["requirement_id"] == "official_product_surface")
    assert official["status"] == "gap"
    assert any(gap["gap_type"] == "runtime_case_entity_binding_missing" for gap in official["gaps"])


def test_source_coverage_gate_matches_source_class_alias_and_counterparty_binding() -> None:
    observed = _parsed_row(
        "",
        source_layer_id="L2",
        source_class="supplier_customer_official_news",
        structured_context_type="official_supply_chain_news_context",
        issuer_binding_status="issuer_mentioned_in_snapshot",
        counterparty_binding_status="relationship_context_candidate",
    )
    payload = build_source_coverage_gate(
        industry_schema="energy",
        phase="runtime_case",
        source_layer_capability={
            "rows": [
                _source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True),
                _source("supplier_customer_official_news", "L2", "runtime_ready_context"),
                _source("eia_open_data", "L2", "runtime_ready_context"),
                _source("mainstream_financial_news", "L2", "runtime_ready_context"),
                _source("public_tenders_contracts_orders", "L3", "runtime_ready_context"),
                _source("job_postings_hiring_signals", "L3", "runtime_ready_context"),
                _source("fred_api", "L2", "runtime_ready_context"),
            ]
        },
        observed_rows=[observed],
        specialist_visible_rows={"industry_supply_chain_analyst": [observed]},
        required_dimensions=["industry_supply_chain"],
        generated_at="2026-06-16T00:00:00Z",
    )

    supply = next(row for row in payload["requirements"] if row["requirement_id"] == "supply_chain_official_relationship")
    assert supply["observed_row_count"] == 1
    assert supply["entity_bound_row_count"] == 1
    assert supply["specialist_visible_row_count"] == 1


def test_source_coverage_gate_does_not_mix_official_relationship_with_public_order_exact_route() -> None:
    observed = _parsed_row(
        "",
        source_layer_id="L2",
        source_class="supplier_customer_official_news",
        structured_context_type="official_supply_chain_news_context",
        issuer_binding_status="issuer_mentioned_in_snapshot",
        counterparty_binding_status="counterparty_mentioned_in_snapshot",
        product_binding_status="product_mentioned_in_snapshot",
    )
    payload = build_source_coverage_gate(
        industry_schema="semiconductors_hardware",
        phase="runtime_case",
        source_layer_capability={
            "rows": [
                _source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True),
                _source("supplier_customer_official_news", "L2", "runtime_ready_context"),
                _source("public_tenders_contracts_orders", "L3", "runtime_ready_context"),
                _source("company_product_pages", "L2", "runtime_ready_context"),
                _source("developer_ecosystem_github_npm_pypi_huggingface", "L3", "runtime_ready_context"),
                _source("channel_distributor_locator", "L3", "runtime_ready_context"),
                _source("job_postings_hiring_signals", "L3", "runtime_ready_context"),
                _source("fred_api", "L2", "runtime_ready_context"),
                _source("openalex_api", "L3", "runtime_ready_context"),
                _source("mainstream_financial_news", "L2", "runtime_ready_context"),
            ]
        },
        observed_rows=[observed],
        specialist_visible_rows={"industry_supply_chain_analyst": [observed]},
        required_dimensions=["industry_supply_chain"],
        generated_at="2026-06-16T00:00:00Z",
    )

    public_order = next(row for row in payload["requirements"] if row["requirement_id"] == "public_order_proxy")
    assert public_order["observed_row_count"] == 0
    assert public_order["parser_row_count"] == 0
    assert public_order["entity_bound_row_count"] == 0
    assert public_order["status"] == "gap"
    assert public_order["exact_authority_violation_sources"] == []


def test_source_coverage_gate_accepts_dedicated_technical_product_spec_rows() -> None:
    observed = _parsed_row(
        "official_nvidia_product_page",
        source_layer_id="L2",
        structured_context_type="technical_product_spec",
        issuer_binding_status="issuer_mentioned_in_snapshot",
        product_binding_status="product_mentioned_in_snapshot",
    )
    payload = build_source_coverage_gate(
        industry_schema="semiconductors_hardware",
        phase="runtime_case",
        source_layer_capability={
            "rows": [
                _source("official_nvidia_product_page", "L2", "runtime_ready_context"),
            ]
        },
        observed_rows=[observed],
        specialist_visible_rows={"product_technology_analyst": [observed]},
        required_dimensions=["technical_product_spec"],
        generated_at="2026-06-24T00:00:00Z",
    )

    spec = next(row for row in payload["requirements"] if row["requirement_id"] == "technical_product_spec")
    assert spec["status"] == "pass"
    assert spec["observed_row_count"] == 1
    assert spec["entity_bound_row_count"] == 1


def test_source_coverage_gate_does_not_promote_generic_product_page_to_technical_spec() -> None:
    observed = _parsed_row(
        "company_product_pages",
        source_layer_id="L2",
        structured_context_type="official_product_surface",
        issuer_binding_status="issuer_mentioned_in_snapshot",
        product_binding_status="product_mentioned_in_snapshot",
    )
    payload = build_source_coverage_gate(
        industry_schema="semiconductors_hardware",
        phase="runtime_case",
        source_layer_capability={
            "rows": [
                _source("company_product_pages", "L2", "runtime_ready_context"),
                _source("official_nvidia_product_page", "L2", "runtime_ready_context"),
            ]
        },
        observed_rows=[observed],
        specialist_visible_rows={"product_technology_analyst": [observed]},
        required_dimensions=["technical_product_spec"],
        generated_at="2026-06-24T00:00:00Z",
    )

    spec = next(row for row in payload["requirements"] if row["requirement_id"] == "technical_product_spec")
    assert spec["status"] == "gap"
    assert spec["observed_row_count"] == 0


def test_source_coverage_gate_does_not_treat_generic_fsd_as_capital_structure() -> None:
    generic_fsd = _parsed_row(
        "sec_financial_statement_data_sets",
        source_layer_id="L1",
        structured_context_type="financial_statement_fact",
        issuer_binding_status="issuer_mentioned_in_snapshot",
    )
    explicit_capital = _parsed_row(
        "sec_financial_statement_data_sets",
        source_layer_id="L1",
        structured_context_type="capital_structure_context",
        issuer_binding_status="issuer_mentioned_in_snapshot",
        source_role="capital_structure_disclosure",
    )
    kwargs = {
        "industry_schema": "generic_public_research",
        "phase": "runtime_case",
        "source_layer_capability": {"rows": [_source("sec_financial_statement_data_sets", "L1", "runtime_ready_context", exact=True)]},
        "required_dimensions": ["capital_structure_disclosure"],
        "generated_at": "2026-06-24T00:00:00Z",
    }

    generic = build_source_coverage_gate(
        observed_rows=[generic_fsd],
        specialist_visible_rows={"capital_ownership_macro_analyst": [generic_fsd]},
        **kwargs,
    )
    capital = next(row for row in generic["requirements"] if row["requirement_id"] == "capital_structure_disclosure")
    assert capital["status"] == "gap"
    assert capital["observed_row_count"] == 0

    explicit = build_source_coverage_gate(
        observed_rows=[explicit_capital],
        specialist_visible_rows={"capital_ownership_macro_analyst": [explicit_capital]},
        **kwargs,
    )
    capital = next(row for row in explicit["requirements"] if row["requirement_id"] == "capital_structure_disclosure")
    assert capital["status"] == "pass"
    assert capital["observed_row_count"] == 1


def test_source_coverage_gate_fails_non_l1_exact_authority() -> None:
    payload = build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="registry",
        source_layer_capability={
            "rows": [
                _source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True),
                _source("mainstream_financial_news", "L2", "runtime_ready_context", exact=True),
            ]
        },
        generated_at="2026-06-16T00:00:00Z",
    )

    assert payload["status"] == "fail"
    assert payload["validation"]["status"] == "fail"
    assert payload["exact_authority_violations"][0]["source_id"] == "mainstream_financial_news"


def test_source_coverage_matrix_summarizes_multiple_industries() -> None:
    matrix = build_source_coverage_matrix(
        industry_schemas=["generic_public_research", "software"],
        phase="registry",
        source_layer_capability={"rows": [_source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True)]},
        generated_at="2026-06-16T00:00:00Z",
    )

    assert matrix["industry_count"] == 2
    assert matrix["status"] == "gap"
    assert normalize_industry_schema("software") == "software_saas"


def _source(source_id: str, layer_id: str, status: str, *, exact: bool = False, can_structure: bool = False) -> dict[str, object]:
    return {
        "source_id": source_id,
        "layer_id": layer_id,
        "evidence_graph_status": status,
        "runtime_ready_context": status in {"runtime_ready_context", "exact_authority_ready"},
        "exact_value_authority_ready": exact,
        "can_support_company_exact_fact": exact,
        "can_crawl_or_download": can_structure or status != "not_registered",
        "can_structure": can_structure or status in {"runtime_ready_context", "exact_authority_ready", "structured_not_promoted"},
    }


def _parsed_row(
    source_id: str,
    *,
    source_layer_id: str,
    source_class: str = "",
    structured_context_type: str = "bounded_context_fact",
    issuer_binding_status: str = "",
    product_binding_status: str = "",
    counterparty_binding_status: str = "",
    source_role: str = "",
) -> dict[str, object]:
    return {
        "evidence_ref": f"ev:{source_id or source_class}:{structured_context_type}",
        "source_id": source_id,
        "source_class": source_class,
        "source_layer_id": source_layer_id,
        "bounded_structured_context": True,
        "source_specific_parser": "test_parser",
        "structured_fact_status": "bounded_context_fact_materialized",
        "structured_context_type": structured_context_type,
        "source_role": source_role,
        "issuer_binding_status": issuer_binding_status,
        "product_binding_status": product_binding_status,
        "counterparty_binding_status": counterparty_binding_status,
        "exact_value_authority": source_layer_id == "L1",
    }
