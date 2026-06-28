from __future__ import annotations

from sec_agent.product_family_source_routes import (
    build_company_product_family_assignments,
    build_family_source_fetch_audit,
    build_family_source_route_plan,
    build_product_family_lane_registry,
)


def test_product_family_lane_registry_is_valid() -> None:
    registry = build_product_family_lane_registry(generated_at="2026-06-18T00:00:00Z")

    assert registry["validation"]["status"] == "pass"
    assert registry["family_count"] >= 40
    family_ids = {row["family_id"] for row in registry["families"]}
    assert {"gpu_accelerator", "semicap_equipment", "smartphones_tablets"}.issubset(family_ids)


def test_company_product_family_assignment_uses_overrides_and_keywords() -> None:
    assignments = build_company_product_family_assignments(
        company_assignments=[
            {"ticker": "NVDA", "company_name": "NVIDIA Corporation", "primary_lane_id": "V1", "primary_lane_name": "Semiconductors / AI Infrastructure"},
            {"ticker": "ASML", "company_name": "ASML Holding N.V.", "primary_lane_id": "V1", "primary_lane_name": "Semiconductors / AI Infrastructure"},
            {"ticker": "AAPL", "company_name": "Apple Inc.", "primary_lane_id": "V2", "primary_lane_name": "Consumer Hardware / Devices"},
            {"ticker": "ADM", "company_name": "Archer Daniels Midland", "primary_lane_id": "V8", "primary_lane_name": "Retail / CPG / Restaurants / Travel"},
            {"ticker": "ZZZ", "company_name": "Unknown Industrial", "primary_lane_id": "V7", "primary_lane_name": "Energy / Industrials"},
        ],
        product_nodes=[],
        product_runtime_rows=[
            {"ticker": "AAPL", "product_family": "iPhone", "source_id": "company_reported_product_operating_metrics"},
        ],
        public_context_rows=[],
        generated_at="2026-06-18T00:00:00Z",
    )
    by_ticker = {}
    for row in assignments:
        by_ticker.setdefault(row["ticker"], set()).add(row["family_id"])

    assert "gpu_accelerator" in by_ticker["NVDA"]
    assert "semicap_equipment" in by_ticker["ASML"]
    assert "eda_ip" not in by_ticker["ASML"]
    assert "foundry" not in by_ticker["ASML"]
    assert "server_oem" not in by_ticker["ASML"]
    assert "smartphones_tablets" in by_ticker["AAPL"]
    assert "agriculture_commodities_ingredients" in by_ticker["ADM"]
    assert "mass_retail_grocery" not in by_ticker["ADM"]
    assert "v7_general_energy_industrials" in by_ticker["ZZZ"]


def test_company_product_family_assignment_covers_vertical_subfamilies() -> None:
    assignments = build_company_product_family_assignments(
        company_assignments=[
            {"ticker": "CCL", "company_name": "Carnival Corporation", "primary_lane_id": "V8", "primary_lane_name": "Retail / CPG / Restaurants / Travel"},
            {"ticker": "DHI", "company_name": "D.R. Horton, Inc.", "primary_lane_id": "V8", "primary_lane_name": "Retail / CPG / Restaurants / Travel"},
            {"ticker": "IRM", "company_name": "Iron Mountain Incorporated", "primary_lane_id": "V7", "primary_lane_name": "Energy / Industrials"},
            {"ticker": "SWKS", "company_name": "Skyworks Solutions, Inc.", "primary_lane_id": "V3", "primary_lane_name": "SaaS / Cloud / Developer Products"},
            {"ticker": "NWSA", "company_name": "News Corporation", "primary_lane_id": "V3", "primary_lane_name": "SaaS / Cloud / Developer Products"},
        ],
        product_nodes=[],
        product_runtime_rows=[],
        public_context_rows=[],
        generated_at="2026-06-18T00:00:00Z",
    )
    by_ticker = {}
    for row in assignments:
        by_ticker.setdefault(row["ticker"], set()).add(row["family_id"])

    assert "lodging_resorts_cruise" in by_ticker["CCL"]
    assert "homebuilding_residential" in by_ticker["DHI"]
    assert "real_estate_infrastructure_reit" in by_ticker["IRM"]
    assert "connectivity_semiconductor_components" in by_ticker["SWKS"]
    assert "digital_media_content" in by_ticker["NWSA"]


