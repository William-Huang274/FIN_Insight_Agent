from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse


L4_SOURCE_CLASSIFIER_SCHEMA_VERSION = "finsight_l4_source_classifier_v0_1"
WEAK_SIGNAL_LEAD_SCHEMA_VERSION = "finsight_l4_weak_signal_lead_v0_1"
WEAK_SIGNAL_EXCLUSION_NOTE_SCHEMA_VERSION = "finsight_l4_weak_signal_exclusion_note_v0_1"
L4_PROMOTION_ATTEMPT_SCHEMA_VERSION = "finsight_l4_promotion_attempt_v0_1"
L4_RUNTIME_STORE_SCHEMA_VERSION = "finsight_l4_runtime_store_v0_1"

L4_SOURCE_IDS = {
    "common_crawl_index",
    "generic_search_snippet",
    "search_snippet",
    "unverified_self_media_forums",
    "unverified_social_post",
    "forum_thread",
    "rumor_board",
    "yahoo_chart",
}

COMMERCIAL_GAP_SOURCE_IDS = {
    "commercial_market_data_and_consensus",
    "idc_trackers",
    "counterpoint_market_data",
    "gartner_tracker",
    "omdia_canalys_tracker",
    "sensor_tower",
    "similarweb",
    "iqvia_symphony",
    "circana_nielseniq",
    "sp_global_mobility",
}

L2_SOURCE_IDS = {
    "company_ir_reports",
    "company_product_pages",
    "official_social_accounts",
    "mainstream_financial_news",
    "supplier_customer_official_news",
    "industry_association_reports",
    "fred_api",
    "fred_graph_csv",
    "bls_public_api",
    "bea_data_api",
    "census_data_api",
    "eia_open_data",
    "fdic_bankfind_api",
    "clinicaltrials_api",
    "openfda_api",
    "cms_public_data",
    "nhtsa_vpic_api",
    "patentsview_api",
    "openalex_api",
}

L3_SOURCE_IDS = {
    "ecommerce_major_platforms",
    "app_store_rankings",
    "developer_ecosystem_github_npm_pypi_huggingface",
    "public_tenders_contracts_orders",
    "job_postings_hiring_signals",
    "channel_pricing_quotations",
    "platform_reviews_rankings_downloads",
}

UNVERIFIED_SOCIAL_DOMAINS = {
    "reddit.com",
    "www.reddit.com",
    "x.com",
    "twitter.com",
    "www.twitter.com",
    "weibo.com",
    "xueqiu.com",
    "www.xueqiu.com",
    "xiaohongshu.com",
    "www.xiaohongshu.com",
    "stocktwits.com",
    "www.stocktwits.com",
}

OFFICIAL_ACCOUNT_CLASSES = {
    "official_social_account",
    "verified_official_social_account",
    "company_verified_social_account",
}

L4_FORBIDDEN_CLAIM_SCOPES = (
    "revenue",
    "sales",
    "market_share",
    "asp",
    "sell_through",
    "inventory",
    "order_volume",
    "customer_adoption",
    "product_success",
    "technology_leadership",
    "management_intent",
    "exact_financial_fact",
    "core_thesis_evidence",
)

L4_ALLOWED_MEMO_SCOPES = {"weak_signal_exclusion", "source_gap", "targeted_repair_provenance"}

STRONG_BINDING_STATUSES = {
    "issuer_mentioned_in_snapshot",
    "company_domain_bound",
    "product_mentioned_in_snapshot",
    "technology_topic_bound",
    "counterparty_mentioned_in_snapshot",
    "relationship_context_candidate",
    "counterparty_keyword_context_candidate",
    "official_source_bound",
    "exact_ticker_match",
}


@dataclass(frozen=True)
class WeakSignalLead:
    lead_id: str
    source_id: str
    source_url: str
    source_domain: str
    source_quality_class: str
    observed_at: str
    ticker_candidates: tuple[str, ...] = ()
    product_candidates: tuple[str, ...] = ()
    counterparty_candidates: tuple[str, ...] = ()
    extracted_hint: str = ""
    suggested_repair_routes: tuple[str, ...] = ()
    required_verification_source_layers: tuple[str, ...] = ("L1", "L2", "L3")
    expiry_at: str = ""
    disallowed_claim_scopes: tuple[str, ...] = L4_FORBIDDEN_CLAIM_SCOPES
    promotion_status: str = "lead_only"
    source_layer_id: str = "L4"
    exact_value_authority: bool = False
    can_support_company_exact_fact: bool = False
    schema_version: str = WEAK_SIGNAL_LEAD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_payload(self)


