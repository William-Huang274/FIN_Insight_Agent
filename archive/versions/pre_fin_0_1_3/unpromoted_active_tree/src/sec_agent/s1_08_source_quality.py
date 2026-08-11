from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_QUERY_PREFIXES = ("utm_", "icid", "ocid", "ef_id")
_NAVIGATION_OR_COMMERCE_PATHS = (
    "/store/",
    "/surface/",
    "/microsoft-365/outlook/",
    "/microsoft-products-and-apps",
    "/diversity/",
    "/corporate-governance/",
    "/dividends-and-stock-history",
    "/investment-history",
    "/privacy/",
    "/legal/",
    "/careers/",
)
_ROLE_TERMS: Mapping[str, tuple[str, ...]] = {
    "issuer_results_and_management_commentary": (
        "earnings",
        "results",
        "financial",
        "revenue",
        "prepared remarks",
        "10-q",
        "10-k",
        "8-k",
        "20-f",
        "6-k",
    ),
    "regulatory_risk_and_financial_reconciliation": (
        "10-q",
        "10-k",
        "8-k",
        "20-f",
        "6-k",
        "risk factors",
        "cash flow",
        "segment",
        "filing",
    ),
    "customer_demand_and_deployment_validation": (
        "customer",
        "deployment",
        "capacity",
        "capital expenditure",
        "capex",
        "earnings",
        "metrics",
        "ai infrastructure",
        "data center",
    ),
    "supply_chain_capacity_and_counterevidence": (
        "capacity",
        "supply",
        "constraint",
        "packaging",
        "memory",
        "foundry",
        "inventory",
        "earnings",
        "results",
    ),
    "market_expectation_context": (
        "market",
        "valuation",
        "price",
        "return",
        "expectation",
    ),
}


@dataclass(frozen=True)
class LocatorQualityDecision:
    decision: str
    reason_codes: tuple[str, ...]
    quality_score: int
    canonical_locator: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_codes": list(self.reason_codes),
            "quality_score": self.quality_score,
            "canonical_locator": self.canonical_locator,
        }


def canonical_locator_key(value: str) -> str:
    split = urlsplit(str(value or "").strip())
    host = split.netloc.lower()
    path = re.sub(r"/{2,}", "/", split.path or "/")
    if host in {"www.microsoft.com", "microsoft.com"}:
        path = path.lower()
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(split.query, keep_blank_values=True)
            if not key.lower().startswith(_TRACKING_QUERY_PREFIXES)
        )
    )
    return urlunsplit((split.scheme.lower(), host, path.rstrip("/") or "/", query, ""))


def infer_source_family(url: str, *, form_type: str = "") -> str:
    split = urlsplit(url)
    host = split.netloc.lower()
    path = split.path.lower()
    if host in {"www.sec.gov", "sec.gov", "data.sec.gov"}:
        return "regulatory_filing" if form_type or "/archives/" in path else "regulatory_index"
    if "/customers/" in path or "/customer" in path:
        return "customer_official_disclosure"
    if any(token in path for token in ("/earnings/", "/results", "/news/", "/events/")):
        return "issuer_ir_document"
    if path.endswith(("sitemap.xml", ".rss", ".xml")) or "rss" in path:
        return "issuer_structured_discovery"
    return "issuer_official_page"


def qualify_locator(
    *,
    role_id: str,
    allowed_source_families: Sequence[str],
    url: str,
    title: str,
    published_on: str,
    as_of: str,
    currentness_window_days: int,
    form_type: str = "",
) -> LocatorQualityDecision:
    canonical = canonical_locator_key(url)
    split = urlsplit(canonical)
    haystack = f"{title} {split.path} {form_type}".lower()
    reasons: list[str] = []
    source_family = infer_source_family(url, form_type=form_type)
    if split.scheme != "https" or not split.netloc:
        reasons.append("locator_not_https")
    if any(fragment in split.path.lower() for fragment in _NAVIGATION_OR_COMMERCE_PATHS):
        reasons.append("navigation_or_commerce_surface")
    if source_family not in set(allowed_source_families):
        reasons.append("source_family_not_allowed_for_evidence_slot")
    role_terms = _ROLE_TERMS.get(role_id, ())
    matched_terms = sum(term in haystack for term in role_terms)
    if source_family == "regulatory_filing" and form_type in {
        "10-K",
        "10-Q",
        "8-K",
        "20-F",
        "6-K",
    }:
        matched_terms += 2
    if matched_terms == 0:
        reasons.append("evidence_slot_fit_unproven")
    parsed_date: date | None = None
    if published_on:
        try:
            parsed_date = date.fromisoformat(published_on)
        except ValueError:
            reasons.append("locator_publication_date_invalid")
    try:
        boundary = date.fromisoformat(as_of)
    except ValueError:
        reasons.append("as_of_invalid")
        boundary = date.max
    if parsed_date is not None:
        if parsed_date > boundary:
            reasons.append("locator_after_as_of")
        elif parsed_date < boundary - timedelta(days=currentness_window_days):
            reasons.append("stale_for_current_evidence_slot")
    score = matched_terms * 10
    if source_family == "regulatory_filing":
        score += 8
    elif source_family in {"issuer_ir_document", "customer_official_disclosure"}:
        score += 6
    if parsed_date is not None and parsed_date <= boundary:
        score += max(0, currentness_window_days - (boundary - parsed_date).days) // 30
    return LocatorQualityDecision(
        decision="fetch" if not reasons else "reject_before_fetch",
        reason_codes=tuple(sorted(set(reasons))),
        quality_score=score,
        canonical_locator=canonical,
    )