def test_family_source_route_plan_marks_runtime_materialized_seed_and_gap() -> None:
    family_assignments = [
        {
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "primary_lane_id": "V1",
            "family_lane_id": "V1",
            "family_id": "gpu_accelerator",
            "family_name": "GPU / Accelerator",
            "query_terms": ["GPU", "CUDA"],
        }
    ]
    route_plan = build_family_source_route_plan(
        family_assignments=family_assignments,
        product_runtime_rows=[
            {
                "ticker": "NVDA",
                "source_id": "company_reported_product_operating_metrics",
                "product_family": "Data Center GPU",
                "text": "NVIDIA disclosed Data Center GPU revenue.",
                "evidence_ref": "runtime:gpu",
            }
        ],
        public_context_rows=[
            {
                "ticker": "NVDA",
                "source_id": "developer_ecosystem_github_npm_pypi_huggingface",
                "topic": "CUDA",
                "text": "CUDA developer ecosystem proxy context.",
                "evidence_ref": "runtime:cuda",
            }
        ],
        materialized_product_pages=[
            {
                "ticker": "NVDA",
                "source_url": "https://www.nvidia.com/en-us/data-center/",
                "title": "Data Center GPU",
                "product": "GPU",
            }
        ],
        repair_queue_rows=[
            {
                "ticker": "NVDA",
                "requirement_id": "channel_offer_proxy",
                "repair_seed_status": "seed_available",
            }
        ],
        generated_at="2026-06-18T00:00:00Z",
    )
    by_route = {row["route_id"]: row for row in route_plan}

    assert by_route["primary_company_disclosure"]["route_status"] == "runtime_family_row_available"
    assert by_route["developer_ecosystem_proxy"]["route_status"] == "runtime_family_row_available"
    assert by_route["official_product_surface"]["route_status"] in {
        "runtime_family_row_available",
        "runtime_company_row_available",
        "materialized_fetch_available",
    }
    assert by_route["channel_offer_proxy"]["route_status"] == "seed_available_not_materialized"
    assert by_route["public_order_proxy"]["route_status"] == "not_materialized"

    audit = build_family_source_fetch_audit(route_plan_rows=route_plan, generated_at="2026-06-18T00:00:00Z")
    assert audit["validation"]["status"] == "pass"
    assert audit["status"] == "gap"


def test_family_source_route_plan_adds_official_customer_event_route_only_when_runtime_row_exists() -> None:
    route_plan = build_family_source_route_plan(
        family_assignments=[
            {
                "ticker": "AEHR",
                "company_name": "Aehr Test Systems",
                "primary_lane_id": "V1",
                "family_lane_id": "V1",
                "family_id": "semicap_equipment",
                "family_name": "Semicap Equipment",
                "query_terms": ["semiconductor equipment", "FOX-XP"],
            }
        ],
        product_runtime_rows=[],
        public_context_rows=[
            {
                "ticker": "AEHR",
                "source_id": "supplier_customer_official_news",
                "source_role": "official_customer_order_or_deployment_event",
                "product_or_segment": "FOX-XP wafer-level test systems",
                "fact_label": "Aehr production order from lead hyperscale AI customer",
                "event_type": "customer_order",
                "text": "Aehr production order for FOX-XP semiconductor equipment.",
                "evidence_ref": "event:aehr",
            }
        ],
        generated_at="2026-06-24T00:00:00Z",
    )
    by_route = {row["route_id"]: row for row in route_plan}

    assert by_route["official_customer_order_or_deployment_event"]["route_status"] == "runtime_family_row_available"
    assert by_route["official_customer_order_or_deployment_event"]["runtime_company_row_count"] == 1


