from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sec_agent.product_intelligence_runtime import normalize_product_intelligence_company_pack


AI_SEMIS_PRODUCT_EVIDENCE_PACK_SCHEMA_VERSION = "finsight_ai_semis_product_evidence_pack_v0_2"
AI_SEMIS_PRODUCT_DEPTH_GATE_SCHEMA_VERSION = "finsight_ai_semis_product_depth_gate_v0_2"

DEFAULT_AI_SEMIS_ROUTE_GATE_JSONL = "data/manifests/r18_ai_semis_source_route_gate_rows_v0_1.jsonl"
DEFAULT_PRODUCT_INTELLIGENCE_PACK_JSONL = "data/manifests/product_intelligence_company_pack_v0_1.jsonl"
DEFAULT_AI_SEMIS_PRODUCT_EVIDENCE_PACK_JSONL = "data/manifests/ai_semis_product_evidence_pack_v0_2.jsonl"

SOURCE_LAYER_FILES: dict[str, tuple[str, ...]] = {
    "product_profile": (
        "data/manifests/official_product_surface_context_rows_v0_1.jsonl",
        "data/manifests/company_disclosed_product_profile_context_rows_v0_1.jsonl",
    ),
    "product_spec_architecture": (
        "data/manifests/official_product_spec_context_rows_v0_1.jsonl",
        "data/manifests/targeted_official_technology_document_context_rows_v0_1.jsonl",
        "data/manifests/ai_semis_product_spec_followup_context_rows_v0_1.jsonl",
    ),
    "customer_deployment_adoption": (
        "data/manifests/official_customer_deployment_surface_context_rows_v0_1.jsonl",
        "data/manifests/targeted_supply_chain_official_relationship_context_rows_v0_1.jsonl",
        "data/manifests/public_contract_award_context_rows_v0_1.jsonl",
        "data/manifests/broad_public_contract_award_context_rows_v0_1.jsonl",
        "data/manifests/ai_semis_customer_deployment_followup_context_rows_v0_1.jsonl",
    ),
    "product_performance_proxy": (
        "data/manifests/family_channel_distributor_context_rows_v0_1.jsonl",
        "data/manifests/developer_ecosystem_context_rows_v0_1.jsonl",
        "data/manifests/v1_openalex_technology_research_context_rows_v0_1.jsonl",
        "data/manifests/v1_patentsview_technology_research_context_rows_v0_1.jsonl",
        "data/manifests/ai_semis_product_performance_proxy_followup_context_rows_v0_1.jsonl",
    ),
    "product_kpi_exact": (
        "data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
        "data/manifests/company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
        "data/manifests/non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
    ),
}

EXACT_KPI_BOUNDARY = (
    "Product-KPI exact remains strict: value/unit/period/product/citation rows from company disclosure or "
    "source-specific parser only. Product pages, benchmarks, customer news, and channel rows cannot be promoted "
    "to revenue, shipments, ASP, share, sell-through, inventory, backlog, or order-value facts."
)
CONTEXT_BOUNDARY = (
    "Bounded product intelligence context. May support product capability, taxonomy, adoption, channel, "
    "technology, customer/deployment, or relationship thesis drivers inside the cited boundary; cannot become "
    "undisclosed financial or operating exact evidence."
)

EDGE_AUTHORITY_TO_ROLE = {
    "competitive_context_candidate": "competitive_context_candidate",
    "supply_chain_signal": "supply_chain_signal",
    "deployment_signal_authority": "customer_deployment_signal",
    "channel_presence_signal": "channel_presence_signal",
    "technical_fact_authority": "technical_fact_signal",
    "exact_product_kpi_authority": "exact_product_kpi_signal",
    "industry_operating_metric_authority": "operating_metric_signal",
    "product_profile_authority": "product_profile_signal",
}


def ai_semis_product_evidence_packs_from_state(
    state: Mapping[str, Any],
    *,
    tickers: Sequence[str] | None = None,
    repo_root: str | Path | None = None,
    max_packs: int = 16,
    autoload: bool | None = None,
) -> list[dict[str, Any]]:
    packs = _explicit_depth_packs_from_state(state)
    wanted = _ticker_set(tickers) or _ticker_set(_state_tickers(state))
    if packs:
        filtered = [pack for pack in packs if not wanted or _ticker(pack) in wanted]
        return filtered[: max(0, int(max_packs or 0))]
    should_load = bool(state.get("product_intelligence_runtime_autoload", True)) if autoload is None else bool(autoload)
    if not should_load or not wanted:
        return []
    return load_ai_semis_product_evidence_packs(
        repo_root or Path.cwd(),
        tickers=sorted(wanted),
        max_packs=max_packs,
    )


