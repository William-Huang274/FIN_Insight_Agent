from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit, urlunsplit


CATALOG_SCHEMA = (
    "fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v1_0"
)
CONTRACT_REF = "fin_0_1_3.S1_08.current_source_catalog_candidate_generation:v1"
CASES = ("DELL", "MU", "NVDA")
GOLD_TOKEN_PREFIXES = ("SRC_", "DELL_E", "MU_E", "NVDA_E", "DELL_T", "MU_T", "NVDA_T")


class S108CandidateGenerationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def normalize_locator(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("https://"):
        split = urlsplit(text)
        return urlunsplit(
            (split.scheme.lower(), split.netloc.lower(), split.path.rstrip("/"), split.query, "")
        )
    return text


def load_source_catalog(path: str | Path) -> dict[str, Any]:
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        catalog.get("schema_version") != CATALOG_SCHEMA
        or catalog.get("contract_ref") != CONTRACT_REF
        or catalog.get("as_of") != "2026-08-06"
    ):
        raise S108CandidateGenerationError("s1_08_source_catalog_identity_invalid")
    serialized = json.dumps(catalog, ensure_ascii=False)
    if any(token in serialized for token in GOLD_TOKEN_PREFIXES):
        raise S108CandidateGenerationError("s1_08_gold_identifier_leaked_into_catalog")
    budgets = catalog.get("budgets") or {}
    if (
        budgets.get("maximum_revisions_per_target") != 2
        or budgets.get("selected_pack_ceiling_per_case") != 8
        or budgets.get("model_calls") != 0
        or budgets.get("identical_retry_forbidden") is not True
    ):
        raise S108CandidateGenerationError("s1_08_source_catalog_budget_invalid")
    entities = catalog.get("entities") or []
    keys = [str(row.get("entity_key") or "") for row in entities]
    if len(keys) != len(set(keys)) or not set(CASES).issubset(keys):
        raise S108CandidateGenerationError("s1_08_source_catalog_entity_set_invalid")
    for entity in entities:
        pages = entity.get("official_landing_pages") or []
        if not pages or any(not str(url).startswith("https://") for url in pages):
            raise S108CandidateGenerationError("s1_08_source_catalog_landing_page_invalid")
    return catalog


@dataclass(frozen=True)
class DiscoveryQuery:
    case_key: str
    target_key: str
    role_id: str
    revision: int
    query_text: str
    route_ids: tuple[str, ...]
    entity_keys: tuple[str, ...]
    prior_reason: str
    query_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_key": self.case_key,
            "target_key": self.target_key,
            "role_id": self.role_id,
            "revision": self.revision,
            "query_text": self.query_text,
            "route_ids": list(self.route_ids),
            "entity_keys": list(self.entity_keys),
            "prior_reason": self.prior_reason,
            "query_digest": self.query_digest,
        }


@dataclass(frozen=True)
class DiscoveryCandidate:
    case_key: str
    target_key: str
    role_id: str
    entity_key: str
    title: str
    locator: str
    published_on: str
    authority: str
    discovery_capture_ref: str
    discovery_capture_digest: str
    source_capture_ref: str
    source_capture_digest: str
    parser_capture_ref: str
    parser_capture_digest: str
    promoted: bool = True

    @property
    def candidate_digest(self) -> str:
        return canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_key": self.case_key,
            "target_key": self.target_key,
            "role_id": self.role_id,
            "entity_key": self.entity_key,
            "title": self.title,
            "locator": self.locator,
            "published_on": self.published_on,
            "authority": self.authority,
            "discovery_capture_ref": self.discovery_capture_ref,
            "discovery_capture_digest": self.discovery_capture_digest,
            "source_capture_ref": self.source_capture_ref,
            "source_capture_digest": self.source_capture_digest,
            "parser_capture_ref": self.parser_capture_ref,
            "parser_capture_digest": self.parser_capture_digest,
            "promoted": self.promoted,
        }


class DiscoveryAdapter(Protocol):
    def discover(self, query: DiscoveryQuery) -> Sequence[DiscoveryCandidate]: ...


