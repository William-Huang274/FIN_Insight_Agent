from __future__ import annotations

import re
from typing import Any, Mapping

from sec_agent.entities.entity_resolution import resolve_entity_name

from .edge_schema import normalize_relationship_edge


SEC_RELATIONSHIP_KEYWORDS = (
    "accounted for",
    "represented",
    "comprised",
    "customer",
    "customers",
    "supplier",
    "suppliers",
    "single source",
    "sole source",
    "agreement",
    "contract",
    "partner",
    "partnership",
    "distributor",
    "reseller",
    "concentration",
    "revenue concentration",
)

CUSTOMER_CONCENTRATION_PATTERNS = [
    re.compile(
        r"(?P<target>[A-Z][A-Za-z0-9&.,'() /-]{2,90}?)\s+(?:accounted for|represented|comprised)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)\s*%\s+of\s+(?:our|the company's|company|net)?\s*"
        r"(?P<metric>revenue|revenues|sales|net sales)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:sales|revenue|revenues)\s+to\s+(?P<target>[A-Z][A-Za-z0-9&.,'() /-]{2,90}?)\s+"
        r"(?:accounted for|represented|comprised)\s+(?P<pct>\d+(?:\.\d+)?)\s*%",
        flags=re.IGNORECASE,
    ),
]
SUPPLIER_PATTERNS = [
    re.compile(
        r"(?:single|sole|primary|significant)\s+(?:source\s+)?supplier(?:s)?\s+(?:is|was|are|were|include|includes|from)?\s*"
        r"(?P<target>[A-Z][A-Za-z0-9&.,'() /-]{2,90})",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:depend|depends|dependent|rely|relies|reliant)\s+on\s+(?P<target>[A-Z][A-Za-z0-9&.,'() /-]{2,90})\s+"
        r"(?:as|for|to)?\s*(?:a\s+)?(?:supplier|vendor|manufacturer)",
        flags=re.IGNORECASE,
    ),
]
AGREEMENT_PATTERNS = [
    re.compile(
        r"(?:entered into|signed|announced|renewed|amended|maintains?)\s+(?:a|an|the)?\s*"
        r"(?P<kind>supply|customer|purchase|distribution|reseller|strategic partnership|collaboration|license)?\s*"
        r"(?:agreement|contract|arrangement)\s+with\s+(?P<target>[A-Z][A-Za-z0-9&.,'() /-]{2,90})",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?P<kind>supply|customer|purchase|distribution|reseller|strategic partnership|collaboration|license)\s+"
        r"(?:agreement|contract|arrangement)\s+with\s+(?P<target>[A-Z][A-Za-z0-9&.,'() /-]{2,90})",
        flags=re.IGNORECASE,
    ),
]
PARTNER_PATTERNS = [
    re.compile(
        r"(?:partner(?:s|ed)?|partnership|collaboration|alliance)\s+with\s+"
        r"(?P<target>[A-Z][A-Za-z0-9&.,'() /-]{2,90})",
        flags=re.IGNORECASE,
    ),
]

GENERIC_TARGET_STOPWORDS = {
    "customer",
    "customers",
    "supplier",
    "suppliers",
    "the company",
    "company",
    "our",
    "we",
    "us",
    "none",
    "no",
    "one",
    "two",
    "major",
    "largest",
    "significant",
    "single",
    "sole",
}
GEOGRAPHIC_TARGET_TERMS = {
    "asia",
    "canada",
    "china",
    "europe",
    "germany",
    "india",
    "japan",
    "korea",
    "latin america",
    "mexico",
    "south america",
    "south korea",
    "u.s",
    "u.s.",
    "us",
    "united kingdom",
    "united states",
}
GENERIC_TARGET_PHRASES = {
    "certain key",
    "end customer",
    "end customers",
    "key supplier",
    "key suppliers",
    "major customer",
    "major customers",
    "online sales",
    "sales",
    "net sales",
    "table of contents",
}


