from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit


POLICY_SCHEMA = "fin_ia_0_1_3_s1_residual_gap_external_supplement_policy_v1_0"
PLAN_SCHEMA = "fin_ia_0_1_3_s1_residual_gap_external_priority_plan_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.residual_gap_official_first_external_supplement:v1"
RUN_SCOPE = "S1_RESIDUAL_GAP_EXTERNAL_SUPPLEMENT"
CASES = ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ResidualGapExternalSupplementError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ResidualGapExternalSupplementError(code)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def load_residual_gap_external_supplement_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("run_scope") == RUN_SCOPE
        and tuple(policy.get("cases") or ()) == CASES
        and policy.get("as_of_date") == "2026-08-06",
        "residual_external_policy_identity_invalid",
    )
    result_binding = policy.get("local_evidence_pack_result") or {}
    result_path = _resolve(root, str(result_binding.get("ref") or ""))
    _require(
        result_path.is_file()
        and file_sha256(result_path) == str(result_binding.get("sha256") or ""),
        "residual_external_pack_result_binding_invalid",
    )
    budgets = policy.get("budget") or {}
    _require(
        budgets
        == {
            "selected_intent_count": 12,
            "selected_intents_per_case": 2,
            "official_discovery_fetch_ceiling": 6,
            "locator_provider_call_ceiling": 12,
            "official_document_fetch_ceiling": 12,
            "total_network_call_ceiling": 30,
            "result_ceiling_per_locator_query": 10,
            "retry_ceiling": 0,
            "model_call_ceiling": 0,
            "embedding_call_ceiling": 0,
            "rerank_call_ceiling": 0,
            "automatic_retry": False,
        },
        "residual_external_budget_invalid",
    )
    profiles = policy.get("case_profiles") or {}
    official_host_registry = policy.get("official_host_registry") or {}
    groups = policy.get("intent_groups") or []
    _require(set(profiles) == set(CASES), "residual_external_case_profiles_invalid")
    _require(len(groups) == 12, "residual_external_intent_group_count_invalid")
    counts = Counter(str(row.get("case_key") or "") for row in groups)
    _require(
        counts == Counter({case_key: 2 for case_key in CASES}),
        "residual_external_case_budget_invalid",
    )
    for case_key, profile in profiles.items():
        roots = profile.get("official_discovery_roots") or []
        hosts = {str(value).lower() for value in profile.get("allowed_subject_hosts") or []}
        _require(
            profile.get("case_key") == case_key
            and profile.get("subject_aliases")
            and profile.get("period_terms", {}).get("en")
            and profile.get("period_terms", {}).get("zh")
            and len(roots) == 1
            and hosts,
            "residual_external_case_profile_invalid",
        )
        parsed = urlsplit(str(roots[0]))
        _require(
            parsed.scheme == "https" and (parsed.hostname or "").lower() in hosts,
            "residual_external_discovery_root_invalid",
        )
    _require(
        set(official_host_registry) == {"DELL", "MU", "TSMC", "NVDA", "ORCL", "ASML", "ANET"}
        and all(
            hosts
            and all(
                isinstance(host, str)
                and host == host.lower()
                and "." in host
                and "/" not in host
                and ":" not in host
                for host in hosts
            )
            for hosts in official_host_registry.values()
        ),
        "residual_external_official_host_registry_invalid",
    )
    for group in groups:
        owner_keys = tuple(str(value) for value in group.get("evidence_owner_entity_keys") or ())
        group_hosts = {str(value).lower() for value in group.get("allowed_document_hosts") or ()}
        registered_hosts = {
            host
            for owner_key in owner_keys
            for host in official_host_registry.get(owner_key, ())
        }
        _require(
            owner_keys
            and all(owner_key in official_host_registry for owner_key in owner_keys)
            and group_hosts
            and group_hosts.issubset(registered_hosts),
            "residual_external_intent_official_route_invalid",
        )
    serialized = json.dumps(policy, ensure_ascii=False)
    _require(
        "gold_target" not in serialized.lower()
        and "expected_answer" not in serialized.lower(),
        "residual_external_gold_leak",
    )
    return policy