def compile_initial_queries(
    *, catalog: Mapping[str, Any], case_key: str, research_objective: str
) -> tuple[DiscoveryQuery, ...]:
    if case_key not in CASES or not research_objective.strip():
        raise S108CandidateGenerationError("s1_08_query_case_or_objective_invalid")
    queries: list[DiscoveryQuery] = []
    for role in catalog.get("evidence_role_blueprints") or []:
        role_id = str(role["role_id"])
        entity_keys = _entities_for_role(catalog, case_key, role.get("entity_roles") or [])
        query_text = " ".join(
            [case_key, research_objective, *[str(term) for term in role["query_terms"]]]
        )
        queries.append(
            _make_query(
                case_key=case_key,
                target_key=f"{case_key.lower()}_{role_id}",
                role_id=role_id,
                revision=0,
                query_text=query_text,
                route_ids=tuple(str(value) for value in role["source_routes"]),
                entity_keys=entity_keys,
                prior_reason="initial_role_plan",
            )
        )
    return tuple(queries)


def compile_revision(
    *, catalog: Mapping[str, Any], prior: DiscoveryQuery, reason: str
) -> DiscoveryQuery:
    maximum = int(catalog["budgets"]["maximum_revisions_per_target"])
    revision = prior.revision + 1
    if revision > maximum:
        raise S108CandidateGenerationError("s1_08_query_revision_budget_exceeded")
    if not reason or reason == "identical_retry":
        raise S108CandidateGenerationError("s1_08_query_revision_reason_invalid")
    suffixes = {
        1: "current quarter official release transcript filing latest available",
        2: "prepared remarks exhibit risk factors capacity customer supplier reconciliation",
    }
    route_ids = prior.route_ids
    if revision == 1 and "sec_submissions_discovery" not in route_ids:
        route_ids = (*route_ids, "sec_submissions_discovery")
    query = _make_query(
        case_key=prior.case_key,
        target_key=prior.target_key,
        role_id=prior.role_id,
        revision=revision,
        query_text=f"{prior.query_text} {suffixes[revision]}",
        route_ids=route_ids,
        entity_keys=prior.entity_keys,
        prior_reason=reason,
    )
    if query.query_digest == prior.query_digest or query.query_text == prior.query_text:
        raise S108CandidateGenerationError("s1_08_identical_query_retry_forbidden")
    return query


def run_candidate_generation(
    *,
    catalog: Mapping[str, Any],
    case_key: str,
    research_objective: str,
    adapter: DiscoveryAdapter,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    accepted: dict[str, DiscoveryCandidate] = {}
    rejected: list[dict[str, Any]] = []
    as_of = date.fromisoformat(str(catalog["as_of"]))
    maximum_candidates = int(catalog["budgets"]["maximum_candidates_per_case"])
    for initial in compile_initial_queries(
        catalog=catalog, case_key=case_key, research_objective=research_objective
    ):
        query = initial
        while True:
            observed = list(adapter.discover(query))
            accepted_this_attempt = 0
            for candidate in observed:
                reasons = _candidate_rejection_reasons(
                    candidate=candidate,
                    query=query,
                    catalog=catalog,
                    as_of=as_of,
                )
                digest = candidate.candidate_digest
                if digest in accepted:
                    reasons.append("duplicate_candidate")
                if reasons:
                    rejected.append(
                        {"candidate_digest": digest, "reason_codes": sorted(set(reasons))}
                    )
                elif len(accepted) >= maximum_candidates:
                    rejected.append(
                        {"candidate_digest": digest, "reason_codes": ["candidate_case_ceiling_reached"]}
                    )
                else:
                    accepted[digest] = candidate
                    accepted_this_attempt += 1
            attempts.append(
                {
                    "query": query.as_dict(),
                    "observed_count": len(observed),
                    "accepted_count": accepted_this_attempt,
                    "stop_reason": "role_candidate_found" if accepted_this_attempt else "missing_role_candidate",
                }
            )
            if accepted_this_attempt or query.revision == int(
                catalog["budgets"]["maximum_revisions_per_target"]
            ):
                break
            query = compile_revision(
                catalog=catalog,
                prior=query,
                reason="no_qualified_candidate_for_required_role",
            )
    ordered = sorted(
        accepted.values(),
        key=lambda row: (row.role_id, row.entity_key, normalize_locator(row.locator), row.candidate_digest),
    )
    selected = ordered[: int(catalog["budgets"]["selected_pack_ceiling_per_case"])]
    body = {
        "schema_version": "fin_ia_0_1_3_s1_08_candidate_generation_result_v1_0",
        "contract_ref": CONTRACT_REF,
        "case_key": case_key,
        "as_of": catalog["as_of"],
        "catalog_digest": canonical_digest(catalog),
        "attempts": attempts,
        "accepted_candidates": [row.as_dict() for row in ordered],
        "selected_candidates": [row.as_dict() for row in selected],
        "rejected_candidates": rejected,
        "typed_gaps": [
            {
                "target_key": row["query"]["target_key"],
                "code": "required_evidence_role_not_found_after_bounded_revision",
            }
            for row in attempts
            if row["query"]["revision"] == 2 and row["accepted_count"] == 0
        ],
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": int(getattr(adapter, "network_calls", 0)),
            "query_attempts": len(attempts),
            "accepted_candidates": len(ordered),
            "selected_candidates": len(selected),
            "rejected_candidates": len(rejected),
        },
        "adapter_receipts": list(getattr(adapter, "receipts", ())),
    }
    return {**body, "result_digest": canonical_digest(body)}


