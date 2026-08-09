from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.s1_internal_candidate_ceiling import canonical_observation_digest


RUN_SCOPE = "S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"
POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_qrels_content_requalification_policy_v1_0"
)
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_qrels_content_requalification_packet_v1_0"
)


class S1InternalQrelsContentRequalificationError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S1InternalQrelsContentRequalificationError(code)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "qrels_content_json_object_required")
    return value


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _canonical_digest_valid(value: Mapping[str, Any], field: str) -> bool:
    body = dict(value)
    supplied = str(body.pop(field, ""))
    return bool(supplied) and supplied == canonical_digest(body)


def _candidate_digest_valid(candidate: Mapping[str, Any]) -> bool:
    body = dict(candidate)
    candidate_id = str(body.pop("candidate_id", ""))
    supplied = str(body.pop("candidate_digest", ""))
    expected = canonical_digest(body)
    return supplied == expected and candidate_id == f"internal_candidate_{expected[:24]}"


def _row_key(value: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(value.get("case_key") or ""),
        str(value.get("evidence_slot_id") or ""),
        str(value.get("evidence_owner_ticker") or ""),
    )


def load_qrels_content_requalification_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("run_scope") == RUN_SCOPE
        and policy.get("binding_hash_profile") == "sha256_utf8_lf_normalized_v1",
        "qrels_content_policy_identity_invalid",
    )
    for stem in (
        "source_qrels",
        "owner_acceptance",
        "candidate_observation",
        "prior_semantic_audit",
    ):
        ref = str(policy.get("immutable_inputs", {}).get(f"{stem}_ref") or "")
        supplied = str(
            policy.get("immutable_inputs", {}).get(f"{stem}_sha256") or ""
        )
        target = root / ref
        _require(
            bool(ref) and target.is_file() and _normalized_sha256(target) == supplied,
            f"qrels_content_policy_binding_invalid:{stem}",
        )

    hard = dict(policy.get("hard_boundaries") or {})
    _require(
        hard.get("source_qrels_v1_3_immutable") is True
        and hard.get("qrels_loaded_after_candidate_generation") is True
        and hard.get("owner_acceptance_does_not_equal_evidence_acceptance") is True
        and hard.get("candidate_may_be_promoted_to_evidence") is False
        and hard.get("ranking_or_index_build_admitted") is False
        and all(
            int(hard.get(name, -1)) == 0
            for name in (
                "network",
                "provider",
                "model",
                "embedding",
                "vector_search",
                "rerank",
                "evidence_promotion",
            )
        ),
        "qrels_content_policy_boundary_invalid",
    )

    profiles = dict(policy.get("content_profiles") or {})
    assignments = list(policy.get("assignments") or [])
    contract = dict(policy.get("review_contract") or {})
    keys = [_row_key(item) for item in assignments]
    _require(
        len(assignments) == int(contract.get("expected_row_count") or 0)
        and len(keys) == len(set(keys))
        and all(all(part for part in key) for key in keys),
        "qrels_content_assignment_identity_invalid",
    )
    _require(
        len(profiles) == int(contract.get("expected_profile_count") or 0)
        and all(str(item.get("profile_id") or "") in profiles for item in assignments),
        "qrels_content_profile_assignment_invalid",
    )
    allowed_dispositions = {"retain_current_candidate", "replace_with_frozen_candidate"}
    for profile_id, profile in profiles.items():
        disposition = str(profile.get("ranking_label_disposition") or "")
        covered = [str(item) for item in profile.get("covered_facets") or []]
        uncovered = [str(item) for item in profile.get("uncovered_facets") or []]
        _require(
            bool(profile_id)
            and disposition in allowed_dispositions
            and bool(covered)
            and len(covered) == len(set(covered))
            and len(uncovered) == len(set(uncovered))
            and not set(covered).intersection(uncovered)
            and bool(str(profile.get("business_reason_zh") or "")),
            f"qrels_content_profile_shape_invalid:{profile_id}",
        )
        replacement_fields = (
            str(profile.get("recommended_route_id") or ""),
            str(profile.get("recommended_source_key") or ""),
            str(profile.get("replacement_reason_zh") or ""),
        )
        _require(
            (disposition == "replace_with_frozen_candidate" and all(replacement_fields))
            or (disposition == "retain_current_candidate" and not any(replacement_fields)),
            f"qrels_content_replacement_shape_invalid:{profile_id}",
        )
    return policy