def qualify_parsed_content(
    *,
    role_id: str,
    title: str,
    text: str,
    entity_aliases: Sequence[str],
) -> tuple[str, ...]:
    normalized = " ".join(str(text or "").split()).lower()
    reasons: list[str] = []
    if len(normalized) < 80:
        reasons.append("parsed_content_too_thin")
    role_terms = _ROLE_TERMS.get(role_id, ())
    if role_terms and not any(term in normalized for term in role_terms):
        reasons.append("parsed_content_evidence_role_unproven")
    if entity_aliases and not any(str(alias).lower() in normalized for alias in entity_aliases):
        # Ecosystem evidence may legitimately describe another official entity.  This is
        # a quality finding rather than an automatic rejection when the role is relational.
        if role_id in {
            "issuer_results_and_management_commentary",
            "regulatory_risk_and_financial_reconciliation",
        }:
            reasons.append("parsed_content_subject_identity_unproven")
    if any(fragment in f"{title} {normalized[:400]}" for fragment in ("shop now", "add to cart")):
        reasons.append("parsed_content_commerce_surface")
    return tuple(sorted(set(reasons)))


def qualify_relationship_direction(
    *,
    role_id: str,
    url: str,
    subject_entity: str,
    evidence_owner_entity: str,
    evidence_owner_roles: Sequence[str],
    claim_direction: str,
    allowed_source_owner_roles: Sequence[str],
    forbidden_nested_relationships: Sequence[str],
) -> tuple[str, ...]:
    """Rejects locator semantics that point at the wrong economic edge.

    This is deliberately evaluated before document fetch.  A page on an official
    domain can still discuss that company's customer, supplier or partner rather
    than the evidence owner's own demand/capacity.  Source authority therefore
    does not establish relationship direction by itself.
    """

    reasons: list[str] = []
    path = urlsplit(url).path.lower()
    owner_roles = {str(value) for value in evidence_owner_roles}
    allowed_roles = {str(value) for value in allowed_source_owner_roles}
    forbidden = {str(value) for value in forbidden_nested_relationships}
    if not subject_entity or not evidence_owner_entity or not claim_direction:
        reasons.append("relationship_identity_or_direction_missing")
    if allowed_roles and not owner_roles.intersection(allowed_roles):
        reasons.append("evidence_owner_role_not_allowed_for_slot")
    if role_id in {
        "issuer_results_and_management_commentary",
        "regulatory_risk_and_financial_reconciliation",
    } and evidence_owner_entity != subject_entity:
        reasons.append("subject_self_disclosure_owner_mismatch")
    nested_customer_path = any(
        token in path
        for token in (
            "/customers/",
            "/customer-story/",
            "/customer-stories/",
            "/case-studies/",
        )
    )
    if nested_customer_path and "evidence_owner_customer" in forbidden:
        reasons.append("nested_customer_relationship_direction_invalid")
    if (
        claim_direction == "evidence_owner_own_infrastructure_demand"
        and nested_customer_path
    ):
        reasons.append("evidence_owner_own_demand_not_proven_by_customer_story")
    if (
        claim_direction == "evidence_owner_own_supply_capacity_or_constraint"
        and nested_customer_path
    ):
        reasons.append("evidence_owner_own_supply_not_proven_by_customer_story")
    return tuple(sorted(set(reasons)))


__all__ = [
    "LocatorQualityDecision",
    "canonical_locator_key",
    "infer_source_family",
    "qualify_locator",
    "qualify_parsed_content",
    "qualify_relationship_direction",
]