@dataclass(frozen=True)
class WeakSignalExclusionNote:
    note_id: str
    lead_id: str
    exclusion_reason: str
    checked_routes: tuple[str, ...]
    why_not_promoted: str
    next_possible_source: str = ""
    created_at: str = ""
    schema_version: str = WEAK_SIGNAL_EXCLUSION_NOTE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_payload(self)


@dataclass(frozen=True)
class L4PromotionAttempt:
    attempt_id: str
    lead_id: str
    target_layer: str
    target_source_class: str
    fetch_result: str
    parser_result: str
    entity_binding_result: str
    promotion_status: str
    promoted_evidence_ref: str = ""
    promotion_reason: str = ""
    original_l4_source_id: str = ""
    created_at: str = ""
    schema_version: str = L4_PROMOTION_ATTEMPT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_payload(self)


def classify_l4_source(
    *,
    source_id: str = "",
    source_url: str = "",
    source_class: str = "",
    verified_account: bool | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify low-authority public inputs before they can enter repair planning.

    The classifier is intentionally conservative: unverified social/forum/search/chart
    inputs can only become L4 weak-signal leads, while verified official accounts are
    routed to L2 and commercial tracker/consensus sources are registered as gaps.
    """
    meta = dict(metadata or {})
    sid = _normalize_id(source_id or meta.get("source_id") or meta.get("underlying_source_id"))
    sclass = _normalize_id(source_class or meta.get("source_class"))
    domain = _domain(source_url or str(meta.get("source_url") or ""))
    verified = bool(
        verified_account
        if verified_account is not None
        else meta.get("verified_account") or meta.get("official_account_verified") or meta.get("is_official_account")
    )

    if sid in COMMERCIAL_GAP_SOURCE_IDS or sclass in COMMERCIAL_GAP_SOURCE_IDS:
        return _classification(
            source_id=sid,
            source_url=source_url,
            source_domain=domain,
            source_layer_id="commercial_gap",
            source_quality_class="commercial_tracker_gap",
            route="commercial_gap_ledger",
            is_l4=False,
            reason="commercial_market_or_consensus_source_cannot_be_replaced_by_l4_proxy",
        )

    if verified or sid == "official_social_accounts" or sclass in OFFICIAL_ACCOUNT_CLASSES:
        return _classification(
            source_id=sid or "official_social_accounts",
            source_url=source_url,
            source_domain=domain,
            source_layer_id="L2",
            source_quality_class="verified_official_context",
            route="l2_official_social_or_issuer_context",
            is_l4=False,
            reason="verified_official_account_is_l2_context_not_l4",
        )

    if sid in L4_SOURCE_IDS or sclass in L4_SOURCE_IDS or domain in UNVERIFIED_SOCIAL_DOMAINS:
        quality = "market_chart_lead" if sid == "yahoo_chart" or "finance.yahoo" in domain else (
            "web_scale_discovery" if sid == "common_crawl_index" else "unverified_social_or_forum"
        )
        if sid in {"search_snippet", "generic_search_snippet"}:
            quality = "search_snippet_discovery"
        return _classification(
            source_id=sid or sclass or "unverified_public_web",
            source_url=source_url,
            source_domain=domain,
            source_layer_id="L4",
            source_quality_class=quality,
            route="l4_weak_signal_lead",
            is_l4=True,
            reason="unverified_or_discovery_source_requires_l1_l2_l3_repair_before_use",
        )

    if sid in L3_SOURCE_IDS:
        return _classification(
            source_id=sid,
            source_url=source_url,
            source_domain=domain,
            source_layer_id="L3",
            source_quality_class="public_proxy_context",
            route="l3_proxy_context",
            is_l4=False,
            reason="source_is_registered_l3_proxy_not_l4",
        )

    if sid in L2_SOURCE_IDS:
        return _classification(
            source_id=sid,
            source_url=source_url,
            source_domain=domain,
            source_layer_id="L2",
            source_quality_class="trusted_or_official_context",
            route="l2_trusted_context",
            is_l4=False,
            reason="source_is_registered_l2_context_not_l4",
        )

    return _classification(
        source_id=sid or sclass or "unknown_public_source",
        source_url=source_url,
        source_domain=domain,
        source_layer_id="L4",
        source_quality_class="unclassified_public_discovery",
        route="l4_weak_signal_lead",
        is_l4=True,
        reason="unknown_public_source_defaults_to_l4_until_source_policy_passes",
    )


def make_weak_signal_lead(
    *,
    source_id: str,
    source_url: str = "",
    source_class: str = "",
    observed_at: str | None = None,
    ticker_candidates: Sequence[Any] | None = None,
    product_candidates: Sequence[Any] | None = None,
    counterparty_candidates: Sequence[Any] | None = None,
    extracted_hint: str = "",
    suggested_repair_routes: Sequence[Any] | None = None,
    ttl_days: int = 30,
    metadata: Mapping[str, Any] | None = None,
) -> WeakSignalLead:
    classification = classify_l4_source(
        source_id=source_id,
        source_url=source_url,
        source_class=source_class,
        metadata=metadata,
    )
    if classification["source_layer_id"] == "commercial_gap":
        raise ValueError("commercial_gap_source_cannot_be_materialized_as_l4_weak_signal")
    if classification["source_layer_id"] != "L4":
        raise ValueError("only_l4_sources_can_create_weak_signal_leads")
    observed = _iso_utc(observed_at)
    expiry = _iso_utc(_parse_time(observed) + timedelta(days=max(1, int(ttl_days or 30))))
    tickers = tuple(_unique_upper(ticker_candidates or ()))
    products = tuple(_unique_strings(product_candidates or ()))
    counterparties = tuple(_unique_upper(counterparty_candidates or ()))
    routes = tuple(_unique_strings(suggested_repair_routes or _infer_repair_routes(extracted_hint, products=products)))
    lead_id = _stable_id(
        "weak_signal_lead",
        [
            classification["source_id"],
            classification["source_domain"],
            source_url,
            ",".join(tickers),
            ",".join(products),
            ",".join(counterparties),
            _compact_text(extracted_hint)[:240],
        ],
    )
    return WeakSignalLead(
        lead_id=lead_id,
        source_id=str(classification["source_id"] or source_id),
        source_url=source_url,
        source_domain=str(classification["source_domain"] or _domain(source_url)),
        source_quality_class=str(classification["source_quality_class"] or "unverified_public_discovery"),
        observed_at=observed,
        ticker_candidates=tickers,
        product_candidates=products,
        counterparty_candidates=counterparties,
        extracted_hint=str(extracted_hint or "").strip(),
        suggested_repair_routes=routes,
        expiry_at=expiry,
    )


def make_weak_signal_exclusion_note(
    *,
    lead: WeakSignalLead | Mapping[str, Any],
    exclusion_reason: str,
    checked_routes: Sequence[Any] | None = None,
    why_not_promoted: str = "",
    next_possible_source: str = "",
    created_at: str | None = None,
) -> WeakSignalExclusionNote:
    item = _coerce_lead(lead)
    created = _iso_utc(created_at)
    routes = tuple(_unique_strings(checked_routes or item.suggested_repair_routes))
    note_id = _stable_id("weak_signal_exclusion_note", [item.lead_id, exclusion_reason, ",".join(routes)])
    return WeakSignalExclusionNote(
        note_id=note_id,
        lead_id=item.lead_id,
        exclusion_reason=str(exclusion_reason or "").strip(),
        checked_routes=routes,
        why_not_promoted=str(why_not_promoted or exclusion_reason or "").strip(),
        next_possible_source=str(next_possible_source or "").strip(),
        created_at=created,
    )


def dedupe_weak_signal_leads(leads: Iterable[WeakSignalLead | Mapping[str, Any]]) -> list[WeakSignalLead]:
    """Deduplicate weak leads by canonical source/entity/hint key and keep newest."""
    by_key: dict[str, WeakSignalLead] = {}
    for value in leads:
        lead = _coerce_lead(value)
        key = _dedupe_key(lead)
        current = by_key.get(key)
        if current is None or _parse_time(lead.observed_at) >= _parse_time(current.observed_at):
            by_key[key] = lead
    return sorted(by_key.values(), key=lambda item: item.lead_id)


def is_weak_signal_expired(lead: WeakSignalLead | Mapping[str, Any], *, now: str | datetime | None = None) -> bool:
    item = _coerce_lead(lead)
    return _parse_time(item.expiry_at) <= _parse_time(now)


def weak_signal_to_targeted_repair_plan(lead: WeakSignalLead | Mapping[str, Any]) -> dict[str, Any]:
    item = _coerce_lead(lead)
    routes = item.suggested_repair_routes or tuple(_infer_repair_routes(item.extracted_hint, products=item.product_candidates))
    target_layers = sorted({_target_layer_for_route(route) for route in routes})
    return {
        "schema_version": "finsight_l4_targeted_repair_plan_v0_1",
        "lead_id": item.lead_id,
        "source_layer_id": "L4",
        "source_lead_only": True,
        "target_layers": target_layers,
        "repair_routes": list(routes),
        "ticker_candidates": list(item.ticker_candidates),
        "product_candidates": list(item.product_candidates),
        "counterparty_candidates": list(item.counterparty_candidates),
        "expected_claim_boundary": (
            "L4 lead may trigger L1/L2/L3 repair only; original L4 source cannot support ClaimCards, "
            "exact facts, product success, sales, share, orders, or core thesis evidence."
        ),
        "promotion_requirements": [
            "target row source_layer_id must be L1/L2/L3",
            "target row must be parser-backed structured context or exact authority row",
            "target row must bind to issuer/product/counterparty when the lead names one",
            "L2/L3 rows cannot be exact_value_authority or company exact facts",
        ],
    }


def evaluate_l4_promotion_attempt(
    lead: WeakSignalLead | Mapping[str, Any],
    *,
    promoted_row: Mapping[str, Any] | None = None,
    target_layer: str | None = None,
    target_source_class: str = "",
    fetch_result: str = "not_run",
    created_at: str | None = None,
) -> L4PromotionAttempt:
    item = _coerce_lead(lead)
    row = dict(promoted_row or {})
    target = str(target_layer or row.get("source_layer_id") or row.get("layer_id") or "L2").strip()
    source_class = str(target_source_class or row.get("source_class") or row.get("source_id") or "").strip()
    created = _iso_utc(created_at)

    if not row:
        return _promotion_attempt(
            item,
            target_layer=target,
            target_source_class=source_class,
            fetch_result=fetch_result if fetch_result != "not_run" else "not_found",
            parser_result="not_run",
            entity_binding_result="not_run",
            promotion_status="not_found",
            promotion_reason="repair_route_returned_no_candidate_row",
            created_at=created,
        )

    row_layer = str(row.get("source_layer_id") or row.get("source_layer") or row.get("layer_id") or target).strip()
    parser_result = "parser_backed" if _row_parser_backed(row) else "parser_failed"
    entity_result = "entity_bound" if _row_entity_bound_to_lead(row, item) else "entity_unresolved"
    promoted_ref = str(row.get("evidence_ref") or row.get("evidence_id") or row.get("snapshot_id") or "")

    if row_layer == "L4":
        return _promotion_attempt(
            item,
            target_layer=row_layer,
            target_source_class=source_class,
            fetch_result=fetch_result,
            parser_result=parser_result,
            entity_binding_result=entity_result,
            promotion_status="blocked",
            promoted_evidence_ref=promoted_ref,
            promotion_reason="l4_direct_promotion_forbidden",
            created_at=created,
        )
    if row_layer not in {"L1", "L2", "L3"}:
        return _promotion_attempt(
            item,
            target_layer=row_layer,
            target_source_class=source_class,
            fetch_result=fetch_result,
            parser_result=parser_result,
            entity_binding_result=entity_result,
            promotion_status="blocked",
            promoted_evidence_ref=promoted_ref,
            promotion_reason="target_layer_must_be_l1_l2_or_l3",
            created_at=created,
        )
    if row_layer in {"L2", "L3"} and (bool(row.get("exact_value_authority")) or bool(row.get("can_support_company_exact_fact"))):
        return _promotion_attempt(
            item,
            target_layer=row_layer,
            target_source_class=source_class,
            fetch_result=fetch_result,
            parser_result=parser_result,
            entity_binding_result=entity_result,
            promotion_status="blocked",
            promoted_evidence_ref=promoted_ref,
            promotion_reason="l2_l3_exact_authority_promotion_forbidden",
            created_at=created,
        )
    if parser_result != "parser_backed":
        return _promotion_attempt(
            item,
            target_layer=row_layer,
            target_source_class=source_class,
            fetch_result=fetch_result,
            parser_result=parser_result,
            entity_binding_result=entity_result,
            promotion_status="parser_failed",
            promoted_evidence_ref=promoted_ref,
            promotion_reason="target_row_missing_parser_backed_context",
            created_at=created,
        )
    if entity_result != "entity_bound":
        return _promotion_attempt(
            item,
            target_layer=row_layer,
            target_source_class=source_class,
            fetch_result=fetch_result,
            parser_result=parser_result,
            entity_binding_result=entity_result,
            promotion_status="entity_unresolved",
            promoted_evidence_ref=promoted_ref,
            promotion_reason="target_row_not_bound_to_l4_lead_entities",
            created_at=created,
        )

    return _promotion_attempt(
        item,
        target_layer=row_layer,
        target_source_class=source_class,
        fetch_result=fetch_result,
        parser_result=parser_result,
        entity_binding_result=entity_result,
        promotion_status="promoted",
        promoted_evidence_ref=promoted_ref,
        promotion_reason="parser_backed_l1_l2_l3_row_passed_l4_promotion_gate",
        created_at=created,
    )


def validate_l4_not_promoted_to_claim_cards(
    claim_cards: Iterable[Mapping[str, Any]],
    *,
    l4_lead_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    known_leads = {str(item).strip() for item in (l4_lead_ids or []) if str(item).strip()}
    cards = [item for item in claim_cards if isinstance(item, Mapping)]
    errors: list[dict[str, Any]] = []
    for index, claim in enumerate(cards):
        refs = _extract_nested_rows(claim)
        source_layer_values = _field_values(claim, ("source_layer_id", "source_layer", "layer_id", "source_layers", "evidence_source_layers"))
        source_id_values = _field_values(claim, ("source_id", "source_ids", "underlying_source_id"))
        weak_lead_values = _field_values(claim, ("weak_signal_lead_id", "weak_signal_lead_ids", "lead_id"))
        for row in refs:
            source_layer_values.extend(_field_values(row, ("source_layer_id", "source_layer", "layer_id", "source_layers")))
            source_id_values.extend(_field_values(row, ("source_id", "source_ids", "underlying_source_id")))
            weak_lead_values.extend(_field_values(row, ("weak_signal_lead_id", "lead_id")))

        has_l4_layer = any(str(value).upper() == "L4" for value in source_layer_values)
        has_l4_source = any(_normalize_id(value) in L4_SOURCE_IDS for value in source_id_values)
        has_weak_lead = any(str(value).strip() in known_leads or str(value).strip().startswith("weak_signal_lead_") for value in weak_lead_values)
        if has_l4_layer or has_l4_source or has_weak_lead:
            errors.append(
                {
                    "type": "l4_claim_card_forbidden",
                    "index": index,
                    "claim_id": str(claim.get("claim_id") or claim.get("id") or ""),
                    "reason": "L4 weak signals cannot be ClaimCards or core thesis evidence.",
                }
            )
        if (has_l4_layer or has_l4_source or has_weak_lead) and (
            bool(claim.get("exact_value_authority")) or bool(claim.get("can_support_company_exact_fact"))
        ):
            errors.append(
                {
                    "type": "l4_exact_authority_forbidden",
                    "index": index,
                    "claim_id": str(claim.get("claim_id") or claim.get("id") or ""),
                }
            )
    return {
        "schema_version": "finsight_l4_claimcard_promotion_validation_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "checked_claim_card_count": len(cards),
    }


def validate_memo_l4_usage(memo: Mapping[str, Any]) -> dict[str, Any]:
    """Validate that user-facing memo output does not cite L4 as core evidence."""
    errors: list[dict[str, Any]] = []
    claims = []
    for key in ("memo_claims", "claims", "supported_claims", "dimension_analyses"):
        value = memo.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            claims.extend(item for item in value if isinstance(item, Mapping))
    claim_validation = validate_l4_not_promoted_to_claim_cards(claims)
    if claim_validation["status"] != "pass":
        errors.extend({"type": "memo_contains_l4_claim_card", **error} for error in claim_validation["errors"])
    raw_text = " ".join(str(memo.get(key) or "") for key in ("direct_answer", "summary", "core_judgment", "investment_implications"))
    if "weak_signal_lead_" in raw_text and not any(scope in raw_text for scope in L4_ALLOWED_MEMO_SCOPES):
        errors.append({"type": "memo_exposes_l4_lead_as_core_text", "reason": "L4 lead ids should stay in audit metadata or exclusion notes."})
    return {
        "schema_version": "finsight_l4_memo_usage_validation_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
    }


def write_l4_runtime_objects(
    *,
    leads: Iterable[WeakSignalLead | Mapping[str, Any]] = (),
    exclusion_notes: Iterable[WeakSignalExclusionNote | Mapping[str, Any]] = (),
    promotion_attempts: Iterable[L4PromotionAttempt | Mapping[str, Any]] = (),
    output_path: str | Path,
) -> dict[str, Any]:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    rows.extend({"object_type": "WeakSignalLead", **_object_payload(item)} for item in leads)
    rows.extend({"object_type": "WeakSignalExclusionNote", **_object_payload(item)} for item in exclusion_notes)
    rows.extend({"object_type": "L4PromotionAttempt", **_object_payload(item)} for item in promotion_attempts)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return {
        "schema_version": L4_RUNTIME_STORE_SCHEMA_VERSION,
        "path": str(path),
        "row_count": len(rows),
        "weak_signal_lead_count": sum(1 for row in rows if row.get("object_type") == "WeakSignalLead"),
        "exclusion_note_count": sum(1 for row in rows if row.get("object_type") == "WeakSignalExclusionNote"),
        "promotion_attempt_count": sum(1 for row in rows if row.get("object_type") == "L4PromotionAttempt"),
    }


def load_l4_runtime_objects(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    p = Path(path)
    rows: list[dict[str, Any]] = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return {
        "weak_signal_leads": [row for row in rows if row.get("object_type") == "WeakSignalLead"],
        "exclusion_notes": [row for row in rows if row.get("object_type") == "WeakSignalExclusionNote"],
        "promotion_attempts": [row for row in rows if row.get("object_type") == "L4PromotionAttempt"],
    }


def _classification(
    *,
    source_id: str,
    source_url: str,
    source_domain: str,
    source_layer_id: str,
    source_quality_class: str,
    route: str,
    is_l4: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": L4_SOURCE_CLASSIFIER_SCHEMA_VERSION,
        "source_id": source_id,
        "source_url": source_url,
        "source_domain": source_domain,
        "source_layer_id": source_layer_id,
        "source_quality_class": source_quality_class,
        "route": route,
        "is_l4": is_l4,
        "weak_signal_allowed": is_l4,
        "claim_card_allowed": not is_l4 and source_layer_id in {"L1", "L2", "L3"},
        "reason": reason,
    }


def _promotion_attempt(
    lead: WeakSignalLead,
    *,
    target_layer: str,
    target_source_class: str,
    fetch_result: str,
    parser_result: str,
    entity_binding_result: str,
    promotion_status: str,
    promoted_evidence_ref: str = "",
    promotion_reason: str = "",
    created_at: str,
) -> L4PromotionAttempt:
    attempt_id = _stable_id(
        "l4_promotion_attempt",
        [lead.lead_id, target_layer, target_source_class, promoted_evidence_ref, promotion_status, promotion_reason],
    )
    return L4PromotionAttempt(
        attempt_id=attempt_id,
        lead_id=lead.lead_id,
        target_layer=target_layer,
        target_source_class=target_source_class,
        fetch_result=fetch_result,
        parser_result=parser_result,
        entity_binding_result=entity_binding_result,
        promotion_status=promotion_status,
        promoted_evidence_ref=promoted_evidence_ref,
        promotion_reason=promotion_reason,
        original_l4_source_id=lead.source_id,
        created_at=created_at,
    )


def _coerce_lead(value: WeakSignalLead | Mapping[str, Any]) -> WeakSignalLead:
    if isinstance(value, WeakSignalLead):
        return value
    raw = dict(value)
    return WeakSignalLead(
        lead_id=str(raw.get("lead_id") or ""),
        source_id=str(raw.get("source_id") or ""),
        source_url=str(raw.get("source_url") or ""),
        source_domain=str(raw.get("source_domain") or _domain(str(raw.get("source_url") or ""))),
        source_quality_class=str(raw.get("source_quality_class") or "unclassified_public_discovery"),
        observed_at=_iso_utc(raw.get("observed_at")),
        ticker_candidates=tuple(_unique_upper(raw.get("ticker_candidates") or ())),
        product_candidates=tuple(_unique_strings(raw.get("product_candidates") or ())),
        counterparty_candidates=tuple(_unique_upper(raw.get("counterparty_candidates") or ())),
        extracted_hint=str(raw.get("extracted_hint") or ""),
        suggested_repair_routes=tuple(_unique_strings(raw.get("suggested_repair_routes") or ())),
        required_verification_source_layers=tuple(_unique_strings(raw.get("required_verification_source_layers") or ("L1", "L2", "L3"))),
        expiry_at=_iso_utc(raw.get("expiry_at") or (_parse_time(raw.get("observed_at")) + timedelta(days=30))),
        disallowed_claim_scopes=tuple(_unique_strings(raw.get("disallowed_claim_scopes") or L4_FORBIDDEN_CLAIM_SCOPES)),
        promotion_status=str(raw.get("promotion_status") or "lead_only"),
        source_layer_id=str(raw.get("source_layer_id") or "L4"),
        exact_value_authority=bool(raw.get("exact_value_authority")),
        can_support_company_exact_fact=bool(raw.get("can_support_company_exact_fact")),
        schema_version=str(raw.get("schema_version") or WEAK_SIGNAL_LEAD_SCHEMA_VERSION),
    )


def _row_parser_backed(row: Mapping[str, Any]) -> bool:
    if row.get("bounded_structured_context") or row.get("source_specific_parser") or row.get("structured_context_type"):
        return True
    status = str(row.get("structured_fact_status") or row.get("parser_status") or row.get("runtime_promotion_status") or "")
    return status in {"bounded_context_fact_materialized", "context_rows_ready", "candidate_rows_ready", "exact_ledger_ready", "runtime_fact_allowed", "parser_gate_passed"}


def _row_entity_bound_to_lead(row: Mapping[str, Any], lead: WeakSignalLead) -> bool:
    lead_tickers = set(lead.ticker_candidates)
    lead_products = {_compact_text(item).lower() for item in lead.product_candidates}
    lead_counterparties = set(lead.counterparty_candidates)
    row_tickers = set(_unique_upper([row.get("ticker"), row.get("issuer_ticker"), row.get("company_ticker"), row.get("ticker_scope")]))
    row_counterparties = set(_unique_upper([row.get("counterparty"), row.get("counterparty_ticker"), row.get("buyer_ticker"), row.get("supplier_ticker")]))
    row_product_text = _compact_text(
        " ".join(
            str(row.get(key) or "")
            for key in ("product", "product_name", "product_or_segment", "product_family", "product_model_id", "metric_name")
        )
    ).lower()

    issuer_bound = bool(lead_tickers and not lead_tickers.isdisjoint(row_tickers)) or _binding_status_strong(row, "issuer_binding_status")
    product_bound = bool(lead_products and any(product and product in row_product_text for product in lead_products)) or _binding_status_strong(row, "product_binding_status")
    counterparty_bound = bool(lead_counterparties and not lead_counterparties.isdisjoint(row_counterparties)) or _binding_status_strong(row, "counterparty_binding_status")

    required_checks = []
    if lead_tickers:
        required_checks.append(issuer_bound)
    if lead.product_candidates:
        required_checks.append(product_bound)
    if lead.counterparty_candidates:
        required_checks.append(counterparty_bound)
    return all(required_checks) if required_checks else (
        issuer_bound or product_bound or counterparty_bound or bool(row_tickers) or bool(row_product_text)
    )


def _binding_status_strong(row: Mapping[str, Any], key: str) -> bool:
    return str(row.get(key) or "") in STRONG_BINDING_STATUSES


def _infer_repair_routes(text: str, *, products: Sequence[str] = ()) -> list[str]:
    haystack = " ".join([str(text or ""), " ".join(products)]).lower()
    routes: list[str] = []
    if any(term in haystack for term in ("10-k", "10-q", "20-f", "6-k", "annual report", "filing", "prospectus")):
        routes.extend(["company_disclosure", "sec_fpi_or_local_exchange_filing"])
    if any(term in haystack for term in ("product", "sku", "spec", "datasheet", "launch", "model", "server", "gpu", "accelerator")):
        routes.append("official_product_surface")
    if any(term in haystack for term in ("customer", "supplier", "partner", "contract", "order", "award", "tender")):
        routes.extend(["supplier_customer_official_news", "public_contract_award_context"])
    if any(term in haystack for term in ("price", "availability", "reseller", "channel", "amazon", "jd", "cdw")):
        routes.append("channel_offer_proxy")
    if any(term in haystack for term in ("github", "npm", "pypi", "huggingface", "cuda", "rocm", "developer")):
        routes.append("developer_ecosystem_proxy")
    if any(term in haystack for term in ("trial", "fda", "clinical", "drug", "label", "approval")):
        routes.append("regulated_product_context")
    if any(term in haystack for term in ("recall", "nhtsa", "vin", "vehicle")):
        routes.append("auto_product_identity_context")
    if any(term in haystack for term in ("eia", "fred", "fdic", "macro", "deposit", "energy", "rate")):
        routes.append("public_official_api_context")
    if any(term in haystack for term in ("news", "reported", "press")):
        routes.append("trusted_news_context")
    return _unique_strings(routes or ["company_ir_or_official_source", "trusted_news_context"])


def _target_layer_for_route(route: str) -> str:
    text = str(route or "").lower()
    if any(term in text for term in ("disclosure", "filing", "sec_", "company_reported")):
        return "L1"
    if any(term in text for term in ("official", "regulatory", "trusted_news", "clinical", "fda", "nhtsa", "eia", "fred", "fdic", "openalex", "patents")):
        return "L2"
    return "L3"


def _dedupe_key(lead: WeakSignalLead) -> str:
    canonical_url = _canonical_url(lead.source_url)
    seed = "|".join(
        [
            lead.source_id,
            canonical_url or lead.source_domain,
            ",".join(sorted(lead.ticker_candidates)),
            ",".join(sorted(lead.product_candidates)),
            ",".join(sorted(lead.counterparty_candidates)),
            _compact_text(lead.extracted_hint).lower()[:160],
        ]
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _extract_nested_rows(claim: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for key in ("evidence_rows", "evidence", "citations", "source_rows", "supporting_rows"):
        value = claim.get(key)
        if isinstance(value, Mapping):
            rows.append(value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            rows.extend(item for item in value if isinstance(item, Mapping))
    return rows


def _field_values(row: Mapping[str, Any], keys: Sequence[str]) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            values.extend(part.strip() for part in re.split(r"[,;|]", value) if part.strip())
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            values.extend(str(part).strip() for part in value if str(part).strip())
        else:
            values.append(str(value).strip())
    return values


def _object_payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(value)


def _dataclass_payload(value: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field_name in value.__dataclass_fields__:
        item = getattr(value, field_name)
        payload[field_name] = list(item) if isinstance(item, tuple) else item
    return payload


def _stable_id(prefix: str, parts: Sequence[Any]) -> str:
    seed = "|".join(str(part or "").strip() for part in parts)
    return f"{prefix}_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _domain(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    return (parsed.netloc or parsed.path.split("/")[0]).lower().strip()


def _canonical_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    return f"{(parsed.netloc or '').lower()}{parsed.path.rstrip('/').lower()}"


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_id(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            for item in _unique_strings(value):
                if item not in seen:
                    seen.add(item)
                    output.append(item)
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _unique_upper(values: Iterable[Any]) -> list[str]:
    return [item.upper() for item in _unique_strings(values)]


def _iso_utc(value: str | datetime | None) -> str:
    dt = _parse_time(value)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc).replace(microsecond=0)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc).replace(microsecond=0)
