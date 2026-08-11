from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


COMPANY_PRODUCT_SLOT_SCHEMA_VERSION = "finsight_company_product_slot_v0_1"
PRODUCT_RELATIONSHIP_NODE_SCHEMA_VERSION = "finsight_product_relationship_graph_node_v0_1"
PRODUCT_RELATIONSHIP_EDGE_SCHEMA_VERSION = "finsight_product_relationship_graph_edge_v0_1"
PRODUCT_RELATIONSHIP_SUMMARY_SCHEMA_VERSION = "finsight_product_relationship_graph_summary_v0_1"


EXACT_PRODUCT_SOURCE_IDS = {"company_reported_product_operating_metrics"}
OFFICIAL_PRODUCT_SOURCE_IDS = {"company_product_pages"}
TAXONOMY_PRODUCT_SOURCE_IDS = {"sec_product_taxonomy_normalized"}
DISCLOSURE_SOURCE_IDS = {"company_ir_reports", "sec_edgar_apis", "sec_financial_statement_data_sets"}
SUPPLY_CHAIN_ROUTE_IDS = {"supply_chain_official_relationship", "public_order_proxy", "channel_offer_proxy"}
LOOSE_EXACT_PRODUCT_FAMILY_BINDINGS = {
    ("DOW", "mining_materials_commodities"),
    ("DUK", "regulated_utility_power"),
    ("ED", "regulated_utility_power"),
    ("FDX", "logistics_transportation"),
    ("GE", "aerospace_defense_industrials"),
    ("ISRG", "medtech_devices"),
    ("KLAC", "semicap_equipment"),
    ("LEN", "homebuilding_residential"),
    ("LOW", "home_improvement"),
    ("PKG", "mining_materials_commodities"),
    ("XEL", "regulated_utility_power"),
}

TICKER_FAMILY_TAXONOMY_BINDING_TERMS = {
    ("AEE", "regulated_utility_power"): ("rates", "electric", "natural gas", "utility", "regulation"),
    ("DIOD", "analog_embedded_semiconductors"): ("rectifier", "transistor", "diode", "mosfet", "discrete semiconductor"),
    ("DIOD", "power_semiconductor_components"): ("rectifier", "transistor", "mosfet", "power", "diode"),
    ("INVH", "real_estate_infrastructure_reit"): ("portfolio", "homes", "residents", "single-family", "leasing"),
    ("LULU", "apparel_athletic_retail"): ("product design", "sourcing", "apparel", "technical clothing", "athletic"),
    ("ORLY", "auto_aftermarket_retail"): ("product line", "auto parts", "dual market", "automotive", "aftermarket"),
    ("TSLA", "battery_charging_autonomy"): ("energy storage", "charging", "solar roof", "autonomy", "software"),
    ("UHS", "healthcare_facilities_services"): ("healthcare services", "hospital", "facilities", "behavioral health", "patients"),
}

GENERIC_FAMILY_PREFIXES = ("v1_general_", "v2_general_", "v3_general_", "v4_general_", "v5_general_", "v6_general_", "v7_general_", "v8_general_")
WEAK_GRAPH_MATCH_TERMS = {"device", "hardware", "product", "products", "service", "services", "software", "surface"}
TAXONOMY_PRODUCT_NODE_TYPES = {
    "asset_or_product_family",
    "banner_or_channel",
    "business_line",
    "category_or_brand_family",
    "financial_product_or_service",
    "model_or_product_family",
    "platform",
    "product",
    "product_family",
    "product_line",
    "product_or_therapy_family",
    "segment",
    "service",
    "therapeutic_area_or_business_line",
}
TAXONOMY_CONTEXT_NODE_TYPES = {
    "customer_market",
    "customer_market_or_channel",
    "end_market",
    "indication_or_customer_market",
    "use_case_or_customer_market",
}
PRODUCT_SLOT_NAME_BLOCKLIST = {
    "about us",
    "accessories",
    "account",
    "accept settings",
    "affordable",
    "all other",
    "available information",
    "buy",
    "cart",
    "clean",
    "compare",
    "company",
    "costco homepage",
    "corporation",
    "customer net",
    "customer service",
    "english",
    "featured",
    "feature stories",
    "general information",
    "getting started",
    "guided shopping",
    "holiday schedule",
    "i accept",
    "introduction",
    "invest",
    "join our team",
    "language & location",
    "log in",
    "login",
    "logout",
    "markets we serve",
    "market drivers",
    "market opportunity",
    "marketed",
    "menu menu",
    "mission",
    "news news",
    "policy priorities",
    "popular resources",
    "our mission",
    "patients",
    "performance",
    "quick links quick links",
    "r&d",
    "read more",
    "regions regions",
    "reliable",
    "scroll to top",
    "semiconductor industry association",
    "segments",
    "service excellence",
    "our websites",
    "personal setup",
    "product specification context",
    "products and solutions",
    "scale out",
    "scale up",
    "shop watch",
    "strategy and opportunity",
    "submit feedback",
    "table",
    "tm",
    "trending topics",
    "watch the film",
    "welcome to costco wholesale",
    "who we are",
}
PRODUCT_SLOT_NAME_BLOCK_PATTERNS = (
    " accept ",
    " member",
    " footer",
    " homepage",
    " privacy",
    " trade in",
    "apple store app",
    "anticipated benefits",
    "available information",
    "business plans",
    "business results",
    "business strategy",
    "by the numbers",
    "changes in ",
    "company strategy",
    "connecting now to next",
    "convertible senior notes",
    "customer portal",
    "cutting-edge cameras",
    "delivery and pickup",
    "hide notification",
    "latest ",
    "language ",
    "located in ",
    "more from ",
    "narrative description",
    "note regarding",
    "official product surface",
    "page not found",
    "recent highlights",
    "revolving credit facility",
    "risks relating",
    "shop ",
    "skip to ",
    "spin-off",
    "suppliers",
    "sustainability report",
    "to provide ",
    "vendors",
    "we use investor",
)