def load_bound_qrels_content_requalification_inputs(
    policy: Mapping[str, Any], *, repo_root: str | Path
) -> dict[str, dict[str, Any]]:
    root = Path(repo_root).resolve()
    refs = policy["immutable_inputs"]
    values = {
        stem: _read_json(root / str(refs[f"{stem}_ref"]))
        for stem in (
            "source_qrels",
            "owner_acceptance",
            "candidate_observation",
            "prior_semantic_audit",
        )
    }
    _require(
        _canonical_digest_valid(values["source_qrels"], "review_digest"),
        "qrels_content_source_qrels_digest_invalid",
    )
    _require(
        _canonical_digest_valid(values["owner_acceptance"], "decision_digest"),
        "qrels_content_owner_acceptance_digest_invalid",
    )
    _require(
        values["candidate_observation"].get("result_digest")
        == canonical_observation_digest(values["candidate_observation"]),
        "qrels_content_candidate_observation_digest_invalid",
    )
    _require(
        _canonical_digest_valid(values["prior_semantic_audit"], "result_digest"),
        "qrels_content_prior_semantic_audit_digest_invalid",
    )

    qrels = values["source_qrels"]
    owner = values["owner_acceptance"]
    accepted = list(owner.get("source_qrels", {}).get("accepted_qrel_digests") or [])
    current = [str(item.get("qrel_digest") or "") for item in qrels.get("qrels") or []]
    _require(
        owner.get("owner_decision", {}).get("ranking_entry_eligible") is True
        and owner.get("source_qrels", {}).get("review_digest")
        == qrels.get("review_digest")
        and accepted == current,
        "qrels_content_owner_acceptance_binding_invalid",
    )
    return values


