from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_internal_candidate_ceiling import canonical_observation_digest


RUN_SCOPE = "S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"
POLICY_SCHEMA = "fin_ia_0_1_3_s1_internal_qrels_successor_policy_v1_1"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_internal_qrels_review_packet_v1_1"
POLICY_SCHEMA_V1_2 = "fin_ia_0_1_3_s1_internal_qrels_successor_policy_v1_2"
RESULT_SCHEMA_V1_2 = "fin_ia_0_1_3_s1_internal_qrels_review_packet_v1_2"
_POLICY_RESULT_SCHEMAS = {
    POLICY_SCHEMA: RESULT_SCHEMA,
    POLICY_SCHEMA_V1_2: RESULT_SCHEMA_V1_2,
}


class S1InternalQrelsSuccessorError(RuntimeError):
    pass


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise S1InternalQrelsSuccessorError("internal_qrels_successor_object_required")
    return value


def _canonical_digest_valid(value: Mapping[str, Any], field: str) -> bool:
    body = dict(value)
    supplied = str(body.pop(field, ""))
    return bool(supplied) and supplied == canonical_digest(body)


def load_internal_qrels_successor_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    expected_result_schema = _POLICY_RESULT_SCHEMAS.get(
        str(policy.get("schema_version") or "")
    )
    if (
        expected_result_schema is None
        or policy.get("result_schema") not in (None, expected_result_schema)
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile")
        != "sha256_utf8_lf_normalized_v1"
    ):
        raise S1InternalQrelsSuccessorError(
            "internal_qrels_successor_policy_identity_invalid"
        )
    stems = ["candidate_observation", "previous_review", "benchmark_evidence_pack"]
    if policy.get("immutable_inputs", {}).get("supplemental_asset_manifest_ref"):
        stems.append("supplemental_asset_manifest")
    for stem in stems:
        ref = str(policy.get("immutable_inputs", {}).get(f"{stem}_ref") or "")
        supplied = str(
            policy.get("immutable_inputs", {}).get(f"{stem}_sha256") or ""
        )
        target = root / ref
        if not ref or not target.is_file() or _normalized_sha256(target) != supplied:
            raise S1InternalQrelsSuccessorError(
                f"internal_qrels_successor_binding_invalid:{stem}"
            )
    hard = dict(policy.get("hard_boundaries") or {})
    if (
        hard.get("qrels_loaded_after_candidate_generation") is not True
        or hard.get("target_or_candidate_identity_may_enter_query") is not False
        or hard.get("candidate_may_be_promoted_to_evidence") is not False
        or hard.get("BGE_fusion_rerank_admitted") is not False
        or any(
            int(hard.get(name, -1)) != 0
            for name in (
                "network",
                "provider",
                "model",
                "embedding",
                "rerank",
                "evidence_promotion",
            )
        )
    ):
        raise S1InternalQrelsSuccessorError(
            "internal_qrels_successor_boundary_invalid"
        )
    overrides = list(policy.get("adjudication_overrides") or [])
    if not overrides:
        raise S1InternalQrelsSuccessorError(
            "internal_qrels_successor_override_required"
        )
    keys = [
        (
            str(item.get("case_key") or ""),
            str(item.get("evidence_slot_id") or ""),
            str(item.get("evidence_owner_ticker") or ""),
        )
        for item in overrides
    ]
    if len(keys) != len(set(keys)) or any(not all(key) for key in keys):
        raise S1InternalQrelsSuccessorError(
            "internal_qrels_successor_override_identity_invalid"
        )
    return policy


def load_bound_internal_qrels_successor_inputs(
    policy: Mapping[str, Any], *, repo_root: str | Path
) -> dict[str, dict[str, Any]]:
    root = Path(repo_root).resolve()
    refs = policy["immutable_inputs"]
    stems = [
        "candidate_observation",
        "previous_review",
        "benchmark_evidence_pack",
    ]
    if refs.get("supplemental_asset_manifest_ref"):
        stems.append("supplemental_asset_manifest")
    inputs = {
        stem: _read_json(root / str(refs[f"{stem}_ref"]))
        for stem in stems
    }
    observation = inputs["candidate_observation"]
    if observation.get("result_digest") != canonical_observation_digest(observation):
        raise S1InternalQrelsSuccessorError(
            "internal_qrels_successor_observation_digest_invalid"
        )
    if not _canonical_digest_valid(inputs["previous_review"], "review_digest"):
        raise S1InternalQrelsSuccessorError(
            "internal_qrels_successor_previous_review_digest_invalid"
        )
    if "supplemental_asset_manifest" in inputs:
        from sec_agent.s1_internal_supplemental_assets import (
            load_validated_supplemental_asset_manifest,
        )

        inputs["supplemental_asset_manifest"] = (
            load_validated_supplemental_asset_manifest(
                root / str(refs["supplemental_asset_manifest_ref"]),
                repo_root=root,
            )
        )
    return inputs