SUPPLY_CHAIN_TEMPLATES: tuple[tuple[str, str, str, str], ...] = (
    ("semicap_equipment", "foundry", "ENABLES_PRODUCTION_FOR", "Semicap equipment is upstream production tooling for foundry capacity."),
    ("foundry", "gpu_accelerator", "MANUFACTURING_DEPENDENCY_FOR", "Advanced accelerators depend on foundry manufacturing and packaging capacity."),
    ("foundry", "networking", "MANUFACTURING_DEPENDENCY_FOR", "Datacenter networking silicon depends on foundry manufacturing capacity."),
    ("foundry", "memory", "MANUFACTURING_DEPENDENCY_FOR", "Memory products depend on wafer fabrication and packaging capacity."),
    ("memory", "server_oem", "COMPONENT_INPUT_TO", "Memory is a core input to AI server configurations."),
    ("gpu_accelerator", "server_oem", "COMPONENT_INPUT_TO", "Accelerators are core inputs to AI server/rack OEM systems."),
    ("networking", "server_oem", "COMPLEMENTS_WITH", "Datacenter networking complements AI server/rack deployments."),
    ("power_cooling", "server_oem", "INFRASTRUCTURE_COMPLEMENT_TO", "Power and cooling infrastructure complements AI server/rack deployments."),
    ("power_grid_cooling", "server_oem", "INFRASTRUCTURE_COMPLEMENT_TO", "Power/grid/cooling infrastructure complements AI server/rack deployments."),
    ("server_oem", "cloud_infrastructure", "INFRASTRUCTURE_SUPPLIER_TO", "Server/rack OEM products can be infrastructure inputs to cloud capacity."),
    ("battery_charging_autonomy", "ev_vehicle_platform", "INPUT_OR_COMPLEMENT_TO", "Battery, charging, and autonomy systems complement EV vehicle platforms."),
)