def evaluator_only_gold_match(
    *,
    results: Sequence[Mapping[str, Any]],
    visible_pack: Mapping[str, Any],
    hidden_scoring: Mapping[str, Any],
) -> dict[str, Any]:
    source_by_locator: dict[str, str] = {}
    for source in visible_pack.get("source_registry") or []:
        locator = source.get("url") or source.get("artifact_ref")
        if locator:
            source_by_locator[normalize_locator(str(locator))] = str(source["source_id"])
        if source.get("authority") == "non_authoritative_market_context":
            source_by_locator["current_market_snapshot"] = str(source["source_id"])
    evidence_source_by_case = {
        str(case["case_key"]): {
            str(row["evidence_id"]): str(row["source_id"])
            for row in case.get("evidence_items") or []
        }
        for case in visible_pack.get("cases") or []
    }
    result_by_case = {str(row["case_key"]): row for row in results}
    cases: list[dict[str, Any]] = []
    for hidden_case in hidden_scoring.get("cases") or []:
        case_key = str(hidden_case["case_key"])
        result = result_by_case[case_key]
        matched_sources = {
            source_by_locator[normalize_locator(str(candidate.get("locator") or ""))]
            for candidate in result.get("accepted_candidates") or []
            if normalize_locator(str(candidate.get("locator") or "")) in source_by_locator
        }
        selected_sources = {
            source_by_locator[normalize_locator(str(candidate.get("locator") or ""))]
            for candidate in result.get("selected_candidates") or []
            if normalize_locator(str(candidate.get("locator") or "")) in source_by_locator
        }
        target_rows: list[dict[str, Any]] = []
        for target in hidden_case.get("required_insights") or []:
            evidence_ids = [str(value) for value in target.get("evidence_ids") or []]
            required_sources = {
                evidence_source_by_case[case_key][evidence_id]
                for evidence_id in evidence_ids
            }
            target_rows.append(
                {
                    "target_digest": canonical_digest(
                        {"case_key": case_key, "target_id": target["target_id"]}
                    ),
                    "required_evidence_count": len(evidence_ids),
                    "target_in_pool": required_sources.issubset(matched_sources),
                    "target_in_selected_pack": required_sources.issubset(selected_sources),
                }
            )
        cases.append(
            {
                "case_key": case_key,
                "matched_source_count": len(matched_sources),
                "target_groups": target_rows,
                "target_in_pool_recall": sum(row["target_in_pool"] for row in target_rows) / len(target_rows),
                "selected_pack_required_slot_coverage": sum(
                    row["target_in_selected_pack"] for row in target_rows
                ) / len(target_rows),
            }
        )
    all_targets = [target for case in cases for target in case["target_groups"]]
    body = {
        "schema_version": "fin_ia_0_1_3_s1_08_evaluator_only_candidate_match_v1_0",
        "contract_ref": CONTRACT_REF,
        "cases": cases,
        "summary": {
            "target_groups": len(all_targets),
            "target_in_pool_recall": sum(row["target_in_pool"] for row in all_targets) / len(all_targets),
            "selected_pack_required_slot_coverage": sum(
                row["target_in_selected_pack"] for row in all_targets
            ) / len(all_targets),
            "ranking_metrics_admitted": all(row["target_in_pool"] for row in all_targets),
        },
        "planner_received_hidden_gold": False,
    }
    return {**body, "evaluation_digest": canonical_digest(body)}


