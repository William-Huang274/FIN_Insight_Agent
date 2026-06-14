from __future__ import annotations

from typing import Any, Mapping


ROLE_EVIDENCE_SELECTOR_SCHEMA_VERSION = "finsight_role_evidence_selector_v0_1"

ROLE_POLICIES = {
    "fundamental_analyst": {
        "max_rows": 48,
        "preferred_terms": ("financial_statement", "income", "balance", "cash_flow", "fundamental_statement_pack", "derived_metric"),
        "required_source_families": ("primary_sec_filing",),
    },
    "product_technology_analyst": {
        "max_rows": 48,
        "preferred_terms": ("product", "sku", "model", "spec", "capacity", "generation", "company_product_evidence_graph"),
        "required_source_families": ("company_product_evidence_graph", "primary_sec_filing", "public_source_context", "live_public_web_context"),
    },
    "market_valuation_analyst": {
        "max_rows": 32,
        "preferred_terms": ("market", "valuation", "price", "volume", "event_window", "share"),
        "required_source_families": ("market_snapshot", "industry_snapshot", "relationship_graph"),
    },
    "capital_ownership_macro_analyst": {
        "max_rows": 40,
        "preferred_terms": ("debt", "credit", "offering", "13f", "ownership", "insider", "macro", "capital"),
        "required_source_families": ("primary_sec_filing", "public_source_context"),
    },
    "risk_counterevidence_analyst": {
        "max_rows": 32,
        "preferred_terms": ("risk", "litigation", "regulatory", "conflict", "unsupported", "counter"),
        "required_source_families": ("primary_sec_filing", "company_authored_unaudited_sec_filing", "public_source_context"),
    },
}


def select_role_evidence(
    rows: list[Mapping[str, Any]],
    *,
    role: str,
    max_rows: int | None = None,
) -> dict[str, Any]:
    policy = ROLE_POLICIES.get(role, {"max_rows": 24, "preferred_terms": (), "required_source_families": ()})
    limit = int(max_rows or policy["max_rows"])
    scored = []
    dropped = []
    for index, row in enumerate(rows):
        score = _score_row(row, preferred_terms=policy["preferred_terms"], source_families=policy["required_source_families"])
        item = {"row": dict(row), "score": score, "input_index": index}
        if score <= 0:
            dropped.append({**item, "drop_reason": "role_policy_no_match"})
        else:
            scored.append(item)
    selected = sorted(scored, key=lambda item: (-int(item["score"]), int(item["input_index"])))[:limit]
    cap_hit = len(scored) > len(selected)
    return {
        "schema_version": ROLE_EVIDENCE_SELECTOR_SCHEMA_VERSION,
        "role": role,
        "input_count": len(rows),
        "selected_count": len(selected),
        "dropped_count": len(dropped) + max(0, len(scored) - len(selected)),
        "cap_hit": cap_hit,
        "cap_reason": "role_quota_limit" if cap_hit else "",
        "selected_rows": [item["row"] for item in selected],
        "dropped_taxonomy": _dropped_taxonomy(dropped, cap_hit=cap_hit, capped_count=max(0, len(scored) - len(selected))),
        "policy": {
            "max_rows": limit,
            "preferred_terms": list(policy["preferred_terms"]),
            "required_source_families": list(policy["required_source_families"]),
        },
    }


def _score_row(row: Mapping[str, Any], *, preferred_terms: tuple[str, ...], source_families: tuple[str, ...]) -> int:
    haystack = " ".join(str(row.get(key) or "") for key in row.keys()).lower()
    source = str(row.get("source_family") or row.get("source_tier") or "").lower()
    score = 0
    if source in {item.lower() for item in source_families}:
        score += 3
    for term in preferred_terms:
        if term.lower() in haystack:
            score += 2
    if row.get("evidence_ref") or row.get("evidence_id"):
        score += 1
    if str(row.get("authority") or "").lower() in {"exact", "company_disclosed", "primary"}:
        score += 2
    return score


def _dropped_taxonomy(dropped: list[Mapping[str, Any]], *, cap_hit: bool, capped_count: int) -> dict[str, int]:
    taxonomy: dict[str, int] = {}
    for item in dropped:
        reason = str(item.get("drop_reason") or "unknown")
        taxonomy[reason] = taxonomy.get(reason, 0) + 1
    if cap_hit:
        taxonomy["role_quota_limit"] = taxonomy.get("role_quota_limit", 0) + capped_count
    return taxonomy