def _validate_selected_source_equivalence(
    *,
    selected: Mapping[str, Any],
    expected_refs: list[str],
    expected_urls: set[str],
    override: Mapping[str, Any],
    inputs: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str]:
    selected_url = str(selected.get("source_url") or "")
    accepted_ref = str(override.get("accepted_source_ref") or "")
    equivalence_mode = str(override.get("source_equivalence_mode") or "")
    if selected_url in expected_urls:
        if accepted_ref and accepted_ref not in expected_refs:
            raise S1InternalQrelsSuccessorError(
                "internal_qrels_successor_accepted_source_ref_invalid"
            )
        return accepted_ref, equivalence_mode or "exact_canonical_url"
    manifest = inputs.get("supplemental_asset_manifest")
    if not manifest or accepted_ref not in expected_refs:
        raise S1InternalQrelsSuccessorError(
            "internal_qrels_successor_source_url_mismatch"
        )
    matches = [
        item
        for item in manifest.get("source_bindings") or []
        if accepted_ref in (item.get("accepted_source_refs") or [])
        and str(item.get("selected_url") or "") == selected_url
        and str(item.get("equivalence_mode") or "") == equivalence_mode
        and str(item.get("ticker") or "") == str(selected.get("ticker") or "")
        and str(item.get("filing_date") or "")
        == str(selected.get("published_at") or "")
        and str(item.get("accession_number") or "")
        == str(selected.get("source_accession_number") or "")
    ]
    if len(matches) != 1 or equivalence_mode not in {
        "official_sec_same_event_semantic_alternative"
    }:
        raise S1InternalQrelsSuccessorError(
            "internal_qrels_successor_semantic_source_equivalence_invalid"
        )
    return accepted_ref, equivalence_mode


def _candidate_digest_valid(candidate: Mapping[str, Any]) -> bool:
    body = dict(candidate)
    candidate_id = str(body.pop("candidate_id", ""))
    supplied = str(body.pop("candidate_digest", ""))
    expected = canonical_digest(body)
    return supplied == expected and candidate_id == f"internal_candidate_{expected[:24]}"


def _route_candidates_by_bundle(
    observation: Mapping[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, int]]]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, dict[str, int]] = {}
    for terminal in observation.get("route_terminals") or []:
        bundle_id = str(terminal.get("bundle_id") or "")
        route_id = str(terminal.get("route_id") or "")
        local = [dict(item) for item in terminal.get("candidates") or []]
        if any(not _candidate_digest_valid(item) for item in local):
            raise S1InternalQrelsSuccessorError(
                f"internal_qrels_successor_candidate_digest_invalid:{bundle_id}:{route_id}"
            )
        candidates.setdefault(bundle_id, []).extend(local)
        counts.setdefault(bundle_id, {})[route_id] = int(
            terminal.get("candidate_count") or 0
        )
    return candidates, counts


def _find_candidate(
    candidates: list[dict[str, Any]], *, route_id: str, source_key: str
) -> dict[str, Any]:
    matches = [
        item
        for item in candidates
        if str(item.get("route_id") or "") == route_id
        and str(item.get("source_key") or "") == source_key
    ]
    if len(matches) != 1:
        raise S1InternalQrelsSuccessorError(
            f"internal_qrels_successor_selected_candidate_missing:{route_id}:{source_key}"
        )
    return matches[0]