def _entities_for_role(
    catalog: Mapping[str, Any], case_key: str, requested_roles: Sequence[str]
) -> tuple[str, ...]:
    selected: list[str] = []
    relationship_roles = set(str(value) for value in requested_roles) - {"subject"}
    for entity in catalog.get("entities") or []:
        key = str(entity["entity_key"])
        roles = set(str(value) for value in entity.get("ecosystem_roles") or [])
        if "subject" in requested_roles and key == case_key:
            selected.append(key)
        elif roles.intersection(relationship_roles) and key != case_key:
            selected.append(key)
    return tuple(sorted(set(selected)))


def _make_query(
    *,
    case_key: str,
    target_key: str,
    role_id: str,
    revision: int,
    query_text: str,
    route_ids: tuple[str, ...],
    entity_keys: tuple[str, ...],
    prior_reason: str,
) -> DiscoveryQuery:
    body = {
        "case_key": case_key,
        "target_key": target_key,
        "role_id": role_id,
        "revision": revision,
        "query_text": " ".join(query_text.split()),
        "route_ids": list(route_ids),
        "entity_keys": list(entity_keys),
        "prior_reason": prior_reason,
    }
    return DiscoveryQuery(
        **{key: value for key, value in body.items() if key not in {"route_ids", "entity_keys"}},
        route_ids=route_ids,
        entity_keys=entity_keys,
        query_digest=canonical_digest(body),
    )


def _candidate_rejection_reasons(
    *,
    candidate: DiscoveryCandidate,
    query: DiscoveryQuery,
    catalog: Mapping[str, Any],
    as_of: date,
) -> list[str]:
    reasons: list[str] = []
    known_entities = {str(row["entity_key"]) for row in catalog.get("entities") or []}
    local_locator = not candidate.locator.startswith("https://")
    if candidate.case_key != query.case_key:
        reasons.append("cross_case_candidate")
    if candidate.target_key != query.target_key or candidate.role_id != query.role_id:
        reasons.append("query_binding_mismatch")
    if candidate.entity_key not in known_entities:
        reasons.append("unknown_entity")
    if local_locator and candidate.locator != "current_market_snapshot":
        reasons.append("https_or_governed_local_locator_required")
    try:
        if date.fromisoformat(candidate.published_on) > as_of:
            reasons.append("candidate_after_as_of")
    except ValueError:
        reasons.append("candidate_date_invalid")
    for ref, digest in (
        (candidate.discovery_capture_ref, candidate.discovery_capture_digest),
        (candidate.source_capture_ref, candidate.source_capture_digest),
        (candidate.parser_capture_ref, candidate.parser_capture_digest),
    ):
        if not ref or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            reasons.append("capture_first_lineage_invalid")
            break
    if not candidate.promoted:
        reasons.append("candidate_not_evidence_promoted")
    return reasons


__all__ = [
    "CATALOG_SCHEMA",
    "CONTRACT_REF",
    "DiscoveryAdapter",
    "DiscoveryCandidate",
    "DiscoveryQuery",
    "S108CandidateGenerationError",
    "canonical_digest",
    "compile_initial_queries",
    "compile_revision",
    "evaluator_only_gold_match",
    "load_source_catalog",
    "normalize_locator",
    "run_candidate_generation",
]
