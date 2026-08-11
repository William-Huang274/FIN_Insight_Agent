from __future__ import annotations

from sec_agent.product_slot_relationship_graph import (
    build_company_product_slots,
    build_product_relationship_graph,
    validate_product_relationship_graph,
)


def test_product_slots_extract_family_bound_rows_and_gap_slots() -> None:
    assignments = [
        {
            "assignment_id": "a:nvda:gpu",
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "family_id": "gpu_accelerator",
            "family_name": "GPU / Accelerator",
            "family_lane_id": "V1",
            "query_terms": ["GPU", "CUDA"],
            "assignment_reason": "ticker_override",
            "assignment_confidence": 0.95,
        },
        {
            "assignment_id": "a:asml:semicap",
            "ticker": "ASML",
            "company_name": "ASML Holding N.V.",
            "family_id": "semicap_equipment",
            "family_name": "Semicap Equipment",
            "family_lane_id": "V1",
            "query_terms": ["EUV", "lithography"],
            "assignment_reason": "ticker_override",
            "assignment_confidence": 0.95,
        },
    ]
    routes = [
        {
            "ticker": "NVDA",
            "family_id": "gpu_accelerator",
            "route_id": "official_product_surface",
            "route_status": "runtime_family_row_available",
            "sample_urls": ["https://www.nvidia.com/en-us/data-center/"],
        },
        {
            "ticker": "ASML",
            "family_id": "semicap_equipment",
            "route_id": "official_product_surface",
            "route_status": "seed_available_not_materialized",
            "repair_seed_source_ids": ["company_product_pages"],
            "sample_repair_seed_refs": ["seed:asml"],
        },
    ]
    slots = build_company_product_slots(
        family_assignments=assignments,
        route_plan_rows=routes,
        product_runtime_rows=[],
        public_context_rows=[
            {
                "ticker": "NVDA",
                "source_id": "company_product_pages",
                "product_family": "Blackwell GPU",
                "product_or_segment": "Blackwell GPU",
                "text": "Official product surface mentions Blackwell GPU and CUDA.",
                "url": "https://www.nvidia.com/en-us/data-center/",
                "evidence_ref": "row:nvda:blackwell",
            }
        ],
        generated_at="2026-06-18T00:00:00Z",
    )
    by_ticker = {row["ticker"]: row for row in slots}

    assert by_ticker["NVDA"]["slot_status"] == "official_surface_slot"
    assert by_ticker["NVDA"]["product_slot_name"] == "Blackwell GPU"
    assert by_ticker["NVDA"]["sample_urls"] == ["https://www.nvidia.com/en-us/data-center/"]
    assert by_ticker["ASML"]["slot_status"] == "seed_needs_locator"
    assert by_ticker["ASML"]["sample_repair_seed_refs"] == ["seed:asml"]


def test_product_slots_accept_filings_taxonomy_rows_as_l1_taxonomy_slots() -> None:
    slots = build_company_product_slots(
        family_assignments=[
            {
                "assignment_id": "a:anet:networking",
                "ticker": "ANET",
                "company_name": "Arista Networks",
                "family_id": "networking",
                "family_name": "Datacenter Networking / Connectivity",
                "family_lane_id": "V1",
                "query_terms": ["Ethernet switch", "networking"],
                "family_aliases": ["switch", "network"],
                "assignment_reason": "ticker_override",
                "assignment_confidence": 0.95,
            }
        ],
        route_plan_rows=[],
        product_runtime_rows=[],
        public_context_rows=[
            {
                "schema_version": "fin_agent_company_product_taxonomy_normalized_v0.1",
                "ticker": "ANET",
                "canonical_name": "Network Software and Services",
                "aliases": ["Network Software and Services"],
                "node_type": "product_family",
                "promotion_status": "taxonomy_normalized_auto_gate_passed",
                "max_candidate_confidence": 0.72,
                "source_urls": ["https://www.sec.gov/Archives/edgar/data/1596532/example.htm"],
            }
        ],
        generated_at="2026-06-18T00:00:00Z",
    )

    assert len(slots) == 1
    assert slots[0]["slot_status"] == "filings_taxonomy_slot"
    assert slots[0]["product_slot_name"] == "Network Software and Services"
    assert slots[0]["sample_urls"] == ["https://www.sec.gov/Archives/edgar/data/1596532/example.htm"]


