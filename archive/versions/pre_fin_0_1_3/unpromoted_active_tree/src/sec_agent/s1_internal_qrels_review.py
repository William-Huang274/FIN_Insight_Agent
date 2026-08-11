from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_internal_candidate_ceiling import canonical_observation_digest


RUN_SCOPE = "S1_INTERNAL_CANDIDATE_CEILING_AND_QRELS_GATE"
POLICY_SCHEMA = "fin_ia_0_1_3_s1_internal_qrels_review_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_internal_qrels_review_packet_v1_0"


class S1InternalQrelsReviewError(RuntimeError):
    pass


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise S1InternalQrelsReviewError("internal_qrels_json_object_required")
    return value


def load_internal_qrels_review_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile")
        != "sha256_utf8_lf_normalized_v1"
    ):
        raise S1InternalQrelsReviewError("internal_qrels_policy_identity_invalid")
    for stem in (
        "candidate_observation",
        "integration_proof",
        "target_manifest",
        "benchmark_evidence_pack",
    ):
        ref = str(policy.get("immutable_inputs", {}).get(f"{stem}_ref") or "")
        supplied = str(
            policy.get("immutable_inputs", {}).get(f"{stem}_sha256") or ""
        )
        target = root / ref
        if not target.is_file() or _normalized_sha256(target) != supplied:
            raise S1InternalQrelsReviewError(
                f"internal_qrels_policy_binding_invalid:{stem}"
            )
    hard = policy.get("hard_boundaries") or {}
    if (
        hard.get("qrels_loaded_after_candidate_generation") is not True
        or hard.get("target_or_candidate_identity_may_enter_query") is not False
        or hard.get("graph_without_period_authority_may_satisfy_strict_current_target")
        is not False
        or hard.get("stale_period_may_satisfy_strict_current_target") is not False
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
        raise S1InternalQrelsReviewError("internal_qrels_policy_boundary_invalid")
    return policy


def load_bound_internal_qrels_inputs(
    policy: Mapping[str, Any], *, repo_root: str | Path
) -> dict[str, dict[str, Any]]:
    root = Path(repo_root).resolve()
    refs = policy["immutable_inputs"]
    values = {
        stem: _read_json(root / str(refs[f"{stem}_ref"]))
        for stem in (
            "candidate_observation",
            "integration_proof",
            "target_manifest",
            "benchmark_evidence_pack",
        )
    }
    observation = values["candidate_observation"]
    if observation.get("result_digest") != canonical_observation_digest(observation):
        raise S1InternalQrelsReviewError(
            "internal_qrels_candidate_observation_digest_invalid"
        )
    proof = dict(values["integration_proof"])
    supplied = str(proof.pop("proof_digest", ""))
    if supplied != canonical_digest(proof):
        raise S1InternalQrelsReviewError(
            "internal_qrels_integration_proof_digest_invalid"
        )
    return values


def _candidate_digest_valid(candidate: Mapping[str, Any]) -> bool:
    body = dict(candidate)
    candidate_id = str(body.pop("candidate_id", ""))
    supplied = str(body.pop("candidate_digest", ""))
    expected = canonical_digest(body)
    return (
        supplied == expected
        and candidate_id == f"internal_candidate_{expected[:24]}"
    )


def build_internal_qrels_review_packet(
    *, policy: Mapping[str, Any], inputs: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    observation = inputs["candidate_observation"]
    proof = inputs["integration_proof"]
    manifest = inputs["target_manifest"]
    evidence_pack = inputs["benchmark_evidence_pack"]
    contract = policy["review_contract"]
    targets = [dict(item) for item in manifest.get("targets") or []]
    expected_count = int(contract["target_count"])
    if len(targets) != expected_count:
        raise S1InternalQrelsReviewError("internal_qrels_target_count_invalid")
    target_keys = [
        (
            str(item.get("case_key") or ""),
            str(item.get("evidence_slot_id") or ""),
            str(item.get("evidence_owner_ticker") or ""),
        )
        for item in targets
    ]
    if len(set(target_keys)) != expected_count:
        raise S1InternalQrelsReviewError("internal_qrels_target_identity_invalid")

    source_ids = {
        str(item.get("source_id") or "")
        for item in evidence_pack.get("source_registry") or []
    }
    bundles = {
        (
            str(item.get("case_key") or ""),
            str(item.get("evidence_slot_id") or ""),
            str(item.get("evidence_owner_ticker") or ""),
        ): dict(item)
        for item in proof.get("bundles") or []
    }
    terminals_by_bundle: dict[str, list[dict[str, Any]]] = {}
    for terminal in observation.get("route_terminals") or []:
        terminals_by_bundle.setdefault(str(terminal["bundle_id"]), []).append(
            dict(terminal)
        )

    rows: list[dict[str, Any]] = []
    for target, key in zip(targets, target_keys):
        bundle = bundles.get(key)
        if bundle is None:
            raise S1InternalQrelsReviewError(
                f"internal_qrels_bundle_missing:{'|'.join(key)}"
            )
        refs = [str(item) for item in target.get("expected_source_refs") or []]
        if not refs or any(item not in source_ids for item in refs):
            raise S1InternalQrelsReviewError(
                f"internal_qrels_expected_source_ref_invalid:{'|'.join(key)}"
            )
        terminals = terminals_by_bundle.get(str(bundle["bundle_id"]), [])
        candidates = [
            dict(candidate)
            for terminal in terminals
            for candidate in terminal.get("candidates") or []
        ]
        if any(not _candidate_digest_valid(candidate) for candidate in candidates):
            raise S1InternalQrelsReviewError(
                f"internal_qrels_candidate_digest_invalid:{'|'.join(key)}"
            )
        state = str(target.get("proposed_state") or "")
        selected: dict[str, Any] | None = None
        if state == "strict_current_target_in_pool":
            route_id = str(target.get("selected_route_id") or "")
            source_key = str(target.get("selected_source_key") or "")
            matches = [
                candidate
                for candidate in candidates
                if candidate.get("route_id") == route_id
                and candidate.get("source_key") == source_key
            ]
            if len(matches) != 1:
                raise S1InternalQrelsReviewError(
                    f"internal_qrels_selected_candidate_missing:{'|'.join(key)}"
                )
            selected = matches[0]
            published_at = str(selected.get("published_at") or "")
            as_of = str(bundle.get("as_of_date") or "")
            relevance = int(target.get("proposed_relevance") or 0)
            if (
                relevance < int(contract["strict_target_in_pool_threshold"])
                or not published_at
                or published_at > as_of
                or selected.get("ticker") != key[2]
                or selected.get("candidate_state") != "candidate_only_not_evidence"
                or selected.get("strict_identity_filter_applied") is not True
                or selected.get("strict_period_filter_applied") is not True
            ):
                raise S1InternalQrelsReviewError(
                    f"internal_qrels_selected_candidate_scope_invalid:{'|'.join(key)}"
                )
        elif state == "strict_current_target_absent":
            if target.get("selected_source_key") or not target.get("gap_class"):
                raise S1InternalQrelsReviewError(
                    f"internal_qrels_absent_target_shape_invalid:{'|'.join(key)}"
                )
        else:
            raise S1InternalQrelsReviewError(
                f"internal_qrels_target_state_invalid:{'|'.join(key)}"
            )

        route_candidate_counts = {
            str(terminal["route_id"]): int(terminal.get("candidate_count") or 0)
            for terminal in terminals
        }
        row = {
            "case_key": key[0],
            "evidence_slot_id": key[1],
            "evidence_owner_ticker": key[2],
            "bundle_id": str(bundle["bundle_id"]),
            "reporting_fiscal_years": list(
                bundle.get("reporting_fiscal_years")
                or bundle.get("fiscal_years")
                or []
            ),
            "index_filing_calendar_years": list(
                bundle.get("index_filing_calendar_years") or []
            ),
            "as_of_date": str(bundle["as_of_date"]),
            "expected_source_refs": refs,
            "target_facets": list(target.get("target_facets") or []),
            "proposed_state": state,
            "strict_current_target_in_pool": selected is not None,
            "proposed_relevance": int(target.get("proposed_relevance") or 0),
            "selected_candidate": selected,
            "gap_class": str(target.get("gap_class") or ""),
            "curator_rationale": str(target.get("curator_rationale") or ""),
            "route_candidate_counts": route_candidate_counts,
            "review_state": "agent_curated_pending_owner_review",
        }
        row["qrel_digest"] = canonical_digest(row)
        rows.append(row)

    present = sum(bool(row["strict_current_target_in_pool"]) for row in rows)
    recall = present / expected_count
    gap_counts = Counter(row["gap_class"] for row in rows if row["gap_class"])
    exact_candidates = sum(
        int(row["route_candidate_counts"].get("internal_sql_exact") or 0)
        for row in rows
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": str(policy["contract_ref"]),
        "run_scope": RUN_SCOPE,
        "status": "agent_curated_candidate_ceiling_failed_owner_review_pending",
        "review_state": "agent_curated_pending_owner_review",
        "candidate_observation_digest": str(observation["result_digest"]),
        "integration_proof_digest": str(inputs["integration_proof"]["proof_digest"]),
        "target_count": expected_count,
        "strict_current_target_in_pool_count": present,
        "strict_current_target_absent_count": expected_count - present,
        "strict_current_target_recall": round(recall, 8),
        "required_recall": float(contract["candidate_ceiling_required_recall"]),
        "all_target_exact_sql_candidate_count": exact_candidates,
        "gap_counts": dict(sorted(gap_counts.items())),
        "qrels": rows,
        "gate_decision": {
            "agent_curated_candidate_ceiling_pass": (
                recall >= float(contract["candidate_ceiling_required_recall"])
            ),
            "owner_review_complete": False,
            "candidate_ceiling_proven": False,
            "BGE_fusion_rerank_admitted": False,
            "reason": (
                "Current strict target recall is below 1.0 and exact SQL has no "
                "current candidate. Corpus/index freshness and evidence-owner "
                "coverage must be repaired before ranking evaluation."
            ),
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
            "These labels are an agent-curated review proposal applied only after "
            "candidate generation. They are not owner-reviewed qrels, Evidence, a "
            "ranking result, downstream utilization proof or release acceptance."
        ),
    }
    return {**body, "review_digest": canonical_digest(body)}


__all__ = [
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "S1InternalQrelsReviewError",
    "build_internal_qrels_review_packet",
    "load_bound_internal_qrels_inputs",
    "load_internal_qrels_review_policy",
]