def extract_relationship_edges_from_evidence(
    evidence: Mapping[str, Any],
    *,
    entity_registry: list[Mapping[str, Any]] | None = None,
    max_edges_per_row: int = 8,
) -> list[dict[str, Any]]:
    text = _compact_text(evidence.get("text") or evidence.get("evidence_text"), limit=6000)
    if not text or not _looks_relationship_relevant(text):
        return []
    source_tier = str(evidence.get("source_tier") or (evidence.get("metadata") or {}).get("source_tier") or "").strip()
    source_type = str(evidence.get("source_type") or (evidence.get("metadata") or {}).get("form_type") or "").strip()
    candidates: list[dict[str, Any]] = []
    candidates.extend(_customer_edges(evidence, text, entity_registry=entity_registry, source_tier=source_tier, source_type=source_type))
    candidates.extend(_supplier_edges(evidence, text, entity_registry=entity_registry, source_tier=source_tier, source_type=source_type))
    candidates.extend(_agreement_edges(evidence, text, entity_registry=entity_registry, source_tier=source_tier, source_type=source_type))
    candidates.extend(_partner_edges(evidence, text, entity_registry=entity_registry, source_tier=source_tier, source_type=source_type))
    return _dedupe_edges(candidates)[:max_edges_per_row]


def _customer_edges(
    evidence: Mapping[str, Any],
    text: str,
    *,
    entity_registry: list[Mapping[str, Any]] | None,
    source_tier: str,
    source_type: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pattern in CUSTOMER_CONCENTRATION_PATTERNS:
        for match in pattern.finditer(text):
            target = _clean_target_name(match.group("target"))
            if not _valid_target_name(target):
                continue
            rows.append(
                _edge_payload(
                    evidence,
                    text,
                    target,
                    relation_type="direct_customer_supplier",
                    direction="source_sells_to_target",
                    source_tier=source_tier,
                    source_type=source_type,
                    evidence_text=_span_excerpt(text, match.start(), match.end()),
                    percentage=match.groupdict().get("pct"),
                    metric_name=match.groupdict().get("metric") or "revenue",
                    entity_registry=entity_registry,
                )
            )
    return rows


def _supplier_edges(
    evidence: Mapping[str, Any],
    text: str,
    *,
    entity_registry: list[Mapping[str, Any]] | None,
    source_tier: str,
    source_type: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pattern in SUPPLIER_PATTERNS:
        for match in pattern.finditer(text):
            target = _clean_target_name(match.group("target"))
            if not _valid_target_name(target):
                continue
            rows.append(
                _edge_payload(
                    evidence,
                    text,
                    target,
                    relation_type="direct_customer_supplier",
                    direction="target_sells_to_source",
                    source_tier=source_tier,
                    source_type=source_type,
                    evidence_text=_span_excerpt(text, match.start(), match.end()),
                    metric_name="supplier_dependency",
                    entity_registry=entity_registry,
                )
            )
    return rows


def _agreement_edges(
    evidence: Mapping[str, Any],
    text: str,
    *,
    entity_registry: list[Mapping[str, Any]] | None,
    source_tier: str,
    source_type: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pattern in AGREEMENT_PATTERNS:
        for match in pattern.finditer(text):
            target = _clean_target_name(match.group("target"))
            if not _valid_target_name(target):
                continue
            kind = str(match.groupdict().get("kind") or "").lower()
            relation_type = "partner_channel" if "partnership" in kind or "collaboration" in kind else "contractual_relationship"
            rows.append(
                _edge_payload(
                    evidence,
                    text,
                    target,
                    relation_type=relation_type,
                    direction="unclear",
                    source_tier=source_tier,
                    source_type=source_type,
                    evidence_text=_span_excerpt(text, match.start(), match.end()),
                    metric_name=kind.replace(" ", "_") or "agreement",
                    entity_registry=entity_registry,
                )
            )
    return rows


def _partner_edges(
    evidence: Mapping[str, Any],
    text: str,
    *,
    entity_registry: list[Mapping[str, Any]] | None,
    source_tier: str,
    source_type: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pattern in PARTNER_PATTERNS:
        for match in pattern.finditer(text):
            target = _clean_target_name(match.group("target"))
            if not _valid_target_name(target):
                continue
            rows.append(
                _edge_payload(
                    evidence,
                    text,
                    target,
                    relation_type="partner_channel",
                    direction="bidirectional",
                    source_tier=source_tier,
                    source_type=source_type,
                    evidence_text=_span_excerpt(text, match.start(), match.end()),
                    metric_name="partnership",
                    entity_registry=entity_registry,
                )
            )
    return rows


def _edge_payload(
    evidence: Mapping[str, Any],
    text: str,
    target: str,
    *,
    relation_type: str,
    direction: str,
    source_tier: str,
    source_type: str,
    entity_registry: list[Mapping[str, Any]] | None,
    evidence_text: str,
    percentage: Any = None,
    metric_name: str = "",
) -> dict[str, Any]:
    resolution = resolve_entity_name(target, entity_registry or []) if entity_registry else {"status": "unresolved", "confidence": "low"}
    confidence = (
        "high"
        if resolution.get("status") == "resolved"
        and resolution.get("confidence") == "high"
        and source_tier in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
        else "medium"
    )
    return normalize_relationship_edge(
        {
            "source_ticker": evidence.get("ticker"),
            "source_cik": (evidence.get("metadata") or {}).get("cik") or evidence.get("cik"),
            "source_company_name": evidence.get("company"),
            "target_entity_id": resolution.get("entity_id"),
            "target_ticker": resolution.get("ticker"),
            "target_cik": resolution.get("cik"),
            "target_name_raw": target,
            "relation_type": relation_type,
            "direction": direction,
            "confidence": confidence,
            "source_tier": source_tier,
            "source_doc_type": source_type,
            "source_url_or_filing_id": evidence.get("source_url") or (evidence.get("metadata") or {}).get("accession_number"),
            "fiscal_year": evidence.get("fiscal_year"),
            "report_date": evidence.get("period_end") or evidence.get("publication_date"),
            "evidence_id": evidence.get("evidence_id"),
            "evidence_text": evidence_text,
            "percentage": percentage,
            "metric_name": metric_name,
            "valid_from": evidence.get("period_end") or evidence.get("publication_date"),
            "entity_resolution_status": resolution.get("status"),
            "entity_resolution_confidence": resolution.get("confidence"),
            "metadata": {
                "section": evidence.get("section"),
                "subsection": evidence.get("subsection"),
                "category_slug": (evidence.get("metadata") or {}).get("category_slug"),
            },
        }
    )


def _looks_relationship_relevant(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in SEC_RELATIONSHIP_KEYWORDS)


def _clean_target_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" .,:;()-")
    text = re.sub(r"\b(?:and|or|including|from|for|as|the)\s*$", "", text, flags=re.IGNORECASE).strip(" .,:;()-")
    text = re.split(r",\s+(?:the|a|an|we|which|that|related|included|including)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    text = re.split(
        r"\s+(?:accounted|represented|comprised|for|as|to|during|expand|develop|commercialize|manufactures|provides|supplies)\s+",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    text = _truncate_after_legal_suffix(text)
    return text.strip(" .,:;()-")


def _valid_target_name(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text.lower() in GENERIC_TARGET_STOPWORDS:
        return False
    if len(text) < 3 or len(text) > 90:
        return False
    words = text.split()
    if len(words) > 8:
        return False
    if not any(char.isalpha() for char in text):
        return False
    if text[0].islower():
        return False
    lower = text.lower()
    compact = re.sub(r"[^a-z0-9]+", "", lower)
    if compact in {"us", "usa"} or "-based" in lower:
        return False
    if lower.startswith("certain "):
        return False
    if any(phrase in lower for phrase in GENERIC_TARGET_PHRASES):
        return False
    geo_hits = {term for term in GEOGRAPHIC_TARGET_TERMS if re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", lower)}
    has_legal_suffix = re.search(r"\b(inc|corp|corporation|company|co|ltd|limited|llc|plc|ag|a/s)\b\.?", lower) is not None
    if lower in GEOGRAPHIC_TARGET_TERMS or (len(geo_hits) >= 2 and not has_legal_suffix):
        return False
    return True


def _dedupe_edges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("source_ticker") or ""),
            str(row.get("target_ticker") or row.get("target_name_raw") or "").lower(),
            str(row.get("relation_type") or ""),
            str(row.get("direction") or ""),
            str(row.get("evidence_id") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _truncate_after_legal_suffix(value: str) -> str:
    text = str(value or "").strip()
    suffixes = ("LLC", "Inc", "Inc.", "Corporation", "Corp", "Ltd", "Limited", "PLC", "AG", "A/S")
    for suffix in suffixes:
        pattern = re.compile(rf"\b{re.escape(suffix)}\b\.?", flags=re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return text[: match.end()]
    return text


def _span_excerpt(text: str, start: int, end: int, *, window: int = 500) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    return text[left:right].strip()


def _compact_text(value: Any, *, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]