def compact_ai_semis_product_evidence_pack_refs(
    state: Mapping[str, Any],
    *,
    tickers: Sequence[str] | None = None,
    repo_root: str | Path | None = None,
    max_packs: int = 8,
    autoload: bool | None = None,
) -> dict[str, Any]:
    packs = ai_semis_product_evidence_packs_from_state(
        state,
        tickers=tickers,
        repo_root=repo_root,
        max_packs=max_packs,
        autoload=autoload,
    )
    return {
        "schema_version": AI_SEMIS_PRODUCT_EVIDENCE_PACK_SCHEMA_VERSION,
        "pack_count": len(packs),
        "packs": [_compact_depth_pack(pack) for pack in packs],
        "policy": "product_evidence_pack_v0_2_separates_specs_deployment_proxy_kpi_relationship_and_boundaries",
    }


def load_ai_semis_product_evidence_packs(
    repo_root: str | Path,
    *,
    tickers: Sequence[str],
    jsonl_path: str = DEFAULT_AI_SEMIS_PRODUCT_EVIDENCE_PACK_JSONL,
    max_packs: int = 16,
) -> list[dict[str, Any]]:
    path = Path(repo_root) / jsonl_path
    wanted = _ticker_set(tickers)
    if not path.exists() or not wanted:
        return []
    packs: list[dict[str, Any]] = []
    for row in _load_jsonl(path):
        if _ticker(row) in wanted:
            packs.append(normalize_ai_semis_product_evidence_pack(row))
            if len(packs) >= max(0, int(max_packs or 0)):
                break
    return packs


