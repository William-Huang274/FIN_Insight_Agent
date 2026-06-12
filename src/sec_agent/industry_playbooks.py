from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAYBOOK_REGISTRY_PATH = REPO_ROOT / "configs" / "industry_playbooks_v0_1.yaml"
PLAYBOOK_REGISTRY_SCHEMA_VERSION = "fin_agent_industry_playbook_registry_v0.1"
GENERIC_PLAYBOOK_ID = "generic_public_research"


def load_playbook_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else DEFAULT_PLAYBOOK_REGISTRY_PATH
    if not registry_path.exists():
        return _fallback_registry()
    with registry_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, Mapping):
        return _fallback_registry()
    return normalize_playbook_registry(payload)


def normalize_playbook_registry(payload: Mapping[str, Any]) -> dict[str, Any]:
    playbooks = [
        _normalize_playbook(item)
        for item in payload.get("playbooks") or []
        if isinstance(item, Mapping) and str(item.get("playbook_id") or "").strip()
    ]
    if not any(item.get("playbook_id") == GENERIC_PLAYBOOK_ID for item in playbooks):
        playbooks.insert(0, _generic_playbook())
    common_policy = payload.get("common_policy") if isinstance(payload.get("common_policy"), Mapping) else {}
    return {
        "schema_version": str(payload.get("schema_version") or PLAYBOOK_REGISTRY_SCHEMA_VERSION),
        "registry_id": str(payload.get("registry_id") or "public_evidence_industry_playbooks_v0_1"),
        "default_playbook_id": str(payload.get("default_playbook_id") or GENERIC_PLAYBOOK_ID),
        "common_policy": dict(common_policy),
        "playbooks": playbooks,
    }


def validate_playbook_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if str(registry.get("schema_version") or "") != PLAYBOOK_REGISTRY_SCHEMA_VERSION:
        errors.append({"type": "invalid_schema_version", "schema_version": registry.get("schema_version")})
    playbooks = [item for item in registry.get("playbooks") or [] if isinstance(item, Mapping)]
    if not playbooks:
        errors.append({"type": "playbooks_required"})
    seen: set[str] = set()
    required = {
        "semiconductors",
        "consumer_electronics",
        "software_saas",
        "banks",
        "energy_oil_gas",
        "pharma_biotech",
        "autos_ev",
        "retail_cpg",
    }
    for playbook in playbooks:
        playbook_id = str(playbook.get("playbook_id") or "")
        if not playbook_id:
            errors.append({"type": "playbook_id_required"})
            continue
        if playbook_id in seen:
            errors.append({"type": "duplicate_playbook_id", "playbook_id": playbook_id})
        seen.add(playbook_id)
        if not playbook.get("industry_schema"):
            errors.append({"type": "industry_schema_required", "playbook_id": playbook_id})
        if not playbook.get("source_family_policy") and playbook_id != GENERIC_PLAYBOOK_ID:
            warnings.append({"type": "source_family_policy_empty", "playbook_id": playbook_id})
        if not playbook.get("specialist_routing"):
            errors.append({"type": "specialist_routing_required", "playbook_id": playbook_id})
    missing = sorted(required - seen)
    if missing:
        errors.append({"type": "required_initial_playbooks_missing", "playbook_ids": missing})
    return {"status": "pass" if not errors else "fail", "errors": errors, "warnings": warnings}


def playbook_by_id(registry: Mapping[str, Any], playbook_id: str) -> dict[str, Any] | None:
    target = str(playbook_id or "").strip()
    for playbook in registry.get("playbooks") or []:
        if isinstance(playbook, Mapping) and str(playbook.get("playbook_id") or "") == target:
            return dict(playbook)
    return None