def load_bound_local_evidence_packs(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    root = Path(repo_root).resolve()
    binding = policy["local_evidence_pack_result"]
    result_path = _resolve(root, str(binding["ref"]))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    _require(
        result.get("status")
        == "terminal_succeeded_six_case_local_evidence_packs_with_declared_gaps"
        and result.get("result_digest") == str(binding.get("result_digest") or "")
        and result.get("materialization_order") == list(CASES),
        "residual_external_pack_result_invalid",
    )
    artifact_root = _resolve(root, str(policy.get("local_evidence_pack_artifact_root") or ""))
    packs: dict[str, dict[str, Any]] = {}
    for case_key in CASES:
        ref = (result.get("pack_artifacts") or {}).get(case_key) or {}
        path = artifact_root / str(ref.get("object_key") or "")
        _require(
            path.is_file()
            and file_sha256(path) == str(ref.get("digest") or "")
            and _HEX64.fullmatch(str(ref.get("digest") or "")) is not None,
            "residual_external_local_pack_artifact_invalid",
        )
        pack = json.loads(path.read_text(encoding="utf-8"))
        _require(
            pack.get("case_key") == case_key
            and pack.get("status") == "local_evidence_pack_ready_with_declared_residual_gaps"
            and canonical_digest({
                key: value
                for key, value in pack.items()
                if key != "pack_payload_digest"
            })
            == pack.get("pack_payload_digest"),
            "residual_external_local_pack_payload_invalid",
        )
        packs[case_key] = pack
    return result, packs


def compile_residual_gap_external_priority_plan(
    *,
    policy: Mapping[str, Any],
    local_result: Mapping[str, Any],
    packs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    raw_gaps: dict[str, dict[str, Any]] = {}
    for case_key in CASES:
        for gap in packs[case_key].get("residual_gaps") or []:
            gap_id = str(gap.get("gap_id") or "")
            _require(gap_id and gap_id not in raw_gaps, "residual_external_gap_identity_invalid")
            raw_gaps[gap_id] = {**deepcopy(dict(gap)), "case_key": case_key}
    _require(len(raw_gaps) == 126, "residual_external_raw_gap_count_invalid")

    selected_gap_ids: set[str] = set()
    intents: list[dict[str, Any]] = []
    for group in policy["intent_groups"]:
        case_key = str(group["case_key"])
        profile = policy["case_profiles"][case_key]
        gap_ids = tuple(str(value) for value in group.get("selected_gap_ids") or ())
        _require(gap_ids, "residual_external_selected_gap_set_empty")
        _require(
            all(value in raw_gaps and raw_gaps[value]["case_key"] == case_key for value in gap_ids),
            "residual_external_selected_gap_unknown_or_cross_case",
        )
        _require(
            not selected_gap_ids.intersection(gap_ids),
            "residual_external_selected_gap_duplicate",
        )
        selected_gap_ids.update(gap_ids)
        intent = _compile_one_intent(group=group, profile=profile, gaps=raw_gaps)
        intents.append(intent)

    intents.sort(key=lambda row: (CASES.index(row["case_key"]), row["intent_id"]))
    _require(
        len(intents) == int(policy["budget"]["selected_intent_count"]),
        "residual_external_selected_intent_count_invalid",
    )
    deferred = [
        _deferred_gap_disposition(gap)
        for gap_id, gap in sorted(raw_gaps.items())
        if gap_id not in selected_gap_ids
    ]
    _require(
        len(selected_gap_ids) + len(deferred) == len(raw_gaps),
        "residual_external_gap_disposition_incomplete",
    )
    body = {
        "schema_version": PLAN_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "recorded_at": "2026-08-10",
        "status": "zero_call_priority_plan_ready_network_authority_not_issued",
        "as_of_date": policy["as_of_date"],
        "local_evidence_pack_result_digest": local_result["result_digest"],
        "local_pack_payload_digests": deepcopy(dict(local_result["pack_payload_digests"])),
        "raw_gap_count": len(raw_gaps),
        "selected_gap_count": len(selected_gap_ids),
        "deferred_gap_count": len(deferred),
        "selected_intents": intents,
        "deferred_gap_dispositions": deferred,
        "budget": deepcopy(dict(policy["budget"])),
        "routing_contract": deepcopy(dict(policy["routing_contract"])),
        "stage_acceptance": {
            "all_raw_gaps_dispositioned": True,
            "two_intents_per_case": True,
            "official_first": True,
            "broad_provider_locator_only": True,
            "provider_snippet_evidence_allowed": False,
            "network_authority_issued": False,
            "external_capture_complete": False,
            "external_evidence_readjudicated": False,
            "deepseek_research": False,
            "release": False,
        },
        "known_boundary": (
            "This zero-call plan reduces 126 raw facets to 12 bounded research intents. "
            "It does not authorize network or provider calls, treat provider snippets as "
            "Evidence, claim that public data exists, or close the local typed gaps."
        ),
    }
    plan = {**body, "plan_digest": canonical_digest(body)}
    validate_residual_gap_external_priority_plan(plan, policy=policy)
    return plan


def validate_residual_gap_external_priority_plan(
    plan: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
) -> None:
    body = deepcopy(dict(plan))
    supplied = str(body.pop("plan_digest", ""))
    _require(
        plan.get("schema_version") == PLAN_SCHEMA
        and plan.get("contract_ref") == CONTRACT_REF
        and supplied == canonical_digest(body),
        "residual_external_plan_identity_invalid",
    )
    intents = list(plan.get("selected_intents") or [])
    deferred = list(plan.get("deferred_gap_dispositions") or [])
    _require(
        len(intents) == 12
        and plan.get("raw_gap_count") == 126
        and int(plan.get("selected_gap_count") or 0) + len(deferred) == 126,
        "residual_external_plan_cardinality_invalid",
    )
    _require(
        Counter(str(row.get("case_key") or "") for row in intents)
        == Counter({case_key: 2 for case_key in CASES}),
        "residual_external_plan_case_budget_invalid",
    )
    selected_ids = [gap_id for row in intents for gap_id in row.get("selected_gap_ids") or []]
    deferred_ids = [str(row.get("gap_id") or "") for row in deferred]
    _require(
        len(set(selected_ids)) == len(selected_ids)
        and len(set(deferred_ids)) == len(deferred_ids)
        and not set(selected_ids).intersection(deferred_ids),
        "residual_external_plan_gap_partition_invalid",
    )
    for row in intents:
        intent_payload = {
            key: deepcopy(value)
            for key, value in row.items()
            if key not in {"intent_id", "intent_digest"}
        }
        expected_intent_digest = canonical_digest(intent_payload)
        _require(
            row.get("intent_digest") == expected_intent_digest
            and row.get("intent_id")
            == (
                f"residual_search_intent::{row.get('case_key')}::"
                f"{row.get('intent_key')}::{expected_intent_digest[:16]}"
            )
            and row.get("provider_role") == "locator_only"
            and row.get("evidence_promotion_allowed") is False
            and row.get("writer_citable") is False
            and row.get("official_domain_query", {}).get("en")
            and row.get("official_domain_query", {}).get("zh")
            and row.get("allowed_document_hosts"),
            "residual_external_plan_intent_boundary_invalid",
        )
        owner_keys = tuple(str(value) for value in row.get("evidence_owner_entity_keys") or ())
        registered_hosts = {
            host
            for owner_key in owner_keys
            for host in policy["official_host_registry"].get(owner_key, ())
        }
        _require(
            owner_keys
            and set(row.get("allowed_document_hosts") or ()).issubset(registered_hosts),
            "residual_external_plan_intent_route_invalid",
        )
        query_surface = json.dumps(
            {
                "official": row["official_domain_query"],
                "semantic": row["semantic_locator_query"],
            },
            ensure_ascii=False,
        )
        _require(
            "http://" not in query_surface.lower()
            and "https://" not in query_surface.lower()
            and "gold_target" not in query_surface.lower(),
            "residual_external_query_surface_invalid",
        )
        _require(
            all(
                f"site:{host}" in row["official_domain_query"][language]
                for host in row["allowed_document_hosts"]
                for language in ("en", "zh")
            ),
            "residual_external_official_domain_query_invalid",
        )
    _require(
        plan.get("budget") == policy.get("budget")
        and plan.get("stage_acceptance", {}).get("network_authority_issued") is False,
        "residual_external_plan_authority_boundary_invalid",
    )


def _compile_one_intent(
    *,
    group: Mapping[str, Any],
    profile: Mapping[str, Any],
    gaps: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    case_key = str(group["case_key"])
    aliases = tuple(str(value) for value in profile["subject_aliases"])
    owners = tuple(str(value) for value in group.get("evidence_owner_aliases") or aliases)
    hosts = tuple(sorted({str(value).lower() for value in group["allowed_document_hosts"]}))
    _require(hosts, "residual_external_intent_host_missing")
    for host in hosts:
        _require(
            host and "/" not in host and ":" not in host and "." in host,
            "residual_external_intent_host_invalid",
        )
    query_by_language: dict[str, str] = {}
    semantic_by_language: dict[str, str] = {}
    for language in ("en", "zh"):
        components = [
            aliases[0],
            " ".join(owners),
            " ".join(str(value) for value in profile["period_terms"][language]),
            " ".join(str(value) for value in group["document_types"][language]),
            " ".join(str(value) for value in group["query_atoms"][language]),
        ]
        semantic = " ".join(" ".join(components).split())
        site_clause = " OR ".join(f"site:{host}" for host in hosts)
        semantic_by_language[language] = semantic
        query_by_language[language] = f"{semantic} {site_clause}"
    payload = {
        "intent_key": str(group["intent_key"]),
        "case_key": case_key,
        "decision_surface": str(group["decision_surface"]),
        "priority": str(group["priority"]),
        "public_obtainability": str(group["public_obtainability"]),
        "subject_aliases": list(aliases),
        "evidence_owner_entity_keys": list(group["evidence_owner_entity_keys"]),
        "evidence_owner_aliases": list(owners),
        "relationship_direction": str(group["relationship_direction"]),
        "source_families": list(group["source_families"]),
        "selected_gap_ids": list(group["selected_gap_ids"]),
        "selected_facets": sorted({str(gaps[gap_id]["facet_id"]) for gap_id in group["selected_gap_ids"]}),
        "official_discovery_roots": list(profile["official_discovery_roots"]),
        "allowed_document_hosts": list(hosts),
        "official_domain_query": query_by_language,
        "semantic_locator_query": semantic_by_language,
        "provider_role": "locator_only",
        "provider_date_authority": False,
        "evidence_promotion_allowed": False,
        "writer_citable": False,
        "identical_retry_allowed": False,
    }
    digest = canonical_digest(payload)
    return {
        **payload,
        "intent_id": f"residual_search_intent::{case_key}::{group['intent_key']}::{digest[:16]}",
        "intent_digest": digest,
    }


def _deferred_gap_disposition(gap: Mapping[str, Any]) -> dict[str, Any]:
    slot_id = str(gap.get("slot_id") or "")
    facet_id = str(gap.get("facet_id") or "")
    gap_code = str(gap.get("gap_code") or "")
    if slot_id == "capital_allocation_and_valuation":
        reason = "local_market_pit_or_numeric_program_owned"
    elif facet_id in {
        "observable_invalidation_threshold",
        "observable_quarterly_threshold",
        "monitoring_metric_and_timing",
    }:
        reason = "s3_analysis_method_and_user_risk_preference_owned"
    elif gap_code == "formula_input_missing":
        reason = "numeric_program_after_authoritative_inputs_owned"
    elif gap_code in {"relationship_allocation_unproven", "relationship_attribution_unproven"}:
        reason = "low_public_obtainability_preserve_company_specific_boundary"
    elif gap_code in {"commercial_data_gap", "metric_not_disclosed"}:
        reason = "lower_priority_or_low_public_obtainability_under_case_budget"
    else:
        reason = "deferred_by_two_intent_per_case_budget"
    return {
        "gap_id": str(gap["gap_id"]),
        "case_key": str(gap["case_key"]),
        "slot_id": slot_id,
        "facet_id": facet_id,
        "gap_code": gap_code,
        "disposition": "deferred_typed_gap_not_searched_this_attempt",
        "defer_reason": reason,
        "evidence_state": "typed_gap",
    }


__all__ = [
    "CASES",
    "CONTRACT_REF",
    "PLAN_SCHEMA",
    "POLICY_SCHEMA",
    "RUN_SCOPE",
    "ResidualGapExternalSupplementError",
    "canonical_digest",
    "compile_residual_gap_external_priority_plan",
    "file_sha256",
    "load_bound_local_evidence_packs",
    "load_residual_gap_external_supplement_policy",
    "validate_residual_gap_external_priority_plan",
]