def _candidates_by_bundle(
    observation: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for terminal in observation.get("route_terminals") or []:
        bundle_id = str(terminal.get("bundle_id") or "")
        candidates = [dict(item) for item in terminal.get("candidates") or []]
        _require(
            bool(bundle_id) and all(_candidate_digest_valid(item) for item in candidates),
            f"qrels_content_candidate_digest_invalid:{bundle_id}",
        )
        result.setdefault(bundle_id, []).extend(candidates)
    return result


def _find_replacement(
    *,
    candidates: list[dict[str, Any]],
    route_id: str,
    source_key: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    matches = [
        item
        for item in candidates
        if str(item.get("route_id") or "") == route_id
        and str(item.get("source_key") or "") == source_key
    ]
    _require(
        len(matches) == 1,
        f"qrels_content_replacement_not_in_frozen_pool:{'|'.join(_row_key(row))}",
    )
    replacement = matches[0]
    _require(
        replacement.get("candidate_state") == "candidate_only_not_evidence"
        and replacement.get("strict_identity_filter_applied") is True
        and replacement.get("strict_period_filter_applied") is True
        and str(replacement.get("ticker") or "")
        == str(row.get("evidence_owner_ticker") or "")
        and bool(str(replacement.get("published_at") or ""))
        and str(replacement.get("published_at")) <= str(row.get("as_of_date") or ""),
        f"qrels_content_replacement_scope_invalid:{'|'.join(_row_key(row))}",
    )
    source_key_value = str(replacement.get("source_key") or "")
    lineage_method = str(replacement.get("lineage_resolution_method") or "")
    source_url = str(replacement.get("source_url") or "")
    _require(
        source_url.startswith(("https://", "http://"))
        and bool(str(replacement.get("source_accession_number") or ""))
        and bool(str(replacement.get("lineage_manifest_ref") or ""))
        and bool(lineage_method)
        and (
            not source_key_value.startswith("8K_EARNINGS::")
            or lineage_method == "exact_accession_exhibit"
        ),
        f"qrels_content_replacement_lineage_invalid:{'|'.join(_row_key(row))}",
    )
    return replacement


def build_qrels_content_requalification_packet(
    *,
    policy: Mapping[str, Any],
    inputs: Mapping[str, Mapping[str, Any]],
    project_os_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    qrels = inputs["source_qrels"]
    owner = inputs["owner_acceptance"]
    observation = inputs["candidate_observation"]
    profiles = dict(policy["content_profiles"])
    assignments = {_row_key(item): dict(item) for item in policy["assignments"]}
    rows = [dict(item) for item in qrels.get("qrels") or []]
    qrel_keys = {_row_key(item) for item in rows}
    _require(
        qrel_keys == set(assignments),
        "qrels_content_assignment_set_mismatch",
    )
    candidate_pool = _candidates_by_bundle(observation)

    reviewed: list[dict[str, Any]] = []
    for row in rows:
        key = _row_key(row)
        assignment = assignments[key]
        profile_id = str(assignment["profile_id"])
        profile = dict(profiles[profile_id])
        target_facets = [str(item) for item in row.get("target_facets") or []]
        covered = [str(item) for item in profile.get("covered_facets") or []]
        uncovered = [str(item) for item in profile.get("uncovered_facets") or []]
        _require(
            set(covered).union(uncovered) == set(target_facets)
            and len(covered) + len(uncovered) == len(target_facets),
            f"qrels_content_facet_partition_invalid:{'|'.join(key)}",
        )
        current = dict(row.get("selected_candidate") or {})
        _require(
            bool(current) and _candidate_digest_valid(current),
            f"qrels_content_current_candidate_invalid:{'|'.join(key)}",
        )
        disposition = str(profile["ranking_label_disposition"])
        replacement: dict[str, Any] | None = None
        if disposition == "replace_with_frozen_candidate":
            replacement = _find_replacement(
                candidates=candidate_pool.get(str(row.get("bundle_id") or ""), []),
                route_id=str(profile["recommended_route_id"]),
                source_key=str(profile["recommended_source_key"]),
                row=row,
            )
            _require(
                replacement.get("candidate_id") != current.get("candidate_id"),
                f"qrels_content_replacement_equals_current:{'|'.join(key)}",
            )
        coverage_state = (
            "complete_slot_facet_coverage"
            if not uncovered
            else "material_partial_slot_coverage"
        )
        item: dict[str, Any] = {
            "case_key": key[0],
            "evidence_slot_id": key[1],
            "evidence_owner_ticker": key[2],
            "bundle_id": str(row.get("bundle_id") or ""),
            "source_qrel_digest": str(row.get("qrel_digest") or ""),
            "source_relevance_grade": int(row.get("proposed_relevance") or 0),
            "ranking_label_valid": True,
            "ranking_label_disposition": disposition,
            "content_profile_id": profile_id,
            "slot_coverage_state": coverage_state,
            "covered_facets": covered,
            "uncovered_facets": uncovered,
            "current_candidate": {
                "route_id": str(current.get("route_id") or ""),
                "route_rank": int(current.get("route_rank") or 0),
                "source_key": str(current.get("source_key") or ""),
                "candidate_id": str(current.get("candidate_id") or ""),
                "preview": str(current.get("preview") or ""),
            },
            "recommended_candidate": (
                {
                    "route_id": str(replacement.get("route_id") or ""),
                    "route_rank": int(replacement.get("route_rank") or 0),
                    "source_key": str(replacement.get("source_key") or ""),
                    "candidate_id": str(replacement.get("candidate_id") or ""),
                    "source_url": str(replacement.get("source_url") or ""),
                    "source_accession_number": str(
                        replacement.get("source_accession_number") or ""
                    ),
                    "lineage_resolution_method": str(
                        replacement.get("lineage_resolution_method") or ""
                    ),
                    "preview": str(replacement.get("preview") or ""),
                }
                if replacement
                else None
            ),
            "content_precision_risk": str(profile["content_precision_risk"]),
            "business_reason_zh": str(profile["business_reason_zh"]),
            "replacement_reason_zh": str(profile.get("replacement_reason_zh") or ""),
            "prior_finding_disposition": str(
                profile.get("prior_finding_disposition") or "not_applicable"
            ),
            "candidate_may_be_promoted_to_evidence": False,
            "owner_reconfirmation_required": replacement is not None,
        }
        item["content_review_digest"] = canonical_digest(item)
        reviewed.append(item)

    counts = Counter(item["ranking_label_disposition"] for item in reviewed)
    coverage = Counter(item["slot_coverage_state"] for item in reviewed)
    corrections = sum(
        item["prior_finding_disposition"]
        == "superseded_preview_only_defect_chunk_relevant_but_low_precision"
        for item in reviewed
    )
    contract = dict(policy["review_contract"])
    _require(
        len(reviewed) == int(contract["expected_row_count"])
        and counts["retain_current_candidate"] == int(contract["expected_retain_count"])
        and counts["replace_with_frozen_candidate"]
        == int(contract["expected_replacement_count"])
        and coverage["complete_slot_facet_coverage"]
        == int(contract["expected_complete_coverage_count"])
        and coverage["material_partial_slot_coverage"]
        == int(contract["expected_partial_coverage_count"])
        and corrections == int(contract["expected_prior_finding_correction_count"]),
        "qrels_content_expected_counts_invalid",
    )

    body: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": str(policy["contract_ref"]),
        "run_scope": RUN_SCOPE,
        "recorded_at": "2026-08-09",
        "status": "agent_curated_content_requalified_successor_owner_review_pending",
        "project_os_preflight": {
            "status": str(project_os_preflight.get("status") or ""),
            "run_scope": str(project_os_preflight.get("run_scope") or ""),
            "open_full_chain_blocker_count": int(
                project_os_preflight.get("open_full_chain_blocker_count") or 0
            ),
        },
        "source_qrels": {
            "ref": str(policy["immutable_inputs"]["source_qrels_ref"]),
            "review_digest": str(qrels["review_digest"]),
            "owner_decision_digest": str(owner["decision_digest"]),
            "preserved_immutable": True,
            "existing_r2_metrics_remain_valid_against_v1_3": True,
        },
        "content_requalification_summary": {
            "reviewed_row_count": len(reviewed),
            "ranking_label_valid_count": sum(item["ranking_label_valid"] for item in reviewed),
            "retain_current_candidate_count": counts["retain_current_candidate"],
            "replacement_proposal_count": counts["replace_with_frozen_candidate"],
            "complete_slot_facet_coverage_count": coverage[
                "complete_slot_facet_coverage"
            ],
            "material_partial_slot_coverage_count": coverage[
                "material_partial_slot_coverage"
            ],
            "typed_gap_count": 0,
            "prior_preview_only_finding_corrected_count": corrections,
        },
        "important_correction": {
            "prior_conclusion": (
                "Two NVIDIA rows were initially classified as qrel "
                "business-semantic defects from truncated previews."
            ),
            "full_text_finding": (
                "The full chunk does contain explicit third-party manufacturing, "
                "assembly, packaging and test reliance; it is relevant at grade 2 "
                "but front-loads contacts and safe-harbor boilerplate."
            ),
            "disposition": (
                "Retain historical qrels and R2 metrics; propose a cleaner frozen "
                "claim-object target whose URL is bound to SEC Exhibit 99.1 for the "
                "successor instead of returning a typed gap."
            ),
        },
        "row_reviews": reviewed,
        "successor_gate": {
            "successor_qrels_v1_4_materialization_admitted": False,
            "owner_reconfirmation_required": True,
            "owner_reconfirmation_row_count": counts["replace_with_frozen_candidate"],
            "unchanged_row_acceptance_preserved_count": counts["retain_current_candidate"],
            "replacement_scope": [
                {
                    "case_key": item["case_key"],
                    "evidence_slot_id": item["evidence_slot_id"],
                    "evidence_owner_ticker": item["evidence_owner_ticker"],
                    "recommended_source_key": item["recommended_candidate"][
                        "source_key"
                    ],
                }
                for item in reviewed
                if item["owner_reconfirmation_required"]
            ],
            "reason": (
                "Five candidate identities have cleaner, already frozen child-claim "
                "alternatives. Owner confirmation is required before qrels v1.4 or a "
                "new ranking attempt; the other thirteen identities remain accepted."
            ),
        },
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "vector_search": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "preserved_boundaries": {
            "candidate_promoted_to_evidence": False,
            "index_build_executed": False,
            "ranking_executed": False,
            "ranking_quality_improved": False,
            "current_quarter_exact_sql": "0_of_6_open",
            "external_official_required_slot_coverage": "4_of_12_open_release_blocker",
            "downstream_utilization_proven": False,
            "product_acceptance": False,
            "release": "not_qualified",
        },
        "known_boundary": str(policy["known_boundary"]),
        "implementation": {
            "module_ref": "src/sec_agent/s1_internal_qrels_content_requalification.py",
            "policy_ref": (
                "configs/runtime/fin_ia_0_1_3_s1_internal_qrels_"
                "content_requalification_policy_v1_0.json"
            ),
            "materializer_ref": (
                "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_"
                "qrels_content_requalification_v1_0.py"
            ),
        },
    }
    body["review_digest"] = canonical_digest(body)
    return body


def materialize_qrels_content_requalification_packet(
    policy: Mapping[str, Any], *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    preflight = run_project_os_preflight(root, run_scope=RUN_SCOPE)
    _require(
        preflight.get("status") == "pass",
        "qrels_content_project_os_preflight_failed",
    )
    inputs = load_bound_qrels_content_requalification_inputs(policy, repo_root=root)
    return build_qrels_content_requalification_packet(
        policy=policy,
        inputs=inputs,
        project_os_preflight=preflight,
    )


def validate_qrels_content_requalification_packet(
    value: Mapping[str, Any]
) -> dict[str, Any]:
    body = dict(value)
    supplied = str(body.pop("review_digest", ""))
    summary = dict(value.get("content_requalification_summary") or {})
    gate = dict(value.get("successor_gate") or {})
    calls = dict(value.get("observed_calls") or {})
    _require(
        value.get("schema_version") == RESULT_SCHEMA
        and value.get("status")
        == "agent_curated_content_requalified_successor_owner_review_pending"
        and supplied == canonical_digest(body)
        and summary.get("reviewed_row_count") == 18
        and summary.get("ranking_label_valid_count") == 18
        and summary.get("retain_current_candidate_count") == 13
        and summary.get("replacement_proposal_count") == 5
        and summary.get("complete_slot_facet_coverage_count") == 4
        and summary.get("material_partial_slot_coverage_count") == 14
        and summary.get("typed_gap_count") == 0
        and summary.get("prior_preview_only_finding_corrected_count") == 2
        and gate.get("successor_qrels_v1_4_materialization_admitted") is False
        and gate.get("owner_reconfirmation_required") is True
        and gate.get("owner_reconfirmation_row_count") == 5
        and gate.get("unchanged_row_acceptance_preserved_count") == 13
        and all(int(item) == 0 for item in calls.values())
        and value.get("preserved_boundaries", {}).get("candidate_promoted_to_evidence")
        is False,
        "qrels_content_requalification_packet_invalid",
    )
    return deepcopy(dict(value))


__all__ = [
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "S1InternalQrelsContentRequalificationError",
    "build_qrels_content_requalification_packet",
    "load_bound_qrels_content_requalification_inputs",
    "load_qrels_content_requalification_policy",
    "materialize_qrels_content_requalification_packet",
    "validate_qrels_content_requalification_packet",
]