def test_product_slots_bind_generic_lane_to_valid_filings_taxonomy_rows() -> None:
    slots = build_company_product_slots(
        family_assignments=[
            {
                "assignment_id": "a:adbe:generic_software",
                "ticker": "ADBE",
                "company_name": "Adobe Inc.",
                "family_id": "v3_general_software_cloud",
                "family_name": "General Software / Cloud",
                "family_lane_id": "V3",
                "query_terms": ["software", "SaaS"],
                "assignment_reason": "lane_fallback_needs_discovery",
                "assignment_confidence": 0.35,
            }
        ],
        route_plan_rows=[],
        product_runtime_rows=[],
        public_context_rows=[
            {
                "schema_version": "fin_agent_company_product_taxonomy_normalized_v0.1",
                "ticker": "ADBE",
                "canonical_name": "Industry-leading Computational Software and Hardware",
                "node_type": "product_family",
                "promotion_status": "taxonomy_normalized_auto_gate_passed",
                "max_candidate_confidence": 0.64,
                "source_urls": ["https://www.sec.gov/Archives/edgar/data/796343/example.htm"],
            }
        ],
        generated_at="2026-06-18T00:00:00Z",
    )

    assert len(slots) == 1
    assert slots[0]["slot_status"] == "filings_taxonomy_slot"
    assert slots[0]["product_slot_name"] == "Industry-leading Computational Software and Hardware"


def test_product_slots_apply_ticker_family_taxonomy_binding_without_global_relaxation() -> None:
    slots = build_company_product_slots(
        family_assignments=[
            {
                "assignment_id": "a:tsla:battery",
                "ticker": "TSLA",
                "company_name": "Tesla, Inc.",
                "family_id": "battery_charging_autonomy",
                "family_name": "Battery / Charging / Autonomy",
                "family_lane_id": "V5",
                "query_terms": ["battery", "charging", "autonomy"],
                "assignment_reason": "ticker_override",
                "assignment_confidence": 0.95,
            },
            {
                "assignment_id": "a:fake:battery",
                "ticker": "FAKE",
                "company_name": "Fake Vehicle Co.",
                "family_id": "battery_charging_autonomy",
                "family_name": "Battery / Charging / Autonomy",
                "family_lane_id": "V5",
                "query_terms": ["battery", "charging", "autonomy"],
                "assignment_reason": "ticker_override",
                "assignment_confidence": 0.95,
            },
        ],
        route_plan_rows=[],
        product_runtime_rows=[],
        public_context_rows=[
            {
                "schema_version": "fin_agent_company_product_taxonomy_normalized_v0.1",
                "ticker": "TSLA",
                "canonical_name": "Energy Storage Products",
                "node_type": "model_or_product_family",
                "promotion_status": "taxonomy_normalized_auto_gate_passed",
                "max_candidate_confidence": 0.72,
                "source_urls": ["https://www.sec.gov/Archives/edgar/data/1318605/example.htm"],
            },
            {
                "schema_version": "fin_agent_company_product_taxonomy_normalized_v0.1",
                "ticker": "FAKE",
                "canonical_name": "Energy Storage Products",
                "node_type": "model_or_product_family",
                "promotion_status": "taxonomy_normalized_auto_gate_passed",
                "max_candidate_confidence": 0.72,
                "source_urls": ["https://example.com/fake.htm"],
            },
        ],
        generated_at="2026-06-18T00:00:00Z",
    )

    by_ticker = {row["ticker"]: row for row in slots}
    assert by_ticker["TSLA"]["slot_status"] == "filings_taxonomy_slot"
    assert by_ticker["TSLA"]["product_slot_name"] == "Energy Storage Products"
    assert by_ticker["FAKE"]["slot_status"] == "source_discovery_needed"