def test_family_source_route_plan_adds_product_signal_routes_only_when_runtime_rows_exist() -> None:
    route_plan = build_family_source_route_plan(
        family_assignments=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA Corporation",
                "primary_lane_id": "V1",
                "family_lane_id": "V1",
                "family_id": "gpu_accelerator",
                "family_name": "GPU / Accelerator",
                "query_terms": ["GPU", "accelerator"],
            }
        ],
        product_runtime_rows=[],
        public_context_rows=[
            {
                "ticker": "NVDA",
                "source_id": "official_nvidia_product_page",
                "source_role": "technical_product_spec",
                "product_family": "GPU / Accelerator",
                "product_or_segment": "H100 SXM",
                "metric_name": "GPU memory",
                "text": "NVIDIA H100 GPU specification.",
                "evidence_ref": "spec:nvda",
            },
            {
                "ticker": "NVDA",
                "source_id": "official_nvidia_product_page",
                "source_role": "product_benchmark_proxy",
                "product_family": "GPU / Accelerator",
                "text": "NVIDIA benchmark context.",
                "evidence_ref": "bench:nvda",
            },
            {
                "ticker": "NVDA",
                "source_id": "official_nvidia_customer_deployment_news",
                "source_role": "customer_deployment_proxy",
                "product_family": "GPU / Accelerator",
                "customer_name": "xAI",
                "text": "NVIDIA customer deployment context.",
                "evidence_ref": "deploy:nvda",
            },
        ],
        generated_at="2026-06-24T00:00:00Z",
    )
    by_route = {row["route_id"]: row for row in route_plan}

    assert by_route["technical_product_spec"]["route_status"] == "runtime_family_row_available"
    assert by_route["product_benchmark_proxy"]["route_status"] == "runtime_family_row_available"
    assert by_route["customer_deployment_proxy"]["route_status"] == "runtime_family_row_available"


def test_family_source_route_plan_adds_v7_business_asset_profile_route() -> None:
    route_plan = build_family_source_route_plan(
        family_assignments=[
            {
                "ticker": "VST",
                "company_name": "Vistra Corp.",
                "primary_lane_id": "V7",
                "family_lane_id": "V7",
                "family_id": "regulated_utility_power",
                "family_name": "Regulated Utility / Power",
                "query_terms": ["utility", "generation"],
            }
        ],
        product_runtime_rows=[],
        public_context_rows=[
            {
                "ticker": "VST",
                "source_id": "official_business_asset_profile_parser",
                "source_role": "business_asset_profile_spec",
                "product_family": "Regulated Utility / Power",
                "metric_name": "generation_capacity",
                "text": "Vistra generation capacity context for utility power generation.",
                "evidence_ref": "profile:vst",
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    by_route = {row["route_id"]: row for row in route_plan}

    assert by_route["business_asset_profile_spec"]["route_status"] == "runtime_family_row_available"
    assert by_route["business_asset_profile_spec"]["runtime_company_row_count"] == 1


def test_family_source_route_plan_adds_v8_business_asset_profile_route_for_physical_footprint() -> None:
    route_plan = build_family_source_route_plan(
        family_assignments=[
            {
                "ticker": "WMT",
                "company_name": "Walmart Inc.",
                "primary_lane_id": "V8",
                "family_lane_id": "V8",
                "family_id": "mass_retail_grocery",
                "family_name": "Mass Retail / Grocery",
                "query_terms": ["retail", "stores"],
            }
        ],
        product_runtime_rows=[],
        public_context_rows=[
            {
                "ticker": "WMT",
                "source_id": "official_business_asset_profile_parser",
                "source_role": "business_asset_profile_spec",
                "product_family": "Mass Retail / Grocery",
                "metric_name": "store_or_location_count",
                "text": "Walmart official store footprint context for mass retail stores.",
                "evidence_ref": "profile:wmt",
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    by_route = {row["route_id"]: row for row in route_plan}

    assert by_route["business_asset_profile_spec"]["route_status"] == "runtime_family_row_available"
    assert by_route["business_asset_profile_spec"]["runtime_company_row_count"] == 1