def build_internal_qrels_successor_packet(
    *, policy: Mapping[str, Any], inputs: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    observation = inputs["candidate_observation"]
    previous = inputs["previous_review"]
    evidence_pack = inputs["benchmark_evidence_pack"]
    candidates_by_bundle, counts_by_bundle = _route_candidates_by_bundle(observation)
    sources = {
        str(item.get("source_id") or ""): dict(item)
        for item in evidence_pack.get("source_registry") or []
    }
    overrides = {
        (
            str(item["case_key"]),
            str(item["evidence_slot_id"]),
            str(item["evidence_owner_ticker"]),
        ): dict(item)
        for item in policy["adjudication_overrides"]
    }
    threshold = int(policy["review_contract"]["strict_target_in_pool_threshold"])
    rows: list[dict[str, Any]] = []
    applied: set[tuple[str, str, str]] = set()
    for old_row in previous.get("qrels") or []:
        row = dict(old_row)
        row.pop("qrel_digest", None)
        selected_old = dict(row.get("selected_candidate") or {})
        key = (
            str(row.get("case_key") or ""),
            str(row.get("evidence_slot_id") or ""),
            str(row.get("evidence_owner_ticker") or ""),
        )
        bundle_id = str(row.get("bundle_id") or "")
        current_candidates = candidates_by_bundle.get(bundle_id, [])
        row["route_candidate_counts"] = counts_by_bundle.get(bundle_id, {})
        override = overrides.get(key)
        if override:
            applied.add(key)
            selected = _find_candidate(
                current_candidates,
                route_id=str(override["selected_route_id"]),
                source_key=str(override["selected_source_key"]),
            )
            relevance = int(override["proposed_relevance"])
            if relevance < threshold:
                raise S1InternalQrelsSuccessorError(
                    f"internal_qrels_successor_relevance_below_threshold:{'|'.join(key)}"
                )
            expected_refs = [str(item) for item in row.get("expected_source_refs") or []]
            expected_urls = {
                str(sources[item].get("url") or "")
                for item in expected_refs
                if item in sources
            }
            try:
                accepted_ref, equivalence_mode = _validate_selected_source_equivalence(
                    selected=selected,
                    expected_refs=expected_refs,
                    expected_urls=expected_urls,
                    override=override,
                    inputs=inputs,
                )
            except S1InternalQrelsSuccessorError as exc:
                raise S1InternalQrelsSuccessorError(
                    f"{exc}:{'|'.join(key)}"
                ) from exc
            if (
                not str(selected.get("published_at") or "")
                or str(selected.get("published_at")) > str(row.get("as_of_date") or "")
                or str(selected.get("ticker") or "") != key[2]
                or selected.get("candidate_state") != "candidate_only_not_evidence"
                or selected.get("strict_identity_filter_applied") is not True
                or selected.get("strict_period_filter_applied") is not True
            ):
                raise S1InternalQrelsSuccessorError(
                    f"internal_qrels_successor_selected_candidate_scope_invalid:{'|'.join(key)}"
                )
            row.update(
                {
                    "selected_candidate": selected,
                    "proposed_state": "strict_current_target_in_pool",
                    "strict_current_target_in_pool": True,
                    "proposed_relevance": relevance,
                    "gap_class": "",
                    "curator_rationale": str(override["curator_rationale"]),
                    "accepted_source_ref": accepted_ref,
                    "source_equivalence_mode": equivalence_mode,
                    "supersedes_qrel_digest": str(old_row["qrel_digest"]),
                }
            )
        elif selected_old:
            selected = _find_candidate(
                current_candidates,
                route_id=str(selected_old["route_id"]),
                source_key=str(selected_old["source_key"]),
            )
            row["selected_candidate"] = selected
            row["supersedes_qrel_digest"] = str(old_row["qrel_digest"])
        else:
            row["selected_candidate"] = None
            row["supersedes_qrel_digest"] = str(old_row["qrel_digest"])
        row["review_state"] = "agent_curated_pending_owner_review"
        row["qrel_digest"] = canonical_digest(row)
        rows.append(row)
    if applied != set(overrides):
        missing = sorted("|".join(item) for item in set(overrides) - applied)
        raise S1InternalQrelsSuccessorError(
            "internal_qrels_successor_override_target_missing:" + ",".join(missing)
        )
    target_count = len(rows)
    present = sum(bool(row["strict_current_target_in_pool"]) for row in rows)
    recall = present / target_count if target_count else 0.0
    gap_counts = Counter(row["gap_class"] for row in rows if row["gap_class"])
    exact_candidates = sum(
        int(row["route_candidate_counts"].get("internal_sql_exact") or 0)
        for row in rows
    )
    required_recall = float(
        policy["review_contract"]["candidate_ceiling_required_recall"]
    )
    separate_numeric_sql = bool(
        policy["review_contract"].get("numeric_sql_uses_separate_qrels_suite")
    )
    if separate_numeric_sql:
        reason = (
            f"Candidate generation reaches {present}/{target_count}. The remaining "
            "current research target must be repaired before ranking admission; "
            "exact SQL is evaluated by a separate numeric-fact qrels suite."
        )
    else:
        reason = (
            f"The newer local object index raises strict current target-in-pool "
            f"to {present}/{target_count}, but missing current official documents "
            "and zero current exact-SQL coverage still block ranking admission."
        )
    body = {
        "schema_version": str(policy.get("result_schema") or RESULT_SCHEMA),
        "contract_ref": str(policy["contract_ref"]),
        "run_scope": RUN_SCOPE,
        "status": "agent_curated_candidate_ceiling_failed_owner_review_pending",
        "review_state": "agent_curated_pending_owner_review",
        "candidate_observation_digest": str(observation["result_digest"]),
        "supersedes_review_digest": str(previous["review_digest"]),
        "target_count": target_count,
        "strict_current_target_in_pool_count": present,
        "strict_current_target_absent_count": target_count - present,
        "strict_current_target_recall": round(recall, 8),
        "required_recall": required_recall,
        "all_target_exact_sql_candidate_count": exact_candidates,
        "gap_counts": dict(sorted(gap_counts.items())),
        "qrels": rows,
        "gate_decision": {
            "agent_curated_candidate_ceiling_pass": recall >= required_recall,
            "owner_review_complete": False,
            "candidate_ceiling_proven": False,
            "BGE_fusion_rerank_admitted": False,
            "reason": reason,
        },
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "known_boundary": (
            "This successor rebinds the provisional qrels proposal to a newer "
            "candidate observation and applies only explicit post-generation "
            "adjudication deltas. It is not owner review, ranking, Evidence or release."
        ),
    }
    return {**body, "review_digest": canonical_digest(body)}


__all__ = [
    "POLICY_SCHEMA",
    "POLICY_SCHEMA_V1_2",
    "RESULT_SCHEMA",
    "RESULT_SCHEMA_V1_2",
    "RUN_SCOPE",
    "S1InternalQrelsSuccessorError",
    "build_internal_qrels_successor_packet",
    "load_bound_internal_qrels_successor_inputs",
    "load_internal_qrels_successor_policy",
]