def match_playbook_candidates(
    categories: Mapping[str, set[str]] | Mapping[str, list[str]],
    registry: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    normalized_registry = normalize_playbook_registry(registry or load_playbook_registry())
    matches: dict[str, dict[str, Any]] = {}
    for category, tickers in categories.items():
        category_text = str(category or "").lower()
        ticker_count = len(list(tickers or []))
        for playbook in normalized_registry.get("playbooks") or []:
            if not isinstance(playbook, Mapping) or playbook.get("playbook_id") == GENERIC_PLAYBOOK_ID:
                continue
            aliases = _strings(playbook.get("aliases"))
            if any(alias.lower() in category_text for alias in aliases):
                item = matches.setdefault(str(playbook.get("playbook_id")), _candidate_from_playbook(playbook, status="candidate"))
                item["matched_categories"].append(str(category))
                item["ticker_count"] += ticker_count
    if matches:
        return sorted(matches.values(), key=lambda item: (-int(item.get("ticker_count") or 0), str(item.get("playbook_id") or "")))
    generic = playbook_by_id(normalized_registry, str(normalized_registry.get("default_playbook_id") or GENERIC_PLAYBOOK_ID)) or _generic_playbook()
    fallback = _candidate_from_playbook(generic, status="fallback_candidate")
    fallback["coverage_gap"] = {
        "gap_type": "industry_playbook_not_matched",
        "reason": "No configured industry playbook matched the manifest categories.",
    }
    fallback["ticker_count"] = sum(len(list(tickers or [])) for tickers in categories.values())
    return [fallback]


def compact_playbook_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_playbook_registry(registry)
    return {
        "schema_version": normalized.get("schema_version"),
        "registry_id": normalized.get("registry_id"),
        "default_playbook_id": normalized.get("default_playbook_id"),
        "playbook_count": len(normalized.get("playbooks") or []),
        "playbooks": [
            _candidate_from_playbook(playbook, status="registry_available")
            for playbook in normalized.get("playbooks") or []
            if isinstance(playbook, Mapping)
        ],
    }


def selected_playbook_policy(
    inventory: Mapping[str, Any],
    selected_playbook_ids: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    candidates = [dict(item) for item in inventory.get("playbook_candidates") or [] if isinstance(item, Mapping)]
    if selected_playbook_ids:
        selected = [item for item in candidates if str(item.get("playbook_id") or "") in set(_strings(selected_playbook_ids))]
    else:
        selected = candidates[:1]
    if not selected:
        return {}
    source_policy: dict[str, Any] = {}
    forbidden_claims: list[str] = []
    commercial_gap_policy: dict[str, Any] = {}
    web_scope_policy_ids: list[str] = []
    default_source_families: list[str] = []
    specialist_routing: dict[str, str] = {}
    for candidate in selected:
        source_policy.update(dict(candidate.get("source_family_policy") or candidate.get("source_policy_summary") or {}))
        forbidden_claims.extend(_strings(candidate.get("forbidden_claims")))
        commercial_gap_policy.update(dict(candidate.get("commercial_gap_policy") or {}))
        web_scope_policy_ids.extend(_strings(candidate.get("web_scope_policy_ids")))
        default_source_families.extend(_strings(candidate.get("default_source_families")))
        specialist_routing.update({str(k): str(v) for k, v in dict(candidate.get("specialist_routing") or {}).items()})
    return {
        "schema_version": "fin_agent_selected_playbook_policy_v0.1",
        "selected_playbook_ids": _dedupe([str(item.get("playbook_id") or "") for item in selected]),
        "industry_schemas": _dedupe([str(item.get("industry_schema") or "") for item in selected]),
        "default_source_families": _dedupe(default_source_families),
        "source_family_policy": source_policy,
        "forbidden_claims": _dedupe(forbidden_claims),
        "commercial_gap_policy": commercial_gap_policy,
        "web_scope_policy_ids": _dedupe(web_scope_policy_ids),
        "specialist_routing": specialist_routing,
    }


def _candidate_from_playbook(playbook: Mapping[str, Any], *, status: str) -> dict[str, Any]:
    return {
        "playbook_id": str(playbook.get("playbook_id") or ""),
        "industry_schema": str(playbook.get("industry_schema") or ""),
        "matched_categories": [],
        "ticker_count": 0,
        "status": status,
        "business_model_drivers": _strings(playbook.get("business_model_drivers"))[:10],
        "default_source_families": _strings(playbook.get("default_source_families"))[:10],
        "deep_only_source_families": _strings(playbook.get("deep_only_source_families"))[:8],
        "source_family_policy": _source_policy_summary(playbook.get("source_family_policy")),
        "commercial_gap_policy": dict(playbook.get("commercial_gap_policy") or {}),
        "forbidden_claims": _strings(playbook.get("forbidden_claims"))[:12],
        "common_failure_modes": _strings(playbook.get("common_failure_modes"))[:8],
        "specialist_routing": {str(k): str(v) for k, v in dict(playbook.get("specialist_routing") or {}).items()},
        "web_scope_policy_ids": _strings(playbook.get("web_scope_policy_ids"))[:8],
    }


def _normalize_playbook(payload: Mapping[str, Any]) -> dict[str, Any]:
    common_safe = dict(payload)
    common_safe["aliases"] = _strings(payload.get("aliases"))
    common_safe["business_model_drivers"] = _strings(payload.get("business_model_drivers"))
    common_safe["default_source_families"] = _strings(payload.get("default_source_families"))
    common_safe["deep_only_source_families"] = _strings(payload.get("deep_only_source_families"))
    common_safe["source_family_policy"] = _source_policy_summary(payload.get("source_family_policy"))
    common_safe["commercial_gap_policy"] = dict(payload.get("commercial_gap_policy") or {})
    common_safe["common_failure_modes"] = _strings(payload.get("common_failure_modes"))
    common_safe["forbidden_claims"] = _strings(payload.get("forbidden_claims"))
    common_safe["specialist_routing"] = {str(k): str(v) for k, v in dict(payload.get("specialist_routing") or {}).items()}
    common_safe["web_scope_policy_ids"] = _strings(payload.get("web_scope_policy_ids"))
    return common_safe


def _source_policy_summary(value: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(value, Mapping):
        return result
    for family, policy in value.items():
        if not isinstance(policy, Mapping):
            continue
        item = {
            "allowed_claims": _strings(policy.get("allowed_claims"))[:12],
            "forbidden_claims": _strings(policy.get("forbidden_claims"))[:12],
            "requires": _strings(policy.get("requires"))[:8],
            "allowed_source_classes": _strings(policy.get("allowed_source_classes"))[:8],
        }
        result[str(family)] = {key: val for key, val in item.items() if val}
    return result


def _fallback_registry() -> dict[str, Any]:
    return {
        "schema_version": PLAYBOOK_REGISTRY_SCHEMA_VERSION,
        "registry_id": "fallback_generic_playbook_registry",
        "default_playbook_id": GENERIC_PLAYBOOK_ID,
        "common_policy": {},
        "playbooks": [_generic_playbook()],
    }


def _generic_playbook() -> dict[str, Any]:
    return {
        "playbook_id": GENERIC_PLAYBOOK_ID,
        "industry_schema": "generic",
        "aliases": ["generic"],
        "business_model_drivers": ["reported_financials", "management_commentary", "risk_factors"],
        "default_source_families": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "deep_only_source_families": [],
        "source_family_policy": {},
        "commercial_gap_policy": {},
        "common_failure_modes": ["industry_not_covered_by_playbook"],
        "forbidden_claims": ["commercial_tracker_replacement", "unsupported_product_or_market_share_fact"],
        "specialist_routing": {"fundamental_analyst": "high", "risk_counterevidence_analyst": "conditional"},
        "web_scope_policy_ids": [],
    }


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _dedupe(value: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