def build_company_product_slots(
    *,
    family_assignments: Iterable[Mapping[str, Any]],
    route_plan_rows: Iterable[Mapping[str, Any]],
    product_runtime_rows: Iterable[Mapping[str, Any]] | None = None,
    public_context_rows: Iterable[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    generated_at = generated_at or _utc_now()
    assignments = [dict(row) for row in family_assignments if isinstance(row, Mapping)]
    route_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in route_plan_rows:
        if not isinstance(row, Mapping):
            continue
        route_groups[(_ticker(row), str(row.get("family_id") or ""))].append(dict(row))
    context_rows = [dict(row) for row in [*(product_runtime_rows or []), *(public_context_rows or [])] if isinstance(row, Mapping)]
    context_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in context_rows:
        ticker = _ticker(row)
        if ticker:
            context_by_ticker[ticker].append(row)

    slots: list[dict[str, Any]] = []
    for assignment in assignments:
        ticker = _ticker(assignment)
        family_id = str(assignment.get("family_id") or "")
        family_terms = _family_terms(assignment)
        routes = route_groups.get((ticker, family_id), [])
        matching_rows = [
            row
            for row in context_by_ticker.get(ticker, [])
            if _row_is_product_relevant(row) and _row_family_matches(row, family_id=family_id, family_terms=family_terms)
        ]
        grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in matching_rows:
            product_name = _normalize_product_name(_row_product_name(row))
            if product_name:
                grouped_rows[_slug(product_name)].append(row)

        if grouped_rows:
            for slug, rows in sorted(grouped_rows.items()):
                slots.append(
                    _slot_from_rows(
                        assignment=assignment,
                        rows=rows,
                        routes=routes,
                        product_name=_best_product_name(rows, default=slug),
                        generated_at=generated_at,
                    )
                )
        else:
            slots.append(_discovery_slot(assignment=assignment, routes=routes, generated_at=generated_at))
    return sorted(slots, key=lambda row: (row["ticker"], row["family_id"], row["product_slot_name"]))


def build_product_relationship_graph(
    *,
    product_slots: Iterable[Mapping[str, Any]],
    route_plan_rows: Iterable[Mapping[str, Any]] | None = None,
    relationship_context_rows: Iterable[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, list[dict[str, Any]] | dict[str, Any]]:
    generated_at = generated_at or _utc_now()
    slots = [dict(row) for row in product_slots if isinstance(row, Mapping)]
    route_index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in route_plan_rows or []:
        if isinstance(row, Mapping):
            route_index[(_ticker(row), str(row.get("family_id") or ""))].append(dict(row))

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    for slot in slots:
        company_node = _node("company", _ticker(slot), label=str(slot.get("company_name") or _ticker(slot)), generated_at=generated_at)
        family_node = _node("product_family", str(slot.get("family_id") or ""), label=str(slot.get("family_name") or slot.get("family_id")), generated_at=generated_at)
        company_family_node = _node(
            "company_product_family",
            _company_family_key(slot),
            label=f"{_ticker(slot)} / {slot.get('family_name') or slot.get('family_id')}",
            generated_at=generated_at,
            payload={
                "ticker": _ticker(slot),
                "company_name": slot.get("company_name") or "",
                "family_id": slot.get("family_id") or "",
                "family_name": slot.get("family_name") or "",
            },
        )
        slot_node = _node("product_slot", str(slot.get("product_slot_id") or ""), label=str(slot.get("product_slot_name") or ""), generated_at=generated_at, payload=slot)
        for node in (company_node, family_node, company_family_node, slot_node):
            if node["node_id"] not in seen_nodes:
                nodes.append(node)
                seen_nodes.add(node["node_id"])
        edges.append(
            _edge(
                "HAS_PRODUCT_FAMILY",
                company_node["node_id"],
                company_family_node["node_id"],
                generated_at=generated_at,
                evidence_refs=[str(slot.get("assignment_id") or "")],
                source_layer="taxonomy_assignment",
                confidence=float(slot.get("assignment_confidence") or 0.0),
                promotion_status=str(slot.get("assignment_reason") or ""),
                claim_boundary="Company-to-product-family assignment guides retrieval and comparison; not product sales, share, or customer proof.",
            )
        )
        edges.append(
            _edge(
                "IN_PRODUCT_FAMILY",
                company_family_node["node_id"],
                family_node["node_id"],
                generated_at=generated_at,
                evidence_refs=[str(slot.get("assignment_id") or "")],
                source_layer="taxonomy_assignment",
                confidence=float(slot.get("assignment_confidence") or 0.0),
                promotion_status=str(slot.get("assignment_reason") or ""),
                claim_boundary="Company-family node is a bounded analyst navigation object, not a market-share estimate.",
            )
        )
        edges.append(
            _edge(
                "FAMILY_HAS_PRODUCT_SLOT",
                company_family_node["node_id"],
                slot_node["node_id"],
                generated_at=generated_at,
                evidence_refs=slot.get("evidence_refs") or [],
                source_layer=_slot_source_layer(slot),
                confidence=_slot_confidence(slot),
                promotion_status=str(slot.get("slot_status") or ""),
                claim_boundary="Product slot belongs to this company-family context within cited evidence boundaries.",
            )
        )
        edges.append(
            _edge(
                "HAS_PRODUCT_SLOT",
                company_node["node_id"],
                slot_node["node_id"],
                generated_at=generated_at,
                evidence_refs=slot.get("evidence_refs") or [],
                source_layer=_slot_source_layer(slot),
                confidence=_slot_confidence(slot),
                promotion_status=str(slot.get("slot_status") or ""),
                claim_boundary="Company has this product slot only within the cited product/family evidence boundary.",
            )
        )
        edges.append(
            _edge(
                "BELONGS_TO_FAMILY",
                slot_node["node_id"],
                family_node["node_id"],
                generated_at=generated_at,
                evidence_refs=[str(slot.get("assignment_id") or "")],
                source_layer="taxonomy_assignment",
                confidence=float(slot.get("assignment_confidence") or 0.0),
                promotion_status=str(slot.get("assignment_reason") or ""),
                claim_boundary="Family assignment guides retrieval and comparison; it is not product sales, market share, or supply-chain proof.",
            )
        )

    edges.extend(_competitive_edges(slots=slots, generated_at=generated_at))
    edges.extend(_supply_chain_template_edges(slots=slots, route_index=route_index, generated_at=generated_at))
    relationship_edges, relationship_nodes = _relationship_context_edges(
        slots=slots,
        relationship_context_rows=relationship_context_rows or [],
        generated_at=generated_at,
    )
    for node in relationship_nodes:
        if node["node_id"] not in seen_nodes:
            nodes.append(node)
            seen_nodes.add(node["node_id"])
    edges.extend(relationship_edges)
    edges = _dedupe_edges(edges)
    summary = build_product_relationship_summary(product_slots=slots, nodes=nodes, edges=edges, generated_at=generated_at)
    return {"slots": slots, "nodes": nodes, "edges": edges, "summary": summary}


def build_product_relationship_summary(
    *,
    product_slots: Sequence[Mapping[str, Any]],
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    slot_status = Counter(str(row.get("slot_status") or "") for row in product_slots)
    edge_types = Counter(str(row.get("relationship_type") or "") for row in edges)
    validation = validate_product_relationship_graph(product_slots=product_slots, nodes=nodes, edges=edges)
    return {
        "schema_version": PRODUCT_RELATIONSHIP_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "fail" if validation["status"] == "fail" else "gap" if slot_status.get("source_discovery_needed") or slot_status.get("seed_needs_locator") else "pass",
        "company_count": len({_ticker(row) for row in product_slots}),
        "product_slot_count": len(product_slots),
        "product_family_count": len({str(row.get("family_id") or "") for row in product_slots}),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "slot_status": dict(sorted(slot_status.items())),
        "edge_types": dict(sorted(edge_types.items())),
        "parser_backed_relationship_edge_count": sum(
            1
            for row in edges
            if str(row.get("source_layer") or "")
            in {"L2_parser_backed_relationship_context", "L3_parser_backed_public_order_or_channel_context"}
        ),
        "with_url_slot_count": sum(1 for row in product_slots if row.get("sample_urls")),
        "with_family_bound_runtime_slot_count": sum(1 for row in product_slots if row.get("slot_status") in {"product_kpi_exact_slot", "filings_taxonomy_slot", "official_surface_slot", "bounded_context_slot"}),
        "validation": validation,
        "boundary": "Product graph is provenance-backed. Competitive/supply-chain edges are retrieval and analyst-context edges unless an official/source-specific parser promotes them; no market share, sales, ASP, or undisclosed KPI authority is inferred.",
    }


def validate_product_relationship_graph(
    *,
    product_slots: Sequence[Mapping[str, Any]],
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    slot_ids: set[str] = set()
    for slot in product_slots:
        slot_id = str(slot.get("product_slot_id") or "")
        if not slot_id:
            errors.append({"type": "missing_product_slot_id", "ticker": slot.get("ticker")})
        elif slot_id in slot_ids:
            errors.append({"type": "duplicate_product_slot_id", "product_slot_id": slot_id})
        slot_ids.add(slot_id)
        if not slot.get("ticker") or not slot.get("family_id") or not slot.get("product_slot_name"):
            errors.append({"type": "missing_slot_core_fields", "product_slot_id": slot_id})
        forbidden = " ".join(str(item) for item in slot.get("allowed_claims") or [])
        if any(term in forbidden.lower() for term in ["market_share", "undisclosed_sales", "sell_through"]):
            errors.append({"type": "slot_claim_boundary_violation", "product_slot_id": slot_id})
    node_ids = {str(node.get("node_id") or "") for node in nodes}
    edge_ids: set[str] = set()
    for edge in edges:
        edge_id = str(edge.get("edge_id") or "")
        if not edge_id:
            errors.append({"type": "missing_edge_id"})
        elif edge_id in edge_ids:
            errors.append({"type": "duplicate_edge_id", "edge_id": edge_id})
        edge_ids.add(edge_id)
        if edge.get("from_node_id") not in node_ids or edge.get("to_node_id") not in node_ids:
            errors.append({"type": "edge_endpoint_missing_node", "edge_id": edge_id})
        if edge.get("relationship_type") in {"COMPETES_WITH", "COMPONENT_INPUT_TO", "ENABLES_PRODUCTION_FOR"} and not edge.get("claim_boundary"):
            errors.append({"type": "missing_edge_claim_boundary", "edge_id": edge_id})
    return {"schema_version": "finsight_product_relationship_graph_validation_v0_1", "status": "fail" if errors else "pass", "errors": errors}


def write_product_relationship_artifacts(
    *,
    product_slots: Sequence[Mapping[str, Any]],
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    output_slots_path: str | Path,
    output_nodes_path: str | Path,
    output_edges_path: str | Path,
    output_summary_path: str | Path,
    output_report_path: str | Path,
) -> dict[str, str]:
    slots_path = Path(output_slots_path)
    nodes_path = Path(output_nodes_path)
    edges_path = Path(output_edges_path)
    summary_path = Path(output_summary_path)
    report_path = Path(output_report_path)
    for path in (slots_path, nodes_path, edges_path, summary_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(slots_path, product_slots)
    _write_jsonl(nodes_path, nodes)
    _write_jsonl(edges_path, edges)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_product_relationship_report(summary=summary, product_slots=product_slots), encoding="utf-8")
    return {"slots": str(slots_path), "nodes": str(nodes_path), "edges": str(edges_path), "summary": str(summary_path), "report": str(report_path)}


def render_product_relationship_report(*, summary: Mapping[str, Any], product_slots: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# Product Slot And Relationship Graph",
        "",
        f"- status: `{summary.get('status')}`",
        f"- company_count: `{summary.get('company_count')}`",
        f"- product_slot_count: `{summary.get('product_slot_count')}`",
        f"- product_family_count: `{summary.get('product_family_count')}`",
        f"- node_count: `{summary.get('node_count')}`",
        f"- edge_count: `{summary.get('edge_count')}`",
        f"- with_url_slot_count: `{summary.get('with_url_slot_count')}`",
        f"- with_family_bound_runtime_slot_count: `{summary.get('with_family_bound_runtime_slot_count')}`",
        "",
        "## Slot Status",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    for status, count in (summary.get("slot_status") or {}).items():
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## Edge Types", "", "| relationship | count |", "| --- | ---: |"])
    for edge_type, count in (summary.get("edge_types") or {}).items():
        lines.append(f"| {edge_type} | {count} |")
    lines.extend(["", "## Sample Slots", ""])
    for row in list(product_slots)[:60]:
        lines.append(
            f"- `{row.get('ticker')}` `{row.get('family_id')}` `{row.get('product_slot_name')}`: "
            f"`{row.get('slot_status')}` urls={len(row.get('sample_urls') or [])} evidence={len(row.get('evidence_refs') or [])}"
        )
    lines.extend(["", "## Boundary", "", str(summary.get("boundary") or ""), ""])
    return "\n".join(lines)


def _slot_from_rows(*, assignment: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], routes: Sequence[Mapping[str, Any]], product_name: str, generated_at: str) -> dict[str, Any]:
    ticker = _ticker(assignment)
    family_id = str(assignment.get("family_id") or "")
    source_ids = sorted({source_id for row in rows for source_id in _row_source_ids(row)})
    exact_rows = [row for row in rows if _row_source_ids(row).intersection(EXACT_PRODUCT_SOURCE_IDS) and bool(row.get("exact_value_authority"))]
    taxonomy_rows = [row for row in rows if _row_source_ids(row).intersection(TAXONOMY_PRODUCT_SOURCE_IDS)]
    official_rows = [row for row in rows if _row_source_ids(row).intersection(OFFICIAL_PRODUCT_SOURCE_IDS)]
    status = "product_kpi_exact_slot" if exact_rows else "filings_taxonomy_slot" if taxonomy_rows else "official_surface_slot" if official_rows else "bounded_context_slot"
    sample_urls = _unique_strings([*_sample_urls(rows), *_sample_route_urls(routes)])[:8]
    return {
        "schema_version": COMPANY_PRODUCT_SLOT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "product_slot_id": _stable_id("product_slot", [ticker, family_id, product_name]),
        "ticker": ticker,
        "company_name": assignment.get("company_name") or "",
        "family_id": family_id,
        "family_name": assignment.get("family_name") or "",
        "family_lane_id": assignment.get("family_lane_id") or assignment.get("primary_lane_id") or "",
        "product_slot_name": product_name,
        "product_slot_slug": _slug(product_name),
        "slot_status": status,
        "slot_source_ids": source_ids,
        "sample_urls": sample_urls,
        "evidence_refs": _unique_strings([_row_ref(row) for row in rows])[:20],
        "source_route_ids": _unique_strings([row.get("route_id") for row in routes])[:20],
        "route_statuses": dict(sorted(Counter(str(row.get("route_status") or "") for row in routes).items())),
        "assignment_id": assignment.get("assignment_id") or "",
        "assignment_reason": assignment.get("assignment_reason") or "",
        "assignment_confidence": float(assignment.get("assignment_confidence") or 0.0),
        "allowed_claims": _slot_allowed_claims(status),
        "forbidden_claims": ["market_share", "sell_through", "channel_inventory", "undisclosed_product_revenue", "ASP_without_company_or_tracker_data"],
        "claim_boundary": _slot_claim_boundary(status),
        "next_action": "ready_for_product_specialist" if status in {"product_kpi_exact_slot", "filings_taxonomy_slot", "official_surface_slot"} else "use_as_context_and_seek_stronger_family_rows",
    }


def _discovery_slot(*, assignment: Mapping[str, Any], routes: Sequence[Mapping[str, Any]], generated_at: str) -> dict[str, Any]:
    ticker = _ticker(assignment)
    family_id = str(assignment.get("family_id") or "")
    route_statuses = Counter(str(row.get("route_status") or "") for row in routes)
    seed_rows = [row for row in routes if row.get("route_status") == "seed_available_not_materialized"]
    company_rows = [row for row in routes if row.get("route_status") == "runtime_company_row_available"]
    if company_rows:
        status = "company_route_needs_family_binding"
        next_action = "tighten product-family binding on existing company-route rows"
    elif seed_rows:
        status = "seed_needs_locator"
        next_action = "resolve repair seed refs to URL/raw locator then fetch and parse"
    else:
        status = "source_discovery_needed"
        next_action = "discover official or allowed public source for this family route"
    return {
        "schema_version": COMPANY_PRODUCT_SLOT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "product_slot_id": _stable_id("product_slot", [ticker, family_id, "family_discovery"]),
        "ticker": ticker,
        "company_name": assignment.get("company_name") or "",
        "family_id": family_id,
        "family_name": assignment.get("family_name") or "",
        "family_lane_id": assignment.get("family_lane_id") or assignment.get("primary_lane_id") or "",
        "product_slot_name": str(assignment.get("family_name") or family_id),
        "product_slot_slug": _slug(str(assignment.get("family_name") or family_id)),
        "slot_status": status,
        "slot_source_ids": _unique_strings([source_id for row in routes for source_id in (row.get("source_ids") or [])])[:20],
        "sample_urls": _sample_route_urls(routes)[:8],
        "evidence_refs": [],
        "repair_seed_source_ids": _unique_strings([source_id for row in routes for source_id in (row.get("repair_seed_source_ids") or [])])[:20],
        "sample_repair_seed_refs": _unique_strings([ref for row in routes for ref in (row.get("sample_repair_seed_refs") or [])])[:20],
        "source_route_ids": _unique_strings([row.get("route_id") for row in routes])[:20],
        "route_statuses": dict(sorted(route_statuses.items())),
        "assignment_id": assignment.get("assignment_id") or "",
        "assignment_reason": assignment.get("assignment_reason") or "",
        "assignment_confidence": float(assignment.get("assignment_confidence") or 0.0),
        "allowed_claims": ["retrieval_planning", "product_family_discovery_context"],
        "forbidden_claims": ["market_share", "sell_through", "channel_inventory", "undisclosed_product_revenue", "product_specific_claim_without_binding"],
        "claim_boundary": "Discovery slot only; do not write product-specific conclusions until a product/source row is bound.",
        "next_action": next_action,
    }


def _competitive_edges(*, slots: Sequence[Mapping[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for slot in slots:
        family_id = str(slot.get("family_id") or "")
        if family_id and not family_id.startswith(GENERIC_FAMILY_PREFIXES) and _slot_is_relationship_ready(slot):
            ticker = _ticker(slot)
            current = by_family[family_id].get(ticker)
            if current is None or _slot_confidence(slot) > _slot_confidence(current):
                by_family[family_id][ticker] = slot
    edges: list[dict[str, Any]] = []
    for family_id, family_slots_by_ticker in by_family.items():
        unique_company_slots = sorted(family_slots_by_ticker.values(), key=lambda row: str(row.get("ticker") or ""))
        for i, left in enumerate(unique_company_slots):
            for right in unique_company_slots[i + 1 :]:
                if left.get("ticker") == right.get("ticker"):
                    continue
                confidence = min(_slot_confidence(left), _slot_confidence(right), 0.65)
                edges.append(
                    _edge(
                        "COMPETES_WITH",
                        _company_family_node_id(left),
                        _company_family_node_id(right),
                        generated_at=generated_at,
                        evidence_refs=[str(left.get("assignment_id") or ""), str(right.get("assignment_id") or "")],
                        source_layer="derived_company_family_comparable",
                        confidence=confidence,
                        promotion_status="candidate_company_family_comparable_edge",
                        claim_boundary="Same product family comparable candidate only; does not prove share, win/loss, pricing, or direct displacement without stronger evidence.",
                    )
                )
    return edges


def _supply_chain_template_edges(*, slots: Sequence[Mapping[str, Any]], route_index: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]], generated_at: str) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for slot in slots:
        if _slot_is_relationship_ready(slot):
            family_id = str(slot.get("family_id") or "")
            ticker = _ticker(slot)
            current = by_family[family_id].get(ticker)
            if current is None or _slot_confidence(slot) > _slot_confidence(current):
                by_family[family_id][ticker] = slot
    edges: list[dict[str, Any]] = []
    for upstream_family, downstream_family, rel_type, rationale in SUPPLY_CHAIN_TEMPLATES:
        for upstream in by_family.get(upstream_family, {}).values():
            for downstream in by_family.get(downstream_family, {}).values():
                if upstream.get("ticker") == downstream.get("ticker"):
                    continue
                evidence_refs = [
                    *_route_refs(route_index.get((_ticker(upstream), upstream_family), []), SUPPLY_CHAIN_ROUTE_IDS),
                    *_route_refs(route_index.get((_ticker(downstream), downstream_family), []), SUPPLY_CHAIN_ROUTE_IDS),
                ]
                promotion = "public_context_relationship_edge" if evidence_refs else "candidate_taxonomy_relationship_edge"
                confidence = 0.58 if evidence_refs else 0.35
                edges.append(
                    _edge(
                        rel_type,
                        _company_family_node_id(upstream),
                        _company_family_node_id(downstream),
                        generated_at=generated_at,
                        evidence_refs=evidence_refs[:12],
                        source_layer="parser_backed_context" if evidence_refs else "derived_lane_template",
                        confidence=confidence,
                        promotion_status=promotion,
                        claim_boundary=f"{rationale} This edge is context for analyst retrieval and hypothesis checking; it is not shipment, revenue, allocation, or customer concentration proof.",
                    )
                )
    return edges


def _relationship_context_edges(
    *,
    slots: Sequence[Mapping[str, Any]],
    relationship_context_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    slots_by_ticker: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for slot in slots:
        if _slot_is_relationship_ready(slot):
            slots_by_ticker[_ticker(slot)].append(slot)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    for raw in relationship_context_rows:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        ticker = _ticker(row)
        if not ticker or ticker not in slots_by_ticker:
            continue
        relationship_type = _relationship_edge_type(row)
        if not relationship_type:
            continue
        counterparty = _relationship_counterparty(row)
        if not counterparty:
            continue
        anchor_slot = _relationship_anchor_slot(row, slots_by_ticker[ticker])
        if not anchor_slot:
            continue
        counterparty_node = _node(
            "external_counterparty",
            _stable_id("counterparty", [counterparty]),
            label=counterparty,
            generated_at=generated_at,
            payload={
                "counterparty": counterparty,
                "source_role": row.get("source_role") or row.get("requirement_id") or "",
            },
        )
        if counterparty_node["node_id"] not in seen_nodes:
            nodes.append(counterparty_node)
            seen_nodes.add(counterparty_node["node_id"])
        source_role = str(row.get("source_role") or row.get("requirement_id") or "")
        source_layer = (
            "L2_parser_backed_relationship_context"
            if source_role in {"official_customer_order_or_deployment_event", "supply_chain_official_relationship"}
            else "L3_parser_backed_public_order_or_channel_context"
        )
        edges.append(
            _edge(
                relationship_type,
                _company_family_node_id(anchor_slot),
                counterparty_node["node_id"],
                generated_at=generated_at,
                evidence_refs=[row.get("evidence_ref") or row.get("evidence_id") or row.get("fact_id") or row.get("source_url") or ""],
                source_layer=source_layer,
                confidence=0.78 if source_layer.startswith("L2") else 0.62,
                promotion_status="parser_backed_relationship_context_edge",
                claim_boundary=str(row.get("claim_boundary") or "")
                or "Parser-backed relationship context only; do not infer revenue, backlog, shipment volume, share, ASP, or sell-through.",
            )
        )
    return edges, nodes


def _relationship_edge_type(row: Mapping[str, Any]) -> str:
    source_role = str(row.get("source_role") or row.get("requirement_id") or "")
    event_type = str(row.get("event_type") or "")
    structured = str(row.get("structured_context_type") or "")
    if source_role == "official_customer_order_or_deployment_event" or event_type in {"customer_order", "customer_deployment", "production_or_manufacturing_plan"}:
        return "OFFICIAL_CUSTOMER_DEPLOYMENT_EVENT"
    if source_role == "supply_chain_official_relationship" or "supply_chain" in structured:
        return "OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP"
    if source_role == "public_order_proxy":
        return "PUBLIC_ORDER_OR_TENDER_CONTEXT"
    if source_role in {"channel_offer_proxy", "channel_pricing_quotations", "channel_distributor_locator"} or structured in {"channel_offer_context", "channel_distributor_locator_context"}:
        return "CHANNEL_OR_DISTRIBUTION_CONTEXT"
    return ""


def _relationship_counterparty(row: Mapping[str, Any]) -> str:
    for key in ("counterparty", "customer_name", "supplier_name", "recipient_name", "buyer_name", "agency_name", "partner_name"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    citation = row.get("citation")
    if isinstance(citation, Mapping):
        title = str(citation.get("title") or "").strip()
        if title:
            return title[:160]
    return ""


def _relationship_anchor_slot(row: Mapping[str, Any], slots: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("product_family", "product_or_segment", "relationship_label", "fact_label", "text", "preview")
    ).lower()
    scored: list[tuple[float, str, Mapping[str, Any]]] = []
    for slot in slots:
        score = _slot_confidence(slot)
        family_id = str(slot.get("family_id") or "").lower()
        family_name = str(slot.get("family_name") or "").lower()
        product_name = str(slot.get("product_slot_name") or "").lower()
        if family_id and family_id in text:
            score += 0.2
        if product_name and product_name in text:
            score += 0.15
        family_terms = [term for term in re.split(r"\W+", family_name) if len(term) > 4]
        if family_terms and any(term in text for term in family_terms):
            score += 0.12
        scored.append((score, str(slot.get("product_slot_id") or ""), slot))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return scored[0][2]


def _node(node_type: str, key: str, *, label: str, generated_at: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": PRODUCT_RELATIONSHIP_NODE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "node_id": f"{node_type}:{key}",
        "node_type": node_type,
        "label": label,
        "payload": dict(payload or {}),
    }


def _company_family_key(slot: Mapping[str, Any]) -> str:
    return f"{_ticker(slot)}:{slot.get('family_id') or ''}"


def _company_family_node_id(slot: Mapping[str, Any]) -> str:
    return f"company_product_family:{_company_family_key(slot)}"


def _edge(
    relationship_type: str,
    from_node_id: str,
    to_node_id: str,
    *,
    generated_at: str,
    evidence_refs: Sequence[Any],
    source_layer: str,
    confidence: float,
    promotion_status: str,
    claim_boundary: str,
) -> dict[str, Any]:
    edge_id = _stable_id("product_relationship_edge", [relationship_type, from_node_id, to_node_id])
    return {
        "schema_version": PRODUCT_RELATIONSHIP_EDGE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "edge_id": edge_id,
        "relationship_type": relationship_type,
        "from_node_id": from_node_id,
        "to_node_id": to_node_id,
        "evidence_refs": _unique_strings(evidence_refs)[:20],
        "source_layer": source_layer,
        "confidence": round(float(confidence), 4),
        "promotion_status": promotion_status,
        "claim_boundary": claim_boundary,
        "forbidden_claims": ["market_share", "shipment_volume", "sell_through", "undisclosed_revenue", "customer_concentration_without_disclosure"],
    }


def _route_refs(rows: Sequence[Mapping[str, Any]], route_ids: set[str]) -> list[str]:
    refs: list[str] = []
    for row in rows:
        if str(row.get("route_id") or "") not in route_ids:
            continue
        refs.extend(row.get("sample_evidence_refs") or [])
    return _unique_strings(refs)


def _dedupe_edges(edges: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for edge in edges:
        edge_id = str(edge.get("edge_id") or "")
        if edge_id not in by_id:
            by_id[edge_id] = dict(edge)
            continue
        existing = by_id[edge_id]
        existing["evidence_refs"] = _unique_strings([*(existing.get("evidence_refs") or []), *(edge.get("evidence_refs") or [])])[:20]
        if float(edge.get("confidence") or 0.0) > float(existing.get("confidence") or 0.0):
            existing["confidence"] = edge.get("confidence")
            existing["promotion_status"] = edge.get("promotion_status")
            existing["source_layer"] = edge.get("source_layer")
    return sorted(by_id.values(), key=lambda row: (row["relationship_type"], row["from_node_id"], row["to_node_id"]))


def _slot_confidence(slot: Mapping[str, Any]) -> float:
    status = str(slot.get("slot_status") or "")
    base = {
        "product_kpi_exact_slot": 0.95,
        "filings_taxonomy_slot": 0.88,
        "official_surface_slot": 0.85,
        "bounded_context_slot": 0.72,
        "company_route_needs_family_binding": 0.48,
        "seed_needs_locator": 0.32,
        "source_discovery_needed": 0.2,
    }.get(status, 0.3)
    return min(base, float(slot.get("assignment_confidence") or base))


def _slot_source_layer(slot: Mapping[str, Any]) -> str:
    status = str(slot.get("slot_status") or "")
    if status == "product_kpi_exact_slot":
        return "L1_exact_company_disclosure"
    if status == "filings_taxonomy_slot":
        return "L1_company_disclosure_taxonomy"
    if status == "official_surface_slot":
        return "L2_official_product_surface"
    if status == "bounded_context_slot":
        return "L2_L3_bounded_context"
    return "retrieval_planning_gap"


def _slot_allowed_claims(status: str) -> list[str]:
    if status == "product_kpi_exact_slot":
        return ["company_disclosed_product_kpi", "product_taxonomy", "product_financial_bridge"]
    if status == "filings_taxonomy_slot":
        return ["company_disclosed_product_taxonomy", "product_segment_retrieval_planning", "product_financial_bridge_context"]
    if status == "official_surface_slot":
        return ["official_product_surface", "product_taxonomy_context", "product_spec_context"]
    return ["bounded_context", "retrieval_planning"]


def _slot_claim_boundary(status: str) -> str:
    if status == "product_kpi_exact_slot":
        return "Company-disclosed product KPI slot; exact value authority is limited to cited metric/period/unit/product row."
    if status == "filings_taxonomy_slot":
        return "Company filing product/segment taxonomy slot; supports disclosed business/product taxonomy and retrieval planning, not product sales/share/ASP unless a metric row is separately cited."
    if status == "official_surface_slot":
        return "Official product surface slot; supports product existence/spec/taxonomy, not sales/share/ASP/inventory."
    if status == "bounded_context_slot":
        return "Bounded public context slot; supports direction and retrieval planning, not company exact financial facts."
    return "Planning/gap slot only; do not use as product fact without repair."


def _row_is_product_relevant(row: Mapping[str, Any]) -> bool:
    source_ids = _row_source_ids(row)
    if source_ids.intersection(TAXONOMY_PRODUCT_SOURCE_IDS):
        return _taxonomy_row_valid(row)
    if source_ids.intersection(EXACT_PRODUCT_SOURCE_IDS | OFFICIAL_PRODUCT_SOURCE_IDS):
        return True
    claim_text = " ".join(str(item) for item in row.get("claim_types") or []).lower()
    structured_type = str(row.get("structured_context_type") or row.get("fact_type") or "").lower()
    return any(term in claim_text or term in structured_type for term in ["product", "technology", "clinical", "vehicle_model", "developer", "channel_offer"])


def _row_product_name(row: Mapping[str, Any]) -> str:
    for key in ("product_or_segment", "canonical_name", "product_family", "topic", "fact_label", "matched_product_alias"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _best_product_name(rows: Sequence[Mapping[str, Any]], *, default: str) -> str:
    names = [_normalize_product_name(_row_product_name(row)) for row in rows]
    names = [name for name in names if name]
    if not names:
        return default
    return Counter(names).most_common(1)[0][0]


def _normalize_product_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    text = text.strip(" -:|")
    if not text or text.lower() in {"product", "products", "services", "official product surface"}:
        return ""
    lower = text.lower()
    if lower in PRODUCT_SLOT_NAME_BLOCKLIST or any(pattern in lower for pattern in PRODUCT_SLOT_NAME_BLOCK_PATTERNS):
        return ""
    if lower.endswith("products &") or lower.endswith("services &"):
        return ""
    if text.endswith(".") and not _product_name_has_model_signal(text):
        return ""
    if re.search(r"\b(benefit|browse|continue|designed|everything|explore|homepage|peace of mind|switching from)\b", lower):
        return ""
    if len(text.split()) > 9:
        return ""
    return text[:160]


def _product_name_has_model_signal(value: str) -> bool:
    return bool(
        re.search(
            r"\b(airpods|apple watch|blackwell|cuda|dgx|duv|euv|exe|gb[0-9]+|h[0-9]{3}|hgx|iphone|ipad|"
            r"lithography|mac|nvl[0-9]+|nxe|nvlink|poweredge|proliant|rtx|watch)\b",
            str(value or "").lower(),
        )
    )


def _family_terms(assignment: Mapping[str, Any]) -> list[str]:
    terms = [
        assignment.get("family_id"),
        assignment.get("family_name"),
        *(assignment.get("query_terms") or []),
        *(assignment.get("family_aliases") or []),
        *(assignment.get("matched_terms") or []),
    ]
    return _unique_strings(terms)


def _row_text(row: Mapping[str, Any]) -> str:
    citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
    binding = row.get("entity_binding") if isinstance(row.get("entity_binding"), Mapping) else {}
    values = [
        row.get("product_family"),
        row.get("product_or_segment"),
        row.get("canonical_name"),
        " ".join(row.get("aliases") or []),
        row.get("node_type"),
        row.get("topic"),
        row.get("fact_label"),
        row.get("fact_value"),
        row.get("metric_name"),
        row.get("title"),
        row.get("source_title"),
        row.get("preview"),
        row.get("text"),
        row.get("structured_context_summary"),
        citation.get("title"),
        " ".join(binding.get("product_matched_terms") or []),
    ]
    return " ".join(str(value) for value in values if value).lower()


def _text_matches_terms(text: str, terms: Sequence[str]) -> bool:
    text_l = str(text or "").lower()
    for term in terms:
        term_l = str(term or "").lower().replace("_", " ").strip()
        if not term_l:
            continue
        if term_l in WEAK_GRAPH_MATCH_TERMS:
            continue
        if len(term_l) <= 3:
            if re.search(rf"\b{re.escape(term_l)}\b", text_l):
                return True
            continue
        if term_l in text_l:
            return True
        words = [word for word in re.split(r"[^a-z0-9]+", term_l) if len(word) > 3 and word not in WEAK_GRAPH_MATCH_TERMS]
        for word in words:
            variants = {word}
            if word.endswith("ing") and len(word) > 6:
                variants.add(word[:-3])
            if word.endswith("ies") and len(word) > 5:
                variants.add(word[:-3] + "y")
            if word.endswith("y") and len(word) > 4:
                variants.add(word[:-1] + "ies")
            if word.endswith("s") and len(word) > 5:
                variants.add(word[:-1])
            if any(re.search(rf"\b{re.escape(variant)}\b", text_l) for variant in variants):
                return True
    return False


def _row_family_matches(row: Mapping[str, Any], *, family_id: str, family_terms: Sequence[str]) -> bool:
    row_family_id = str(row.get("family_id") or "").strip()
    if row_family_id:
        return row_family_id == family_id
    if _row_source_ids(row).intersection(EXACT_PRODUCT_SOURCE_IDS) and (_ticker(row), family_id) in LOOSE_EXACT_PRODUCT_FAMILY_BINDINGS:
        return True
    if _row_source_ids(row).intersection(TAXONOMY_PRODUCT_SOURCE_IDS) and _taxonomy_binding_whitelisted(row, family_id=family_id):
        return True
    if _row_source_ids(row).intersection(TAXONOMY_PRODUCT_SOURCE_IDS) and str(family_id or "").startswith(GENERIC_FAMILY_PREFIXES):
        return True
    return _text_matches_terms(_row_text(row), family_terms)


def _taxonomy_binding_whitelisted(row: Mapping[str, Any], *, family_id: str) -> bool:
    terms = TICKER_FAMILY_TAXONOMY_BINDING_TERMS.get((_ticker(row), family_id))
    if not terms:
        return False
    text = _row_text(row)
    return _text_matches_terms(text, terms)


def _taxonomy_row_valid(row: Mapping[str, Any]) -> bool:
    if str(row.get("promotion_status") or "") and "passed" not in str(row.get("promotion_status") or "").lower():
        return False
    name = _normalize_product_name(str(row.get("canonical_name") or ""))
    if not name:
        return False
    node_type = str(row.get("node_type") or "").lower()
    if node_type not in TAXONOMY_PRODUCT_NODE_TYPES | TAXONOMY_CONTEXT_NODE_TYPES:
        return False
    if float(row.get("max_candidate_confidence") or 0.0) < 0.58:
        return False
    lower = name.lower()
    taxonomy_noise = (
        "available information",
        "anticipated benefits",
        "business plans",
        "business results",
        "business strategy",
        "company strategy",
        "convertible senior notes",
        "each of which",
        "environmental",
        "financing",
        "following this",
        "fundamentals of",
        "general development",
        "general information",
        "industry overview",
        "introduction",
        "investor relations",
        "jurisdiction",
        "key 2024",
        "located in",
        "major subsidiaries",
        "matters",
        "narrative description",
        "note regarding",
        "ownership of ads",
        "potential security vulnerabilities",
        "principal industries",
        "recent highlights",
        "revolving credit facility",
        "risks relating",
        "service company subsidiary",
        "shares or adss",
        "strategy",
        "sustainability",
        "we use investor",
        "overview",
    )
    if any(term in lower for term in taxonomy_noise):
        return False
    return True


def _slot_is_relationship_ready(slot: Mapping[str, Any]) -> bool:
    return str(slot.get("slot_status") or "") in {"product_kpi_exact_slot", "filings_taxonomy_slot", "official_surface_slot", "bounded_context_slot"}


def _row_ref(row: Mapping[str, Any]) -> str:
    return str(row.get("evidence_ref") or row.get("evidence_id") or row.get("snapshot_id") or row.get("record_id") or "").strip()


def _sample_urls(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    urls: list[str] = []
    for row in rows:
        citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
        urls.append(str(row.get("source_url") or row.get("url") or row.get("snapshot_url") or citation.get("url") or "").strip())
        urls.extend(str(url).strip() for url in (row.get("source_urls") or []) if str(url).strip())
    return _unique_strings(urls)


def _sample_route_urls(routes: Iterable[Mapping[str, Any]]) -> list[str]:
    urls: list[str] = []
    for route in routes:
        urls.extend(route.get("sample_urls") or [])
    return _unique_strings(urls)


def _row_source_ids(row: Mapping[str, Any]) -> set[str]:
    values = {
        str(row.get("source_id") or "").strip(),
        str(row.get("underlying_source_id") or "").strip(),
        str(row.get("source_class") or "").strip(),
    }
    if str(row.get("schema_version") or "").startswith("fin_agent_company_product_taxonomy_normalized"):
        values.add("sec_product_taxonomy_normalized")
    return {value for value in values if value}


def _ticker(row: Mapping[str, Any]) -> str:
    direct = str(row.get("ticker") or row.get("issuer_ticker") or "").strip().upper()
    if direct:
        return direct
    binding = row.get("entity_binding") if isinstance(row.get("entity_binding"), Mapping) else {}
    return str(binding.get("issuer_ticker") or "").strip().upper()


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return text or "unknown"


def _stable_id(prefix: str, parts: Sequence[Any]) -> str:
    digest = hashlib.sha1("::".join(str(part) for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _unique_strings(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