def test_product_relationship_graph_builds_competitive_and_supply_chain_edges() -> None:
    slots = [
        {
            "product_slot_id": "nvda_gpu",
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "family_id": "gpu_accelerator",
            "family_name": "GPU / Accelerator",
            "product_slot_name": "Blackwell GPU",
            "slot_status": "official_surface_slot",
            "assignment_id": "a:nvda:gpu",
            "assignment_confidence": 0.95,
            "evidence_refs": ["row:nvda"],
        },
        {
            "product_slot_id": "amd_gpu",
            "ticker": "AMD",
            "company_name": "Advanced Micro Devices, Inc.",
            "family_id": "gpu_accelerator",
            "family_name": "GPU / Accelerator",
            "product_slot_name": "Instinct GPU",
            "slot_status": "official_surface_slot",
            "assignment_id": "a:amd:gpu",
            "assignment_confidence": 0.95,
            "evidence_refs": ["row:amd"],
        },
        {
            "product_slot_id": "dell_server",
            "ticker": "DELL",
            "company_name": "Dell Technologies Inc.",
            "family_id": "server_oem",
            "family_name": "AI Server / Rack OEM",
            "product_slot_name": "PowerEdge AI Server",
            "slot_status": "official_surface_slot",
            "assignment_id": "a:dell:server",
            "assignment_confidence": 0.95,
            "evidence_refs": ["row:dell"],
        },
    ]
    graph = build_product_relationship_graph(
        product_slots=slots,
        route_plan_rows=[
            {
                "ticker": "NVDA",
                "family_id": "gpu_accelerator",
                "route_id": "public_order_proxy",
                "sample_evidence_refs": ["order:nvda"],
            }
        ],
        generated_at="2026-06-18T00:00:00Z",
    )
    edge_types = {row["relationship_type"] for row in graph["edges"]}

    assert "COMPETES_WITH" in edge_types
    assert "COMPONENT_INPUT_TO" in edge_types
    assert graph["summary"]["validation"]["status"] == "pass"
    assert graph["summary"]["edge_types"]["COMPETES_WITH"] == 1
    assert any(row["node_type"] == "company_product_family" for row in graph["nodes"])
    assert all(
        row["from_node_id"].startswith("company_product_family:")
        and row["to_node_id"].startswith("company_product_family:")
        for row in graph["edges"]
        if row["relationship_type"] in {"COMPETES_WITH", "COMPONENT_INPUT_TO"}
    )
    assert validate_product_relationship_graph(
        product_slots=graph["slots"],
        nodes=graph["nodes"],
        edges=graph["edges"],
    )["status"] == "pass"
    assert all("market_share" in row["forbidden_claims"] for row in graph["edges"])


def test_product_relationship_graph_adds_parser_backed_relationship_edges() -> None:
    slots = [
        {
            "product_slot_id": "nvda_gpu",
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "family_id": "gpu_accelerator",
            "family_name": "GPU / Accelerator",
            "product_slot_name": "Blackwell GPU",
            "slot_status": "official_surface_slot",
            "assignment_id": "a:nvda:gpu",
            "assignment_confidence": 0.95,
            "evidence_refs": ["row:nvda"],
        }
    ]
    graph = build_product_relationship_graph(
        product_slots=slots,
        relationship_context_rows=[
            {
                "ticker": "NVDA",
                "source_role": "official_customer_order_or_deployment_event",
                "event_type": "customer_deployment",
                "counterparty": "Example Cloud",
                "product_family": "Blackwell GPU deployment",
                "evidence_ref": "official_deployment:nvda:cloud",
                "claim_boundary": "Official deployment context only; no revenue, share, or ASP inference.",
            }
        ],
        generated_at="2026-06-18T00:00:00Z",
    )

    relationship_edges = [row for row in graph["edges"] if row["relationship_type"] == "OFFICIAL_CUSTOMER_DEPLOYMENT_EVENT"]
    assert len(relationship_edges) == 1
    assert relationship_edges[0]["source_layer"] == "L2_parser_backed_relationship_context"
    assert relationship_edges[0]["evidence_refs"] == ["official_deployment:nvda:cloud"]
    assert "undisclosed_revenue" in relationship_edges[0]["forbidden_claims"]
    assert graph["summary"]["parser_backed_relationship_edge_count"] == 1
    assert any(row["node_type"] == "external_counterparty" and row["label"] == "Example Cloud" for row in graph["nodes"])