def normalize_ai_semis_product_evidence_pack(value: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(value)
    row["schema_version"] = str(row.get("schema_version") or AI_SEMIS_PRODUCT_EVIDENCE_PACK_SCHEMA_VERSION)
    row["ticker"] = _ticker(row)
    row["layers"] = {
        str(key): dict(layer)
        for key, layer in (row.get("layers") or {}).items()
        if isinstance(layer, Mapping)
    }
    row["pack_id"] = str(row.get("pack_id") or f"ai_semis_product_evidence_pack:{row['ticker']}")
    return row


def build_ai_semis_product_evidence_packs(
    *,
    route_gate_rows: Iterable[Mapping[str, Any]],
    product_intelligence_pack_rows: Iterable[Mapping[str, Any]],
    source_rows_by_layer: Mapping[str, Iterable[Mapping[str, Any]]] | None = None,
    generated_at: str,
    max_examples_per_layer: int = 8,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    route_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in route_gate_rows:
        ticker = _ticker(row)
        if ticker:
            route_by_ticker[ticker].append(dict(row))
    v1_tickers = set(route_by_ticker)
    pig_by_ticker: dict[str, dict[str, Any]] = {}
    for row in product_intelligence_pack_rows:
        ticker = _ticker(row)
        if ticker in v1_tickers:
            pig_by_ticker[ticker] = normalize_product_intelligence_company_pack(row)
    evidence_by_layer: dict[str, dict[str, list[dict[str, Any]]]] = {
        layer: defaultdict(list) for layer in SOURCE_LAYER_FILES
    }
    for layer, rows in (source_rows_by_layer or {}).items():
        if layer not in evidence_by_layer:
            continue
        for row in rows:
            ticker = _ticker(row)
            if ticker in v1_tickers:
                evidence_by_layer[layer][ticker].append(dict(row))

    packs: list[dict[str, Any]] = []
    gap_queue: list[dict[str, Any]] = []
    for ticker in sorted(v1_tickers):
        pack = _build_one_pack(
            ticker=ticker,
            route_rows=route_by_ticker.get(ticker, []),
            pig_pack=pig_by_ticker.get(ticker, {}),
            evidence_by_layer={layer: dict(rows_by_ticker) for layer, rows_by_ticker in evidence_by_layer.items()},
            generated_at=generated_at,
            max_examples_per_layer=max_examples_per_layer,
        )
        packs.append(pack)
        if pack.get("depth_status") not in {"pass", "pass_with_public_boundary"}:
            gap_queue.append(_gap_queue_row(pack))
        elif pack.get("strict_depth_status") != "pass":
            gap_queue.append(_gap_queue_row(pack, action_status="strict_depth_followup"))
    gate = build_ai_semis_product_depth_gate(packs=packs, gap_queue=gap_queue, generated_at=generated_at)
    return packs, gate, gap_queue


def build_ai_semis_product_depth_gate(
    *,
    packs: Sequence[Mapping[str, Any]],
    gap_queue: Sequence[Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    status_counts = Counter(str(pack.get("depth_status") or "") for pack in packs)
    strict_counts = Counter(str(pack.get("strict_depth_status") or "") for pack in packs)
    layer_status_counts: dict[str, dict[str, int]] = {}
    gap_reasons = Counter()
    for pack in packs:
        layers = pack.get("layers") if isinstance(pack.get("layers"), Mapping) else {}
        for layer_name, layer in layers.items():
            if isinstance(layer, Mapping):
                layer_status_counts.setdefault(str(layer_name), Counter())
                layer_status_counts[str(layer_name)][str(layer.get("status") or "absent")] += 1
        for reason in pack.get("gap_reasons") or []:
            gap_reasons[str(reason)] += 1
    return {
        "schema_version": AI_SEMIS_PRODUCT_DEPTH_GATE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if status_counts.get("needs_deep_repair", 0) == 0 else "needs_repair",
        "company_count": len(packs),
        "depth_status_counts": dict(sorted(status_counts.items())),
        "strict_depth_status_counts": dict(sorted(strict_counts.items())),
        "layer_status_counts": {
            key: dict(sorted(Counter(value).items())) for key, value in sorted(layer_status_counts.items())
        },
        "gap_reason_counts": dict(sorted(gap_reasons.items())),
        "gap_queue_count": len(gap_queue),
        "gate_policy": {
            "main_depth_pass": (
                "profile plus at least two independent non-profile evidence roles, or profile-depth plus exact KPI "
                "when public sources expose product/business performance but not specs/deployment."
            ),
            "strict_depth_pass": (
                "profile plus at least four evidence roles and a relationship/adoption/proxy path; exact Product-KPI "
                "remains a separate strict row."
            ),
            "route_gate_boundary": "route-only, seed-only, and not-materialized roles never count as evidence depth.",
            "memo_boundary": "Memo may use non-financial product evidence for bounded thesis drivers, not exact financial promotion.",
        },
        "representative_gap_tickers": [
            {
                "ticker": str(pack.get("ticker") or ""),
                "company_name": str(pack.get("company_name") or ""),
                "depth_status": str(pack.get("depth_status") or ""),
                "strict_depth_status": str(pack.get("strict_depth_status") or ""),
                "gap_reasons": list(pack.get("gap_reasons") or [])[:8],
            }
            for pack in packs
            if pack.get("strict_depth_status") != "pass"
        ][:24],
    }


def load_source_rows_by_layer(repo_root: str | Path) -> dict[str, list[dict[str, Any]]]:
    root = Path(repo_root)
    rows_by_layer: dict[str, list[dict[str, Any]]] = {}
    for layer, files in SOURCE_LAYER_FILES.items():
        rows: list[dict[str, Any]] = []
        for file_name in files:
            rows.extend(_load_jsonl(root / file_name))
        rows_by_layer[layer] = rows
    return rows_by_layer


def _build_one_pack(
    *,
    ticker: str,
    route_rows: list[dict[str, Any]],
    pig_pack: Mapping[str, Any],
    evidence_by_layer: Mapping[str, Mapping[str, list[dict[str, Any]]]],
    generated_at: str,
    max_examples_per_layer: int,
) -> dict[str, Any]:
    counts = dict(pig_pack.get("counts") or {})
    company_name = str(pig_pack.get("company_name") or _first(route_rows, "company_name") or "")
    family_ids = sorted(
        {
            *_strings(pig_pack.get("family_ids")),
            *[str(row.get("family_id") or "") for row in route_rows if str(row.get("family_id") or "").strip()],
        }
    )
    route_state = _route_state(route_rows)
    layer_inputs = {
        layer: [dict(row) for row in evidence_by_layer.get(layer, {}).get(ticker, [])]
        for layer in SOURCE_LAYER_FILES
    }
    pig_profile_rows = [*_items(pig_pack.get("representative_product_slots")), *_items(pig_pack.get("representative_product_profile_or_specs"))]
    pig_kpi_rows = [*_items(pig_pack.get("representative_exact_kpis")), *_items(pig_pack.get("representative_operating_metrics"))]
    pig_deployment_rows = _items(pig_pack.get("representative_deployment_rows"))
    relationship_rows = _typed_relationship_rows(pig_pack, layer_inputs)

    layers = {
        "product_profile": _profile_layer(
            rows=[*pig_profile_rows, *layer_inputs["product_profile"]],
            route_state=route_state,
            counts=counts,
            max_examples=max_examples_per_layer,
        ),
        "product_spec_architecture": _evidence_layer(
            layer_id="product_spec_architecture",
            rows=[*layer_inputs["product_spec_architecture"], *_spec_like_pig_rows(pig_profile_rows)],
            route_state=route_state,
            positive_status="evidence_ready",
            boundary=CONTEXT_BOUNDARY,
            max_examples=max_examples_per_layer,
        ),
        "customer_deployment_adoption": _evidence_layer(
            layer_id="customer_deployment_adoption",
            rows=[*pig_deployment_rows, *layer_inputs["customer_deployment_adoption"]],
            route_state=route_state,
            positive_status="evidence_ready",
            boundary=CONTEXT_BOUNDARY,
            max_examples=max_examples_per_layer,
        ),
        "product_performance_proxy": _evidence_layer(
            layer_id="product_performance_proxy",
            rows=layer_inputs["product_performance_proxy"],
            route_state=route_state,
            positive_status="evidence_ready",
            boundary=CONTEXT_BOUNDARY,
            max_examples=max_examples_per_layer,
        ),
        "product_kpi_exact": _evidence_layer(
            layer_id="product_kpi_exact",
            rows=[*pig_kpi_rows, *layer_inputs["product_kpi_exact"]],
            route_state=route_state,
            positive_status="exact_or_operating_metric_ready",
            boundary=EXACT_KPI_BOUNDARY,
            max_examples=max_examples_per_layer,
        ),
        "product_relationship_graph": _relationship_layer(
            rows=relationship_rows,
            route_state=route_state,
            max_examples=max_examples_per_layer,
        ),
    }
    scoring = _score_depth(layers)
    gap_reasons = _gap_reasons(layers=layers, scoring=scoring, route_state=route_state)
    return {
        "schema_version": AI_SEMIS_PRODUCT_EVIDENCE_PACK_SCHEMA_VERSION,
        "generated_at": generated_at,
        "pack_id": f"ai_semis_product_evidence_pack:{ticker}",
        "ticker": ticker,
        "company_name": company_name,
        "primary_lane_id": "V1",
        "primary_lane_name": "Semiconductors / AI Infrastructure",
        "family_ids": family_ids,
        "family_names": sorted({str(row.get("family_name") or "") for row in route_rows if str(row.get("family_name") or "").strip()}),
        "source_route_state": route_state,
        "layers": layers,
        "evidence_role_count": scoring["evidence_role_count"],
        "non_profile_role_count": scoring["non_profile_role_count"],
        "strict_depth_status": scoring["strict_depth_status"],
        "depth_status": scoring["depth_status"],
        "gap_reasons": gap_reasons,
        "claim_boundaries": {
            "product_kpi_exact": EXACT_KPI_BOUNDARY,
            "non_financial_product_evidence": CONTEXT_BOUNDARY,
            "route_gate": "route-ready or seed-only rows are retrieval instructions, not evidence rows.",
        },
        "memo_writer_boundary": (
            "Memo Writer must consume this pack through Research Lead / MemoLogicPlan. Non-financial product layers "
            "can support bounded product capability, adoption, competition, or demand-direction claims; only "
            "product_kpi_exact rows support exact product/business operating metrics."
        ),
    }


def _profile_layer(
    *,
    rows: list[dict[str, Any]],
    route_state: Mapping[str, Any],
    counts: Mapping[str, Any],
    max_examples: int,
) -> dict[str, Any]:
    row_count = len(rows)
    product_slot_count = int(counts.get("product_slot_count") or 0)
    status = "detailed_profile_ready" if row_count >= 5 or product_slot_count >= 3 else ("evidence_ready" if row_count else "absent")
    return {
        "layer_id": "product_profile",
        "status": status,
        "row_count": row_count,
        "product_slot_count": product_slot_count,
        "exact_value_authority": False,
        "claim_scope": "issuer_product_taxonomy_and_product_line_identity",
        "examples": [_compact_source_row(row, layer_id="product_profile") for row in rows[:max_examples]],
        "route_materialization": _role_materialization(route_state, {"official_product_surface", "primary_company_disclosure"}),
        "claim_boundary": "Company/issuer product, service, or business-line identity context only; no sales/share/ASP/order-value authority.",
    }


def _evidence_layer(
    *,
    layer_id: str,
    rows: list[dict[str, Any]],
    route_state: Mapping[str, Any],
    positive_status: str,
    boundary: str,
    max_examples: int,
) -> dict[str, Any]:
    rows = [dict(row) for row in rows if _row_has_runtime_content(row)]
    return {
        "layer_id": layer_id,
        "status": positive_status if rows else "absent",
        "row_count": len(rows),
        "exact_value_authority": layer_id == "product_kpi_exact",
        "claim_scope": _claim_scope_for_layer(layer_id),
        "examples": [_compact_source_row(row, layer_id=layer_id) for row in rows[:max_examples]],
        "route_materialization": _role_materialization(route_state, _roles_for_layer(layer_id)),
        "claim_boundary": boundary,
    }


def _relationship_layer(
    *,
    rows: list[dict[str, Any]],
    route_state: Mapping[str, Any],
    max_examples: int,
) -> dict[str, Any]:
    typed_counts = Counter(str(row.get("relationship_role") or row.get("edge_type") or "unknown") for row in rows)
    return {
        "layer_id": "product_relationship_graph",
        "status": "evidence_ready" if rows else "absent",
        "row_count": len(rows),
        "relationship_role_counts": dict(sorted(typed_counts.items())),
        "exact_value_authority": False,
        "claim_scope": "bounded_product_relationship_context",
        "examples": [_compact_source_row(row, layer_id="product_relationship_graph") for row in rows[:max_examples]],
        "route_materialization": _role_materialization(
            route_state,
            {
                "channel_offer_proxy",
                "public_order_proxy",
                "supply_chain_official_relationship",
                "official_customer_order_or_deployment_event",
                "trusted_external_context",
            },
        ),
        "claim_boundary": (
            "Relationship edges guide competition/substitution/upstream/downstream/deployment/read-through analysis; "
            "they do not prove revenue, share, shipments, ASP, inventory, sell-through, backlog, or order value."
        ),
    }


def _score_depth(layers: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    present = {
        layer_id: str(layer.get("status") or "") not in {"", "absent"}
        for layer_id, layer in layers.items()
    }
    non_profile = sum(1 for layer_id, value in present.items() if layer_id != "product_profile" and value)
    role_count = sum(1 for value in present.values() if value)
    strict = (
        present.get("product_profile")
        and role_count >= 4
        and (
            present.get("product_relationship_graph")
            or present.get("customer_deployment_adoption")
            or present.get("product_performance_proxy")
        )
    )
    public_boundary = (
        present.get("product_profile")
        and present.get("product_kpi_exact")
        and str(layers.get("product_profile", {}).get("status") or "") == "detailed_profile_ready"
    )
    if strict:
        depth = "pass"
    elif present.get("product_profile") and non_profile >= 2:
        depth = "pass_with_public_boundary"
    elif public_boundary:
        depth = "pass_with_public_boundary"
    else:
        depth = "needs_deep_repair"
    return {
        "evidence_role_count": role_count,
        "non_profile_role_count": non_profile,
        "strict_depth_status": "pass" if strict else "needs_strict_depth_followup",
        "depth_status": depth,
    }


def _gap_reasons(
    *,
    layers: Mapping[str, Mapping[str, Any]],
    scoring: Mapping[str, Any],
    route_state: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    for layer_id, layer in layers.items():
        if str(layer.get("status") or "") == "absent":
            materialization = _role_materialization(route_state, _roles_for_layer(layer_id))
            if materialization.get("seed_or_route_only_roles") or materialization.get("not_materialized_roles"):
                reasons.append(f"{layer_id}:route_or_seed_available_but_no_runtime_row")
            else:
                reasons.append(f"{layer_id}:no_public_runtime_row")
    if scoring.get("strict_depth_status") != "pass":
        reasons.append("strict_depth:missing_four_role_or_relationship_adoption_proxy_path")
    if scoring.get("depth_status") == "needs_deep_repair":
        reasons.append("main_depth:insufficient_non_profile_evidence_roles")
    return reasons[:16]


def _typed_relationship_rows(
    pig_pack: Mapping[str, Any],
    layer_inputs: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _items(pig_pack.get("representative_relationship_edges")):
        if not bool(item.get("can_enter_evidence_bundle")):
            continue
        authority = str(item.get("authority_type") or "")
        if authority in {"template_context_edge", "product_taxonomy_context"}:
            continue
        rows.append(
            {
                **item,
                "relationship_role": EDGE_AUTHORITY_TO_ROLE.get(authority, authority or str(item.get("edge_type") or "")),
                "source_class": "product_intelligence_relationship_edge",
                "claim_boundary": str(item.get("claim_boundary") or CONTEXT_BOUNDARY),
            }
        )
    for layer_id, role in (
        ("customer_deployment_adoption", "customer_deployment_or_order_signal"),
        ("product_performance_proxy", "performance_proxy_signal"),
    ):
        for row in layer_inputs.get(layer_id, []):
            rows.append(
                {
                    **row,
                    "relationship_role": _relationship_role_from_row(row, default=role),
                    "edge_type": _relationship_edge_type_from_row(row),
                    "source_class": str(row.get("source_id") or row.get("source_role") or layer_id),
                    "claim_boundary": str(row.get("claim_boundary") or CONTEXT_BOUNDARY),
                }
            )
    return _dedupe_rows(rows)


def _relationship_role_from_row(row: Mapping[str, Any], *, default: str) -> str:
    text = _row_text(row)
    if "contract" in text or "award" in text or "order" in text or "tender" in text:
        return "ordered_by_or_public_award_proxy"
    if "customer" in text or "case" in text or "deploy" in text:
        return "deployed_by_or_adopted_by"
    if "supply" in text or "partner" in text or "alliance" in text:
        return "supply_chain_or_partner_signal"
    if "github" in text or "developer" in text or "openalex" in text or "patent" in text:
        return "technology_or_developer_proxy"
    if "channel" in text or "distributor" in text or "store" in text:
        return "sold_through_or_channel_presence"
    return default


def _relationship_edge_type_from_row(row: Mapping[str, Any]) -> str:
    role = _relationship_role_from_row(row, default="")
    if role == "ordered_by_or_public_award_proxy":
        return "ordered_by_or_awarded_to"
    if role == "deployed_by_or_adopted_by":
        return "deployed_by_or_adopted_by"
    if role == "supply_chain_or_partner_signal":
        return "partnered_with_or_supplies_to"
    if role == "technology_or_developer_proxy":
        return "technology_research_or_ecosystem_proxy"
    if role == "sold_through_or_channel_presence":
        return "sold_through_or_channel_presence"
    return "product_context_relationship"


def _spec_like_pig_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("value") or "").strip() and str(row.get("unit") or "").strip():
            out.append(row)
            continue
        text = _row_text(row)
        if any(term in text for term in ("core", "memory", "bandwidth", "capacity", "kw", "tops", "flops", "architecture")):
            out.append(row)
    return out


def _route_state(route_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    route_status_counts = Counter()
    materialized_roles: set[str] = set()
    seed_or_route_only_roles: set[str] = set()
    not_materialized_roles: set[str] = set()
    group_summaries: list[dict[str, Any]] = []
    for row in route_rows:
        for group in row.get("group_results") or []:
            if not isinstance(group, Mapping):
                continue
            statuses = {
                str(role): str(status)
                for role, status in (group.get("route_statuses") or {}).items()
            }
            for role, status in statuses.items():
                route_status_counts[status] += 1
                if status.startswith("runtime_") and status.endswith("_available"):
                    materialized_roles.add(role)
                elif status in {"seed_available_not_materialized", "route_available_not_materialized"}:
                    seed_or_route_only_roles.add(role)
                elif status in {"not_materialized", "not_in_family_route_plan"}:
                    not_materialized_roles.add(role)
            group_summaries.append(
                {
                    "family_id": str(row.get("family_id") or ""),
                    "group_id": str(group.get("group_id") or ""),
                    "status": str(group.get("status") or ""),
                    "route_statuses": statuses,
                }
            )
    return {
        "family_row_count": len(route_rows),
        "materialized_roles": sorted(materialized_roles),
        "seed_or_route_only_roles": sorted(seed_or_route_only_roles),
        "not_materialized_roles": sorted(not_materialized_roles),
        "route_status_counts": dict(sorted(route_status_counts.items())),
        "group_summaries": group_summaries[:12],
    }


def _role_materialization(route_state: Mapping[str, Any], roles: set[str]) -> dict[str, Any]:
    materialized = sorted(set(route_state.get("materialized_roles") or []) & roles)
    seed_only = sorted(set(route_state.get("seed_or_route_only_roles") or []) & roles)
    not_materialized = sorted(set(route_state.get("not_materialized_roles") or []) & roles)
    return {
        "materialized_roles": materialized,
        "seed_or_route_only_roles": seed_only,
        "not_materialized_roles": not_materialized,
        "materialized_route_available": bool(materialized),
        "counts_as_evidence": False,
    }


def _roles_for_layer(layer_id: str) -> set[str]:
    if layer_id == "product_profile":
        return {"official_product_surface", "primary_company_disclosure"}
    if layer_id == "product_spec_architecture":
        return {"technical_product_spec", "official_product_surface", "technology_research_proxy"}
    if layer_id == "customer_deployment_adoption":
        return {"official_customer_order_or_deployment_event", "public_order_proxy", "supply_chain_official_relationship"}
    if layer_id == "product_performance_proxy":
        return {"channel_offer_proxy", "developer_ecosystem_proxy", "technology_research_proxy", "trusted_external_context"}
    if layer_id == "product_kpi_exact":
        return {"primary_company_disclosure", "company_disclosed_product_kpi"}
    if layer_id == "product_relationship_graph":
        return {
            "channel_offer_proxy",
            "official_customer_order_or_deployment_event",
            "public_order_proxy",
            "supply_chain_official_relationship",
            "trusted_external_context",
        }
    return set()


def _claim_scope_for_layer(layer_id: str) -> str:
    return {
        "product_spec_architecture": "technical_product_capability_or_architecture",
        "customer_deployment_adoption": "customer_deployment_adoption_order_or_supply_chain_context",
        "product_performance_proxy": "public_nonfinancial_product_performance_proxy",
        "product_kpi_exact": "company_disclosed_product_or_business_metric_exact",
    }.get(layer_id, "bounded_product_context")


def _compact_source_row(row: Mapping[str, Any], *, layer_id: str) -> dict[str, Any]:
    source_id = str(
        row.get("source_row_id")
        or row.get("gold_row_id")
        or row.get("fact_id")
        or row.get("product_slot_id")
        or row.get("edge_id")
        or row.get("source_id")
        or _stable_id(layer_id, row)
    )
    return {
        "source_ref": source_id,
        "source_id": str(row.get("source_id") or row.get("source_class") or ""),
        "source_role": str(row.get("source_role") or ""),
        "source_layer": str(row.get("source_layer") or ""),
        "product_family": str(row.get("product_family") or row.get("family_name") or ""),
        "product_or_segment": str(row.get("product_or_segment") or row.get("product_slot_name") or ""),
        "metric_name": str(row.get("metric_name") or row.get("fact_type") or ""),
        "value": row.get("value") if row.get("value") not in (None, "") else "",
        "unit": str(row.get("unit") or ""),
        "period": str(row.get("period") or ""),
        "counterparty": str(row.get("counterparty") or row.get("customer") or row.get("recipient") or ""),
        "citation_url": str(row.get("citation_url") or row.get("source_url") or row.get("url") or ""),
        "relationship_role": str(row.get("relationship_role") or ""),
        "edge_type": str(row.get("edge_type") or row.get("relationship_type") or ""),
        "claim_boundary": str(row.get("claim_boundary") or ""),
    }


def _gap_queue_row(pack: Mapping[str, Any], *, action_status: str = "needs_deep_repair") -> dict[str, Any]:
    return {
        "schema_version": "finsight_ai_semis_product_depth_gap_queue_v0_2",
        "ticker": str(pack.get("ticker") or ""),
        "company_name": str(pack.get("company_name") or ""),
        "primary_lane_id": "V1",
        "action_status": action_status,
        "depth_status": str(pack.get("depth_status") or ""),
        "strict_depth_status": str(pack.get("strict_depth_status") or ""),
        "missing_or_boundary_reasons": list(pack.get("gap_reasons") or [])[:16],
        "recommended_next_actions": _recommended_next_actions(pack),
    }


def _recommended_next_actions(pack: Mapping[str, Any]) -> list[str]:
    reasons = " ".join(pack.get("gap_reasons") or [])
    actions: list[str] = []
    if "product_spec_architecture" in reasons:
        actions.append("run official product spec / datasheet / architecture locator with browser-rendered fetch when issuer site blocks requests")
    if "customer_deployment_adoption" in reasons:
        actions.append("run official customer case-study / partner / public order adapter and keep event facts separate from order-value exact")
    if "product_performance_proxy" in reasons:
        actions.append("run benchmark, developer ecosystem, OpenAlex/PatentsView, channel availability, or trusted external context adapters")
    if "product_relationship_graph" in reasons:
        actions.append("add parser-backed relationship edges; same-family taxonomy alone is not sufficient")
    if "product_kpi_exact" in reasons:
        actions.append("deep-parse IR deck, annual report table, local filing, or SEC table for value/unit/period/product rows")
    return actions or ["review source route materialization and parser row binding"]


def _row_has_runtime_content(row: Mapping[str, Any]) -> bool:
    return bool(
        _ticker(row)
        or str(row.get("product_family") or row.get("product_or_segment") or row.get("metric_name") or row.get("source_url") or row.get("citation_url") or row.get("url") or "").strip()
    )


def _row_text(row: Mapping[str, Any]) -> str:
    return " ".join(str(row.get(key) or "") for key in row.keys()).lower()


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = "|".join(
            str(row.get(field) or "")
            for field in ("source_row_id", "gold_row_id", "fact_id", "edge_id", "source_id", "source_url", "citation_url", "product_or_segment", "metric_name")
        )
        if not key.strip("|"):
            key = _stable_id("row", row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _compact_depth_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    layers = pack.get("layers") if isinstance(pack.get("layers"), Mapping) else {}
    return {
        "pack_id": str(pack.get("pack_id") or ""),
        "ticker": _ticker(pack),
        "company_name": str(pack.get("company_name") or ""),
        "family_ids": [str(item) for item in pack.get("family_ids") or []][:12],
        "depth_status": str(pack.get("depth_status") or ""),
        "strict_depth_status": str(pack.get("strict_depth_status") or ""),
        "evidence_role_count": int(pack.get("evidence_role_count") or 0),
        "layer_statuses": {
            str(layer_id): str(layer.get("status") or "")
            for layer_id, layer in layers.items()
            if isinstance(layer, Mapping)
        },
        "gap_reasons": [str(item) for item in pack.get("gap_reasons") or []][:8],
        "memo_writer_boundary": str(pack.get("memo_writer_boundary") or ""),
    }


def _explicit_depth_packs_from_state(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    for key in ("ai_semis_product_evidence_pack", "product_evidence_pack"):
        value = state.get(key)
        if isinstance(value, Mapping):
            candidates.append(value)
    for key in ("ai_semis_product_evidence_packs", "product_evidence_packs"):
        value = state.get(key)
        if isinstance(value, Mapping):
            candidates.extend(value.values())
        elif isinstance(value, list):
            candidates.extend(value)
    return [normalize_ai_semis_product_evidence_pack(row) for row in candidates if isinstance(row, Mapping)]


def _state_tickers(state: Mapping[str, Any]) -> list[str]:
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    scope = query_contract.get("scope") if isinstance(query_contract.get("scope"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    return [
        *_strings(state.get("focus_tickers")),
        *_strings(query_contract.get("focus_tickers")),
        *_strings(scope.get("focus_tickers")),
        *_strings(activation.get("focus_tickers")),
    ]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _items(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _ticker(value: Mapping[str, Any]) -> str:
    return str(value.get("ticker") or value.get("company_ticker") or "").upper().strip()


def _ticker_set(values: Sequence[str] | None) -> set[str]:
    return {str(item or "").upper().strip() for item in values or [] if str(item or "").strip()}


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item or "").strip()]
    return [str(value)] if str(value or "").strip() else []


def _first(rows: Sequence[Mapping[str, Any]], key: str) -> str:
    for row in rows:
        text = str(row.get(key) or "").strip()
        if text:
            return text
    return ""


def _stable_id(prefix: str, row: Mapping[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
    return f"{prefix}:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"
