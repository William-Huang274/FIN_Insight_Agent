from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest


SCHEMA_VERSION = "fin_ia_0_1_3_s1_internal_qrels_owner_acceptance_v1_0"
QRELS_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s1_internal_qrels_review_packet_v1_3.json"
)
EXPECTED_QRELS_SHA256 = (
    "77d438d7c0ea280e5defcd3685f6a503d5b883cd8b85bb1f6e561b77254397eb"
)
EXPECTED_REVIEW_DIGEST = (
    "aca52d205984d0477c1c17186afa2a28d249655419be28b75cf825dbc18716aa"
)


class S1InternalQrelsOwnerAcceptanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S1InternalQrelsOwnerAcceptanceError(code)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "internal_qrels_owner_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validated_qrels(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    path = root / QRELS_REF
    _require(path.is_file(), "internal_qrels_owner_source_missing")
    _require(
        _sha256(path) == EXPECTED_QRELS_SHA256,
        "internal_qrels_owner_source_sha256_drift",
    )
    qrels = _read_json(path)
    body = dict(qrels)
    supplied = str(body.pop("review_digest", ""))
    _require(
        supplied == EXPECTED_REVIEW_DIGEST == canonical_digest(body),
        "internal_qrels_owner_review_digest_invalid",
    )
    rows = list(qrels.get("qrels") or [])
    _require(
        qrels.get("status")
        == "agent_curated_candidate_ceiling_pass_owner_review_pending"
        and qrels.get("review_state") == "agent_curated_pending_owner_review"
        and qrels.get("strict_current_target_in_pool_count") == 18
        and qrels.get("target_count") == 18
        and len(rows) == 18,
        "internal_qrels_owner_source_not_review_ready",
    )
    identities = {
        (
            str(row.get("case_key") or ""),
            str(row.get("evidence_slot_id") or ""),
            str(row.get("evidence_owner_ticker") or ""),
        )
        for row in rows
    }
    _require(
        len(identities) == 18
        and all(all(identity) for identity in identities)
        and all(
            row.get("review_state") == "agent_curated_pending_owner_review"
            and row.get("strict_current_target_in_pool") is True
            and (row.get("selected_candidate") or {}).get("candidate_state")
            == "candidate_only_not_evidence"
            for row in rows
        ),
        "internal_qrels_owner_row_contract_invalid",
    )
    return qrels


def materialize_internal_qrels_owner_acceptance(
    *, repo_root: str | Path
) -> dict[str, Any]:
    qrels = _validated_qrels(repo_root)
    rows = list(qrels["qrels"])
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "decision_id": "FIN-0.1.3-S1-INTERNAL-RESEARCH-QRELS-OWNER-ACCEPTANCE-R1",
        "recorded_at": "2026-08-09",
        "status": "owner_accepted_research_qrels_v1_3_ranking_entry_eligible",
        "authority": {
            "user_message": "继续",
            "user_message_interpreted_as": (
                "accept_the_presented_18_row_qrels_v1_3_and_continue_the_frozen_sequence"
            ),
            "assistant_scope_limitation_presented_before_execution": True,
            "owner_review_complete": True,
        },
        "source_qrels": {
            "ref": QRELS_REF,
            "sha256": EXPECTED_QRELS_SHA256,
            "review_digest": EXPECTED_REVIEW_DIGEST,
            "target_count": 18,
            "strict_current_target_in_pool_count": 18,
            "accepted_qrel_digests": [str(row["qrel_digest"]) for row in rows],
        },
        "owner_decision": {
            "decision": "accept_all_18_research_qrels_without_row_modification",
            "review_state": "owner_reviewed",
            "accepted_qrel_count": 18,
            "returned_qrel_count": 0,
            "ranking_entry_eligible": True,
        },
        "preserved_boundaries": {
            "selected_candidates_remain_candidate_only_not_evidence": True,
            "ranking_quality_accepted": False,
            "BGE_fusion_or_rerank_executed": False,
            "current_quarter_exact_sql": "0_of_6_open",
            "external_official_required_slot_coverage": "4_of_12_open_release_blocker",
            "downstream_utilization_proven": False,
            "product_acceptance": False,
            "release": "not_qualified",
            "production": "not_qualified",
        },
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "recommended_next": "S1_INTERNAL_BGE_FUSION_AND_RERANK_EVALUATION",
        "known_boundary": (
            "Owner acceptance applies only to the relevance labels and selected "
            "candidate identities in qrels v1.3. It does not accept ranking quality, "
            "promote Evidence, close current-quarter SQL freshness, close external "
            "coverage, accept the product, or qualify release."
        ),
    }
    return validate_internal_qrels_owner_acceptance(
        {**body, "decision_digest": canonical_digest(body)}
    )


def validate_internal_qrels_owner_acceptance(
    value: Mapping[str, Any]
) -> dict[str, Any]:
    body = dict(value)
    supplied = str(body.pop("decision_digest", ""))
    _require(
        value.get("schema_version") == SCHEMA_VERSION
        and supplied == canonical_digest(body),
        "internal_qrels_owner_decision_digest_invalid",
    )
    authority = dict(value.get("authority") or {})
    source = dict(value.get("source_qrels") or {})
    decision = dict(value.get("owner_decision") or {})
    boundaries = dict(value.get("preserved_boundaries") or {})
    calls = dict(value.get("observed_calls") or {})
    _require(
        value.get("status")
        == "owner_accepted_research_qrels_v1_3_ranking_entry_eligible"
        and authority.get("user_message") == "继续"
        and authority.get("owner_review_complete") is True
        and source.get("review_digest") == EXPECTED_REVIEW_DIGEST
        and source.get("target_count") == 18
        and len(source.get("accepted_qrel_digests") or []) == 18
        and decision.get("decision")
        == "accept_all_18_research_qrels_without_row_modification"
        and decision.get("review_state") == "owner_reviewed"
        and decision.get("accepted_qrel_count") == 18
        and decision.get("returned_qrel_count") == 0
        and decision.get("ranking_entry_eligible") is True,
        "internal_qrels_owner_decision_semantics_invalid",
    )
    _require(
        boundaries.get("selected_candidates_remain_candidate_only_not_evidence")
        is True
        and boundaries.get("ranking_quality_accepted") is False
        and boundaries.get("BGE_fusion_or_rerank_executed") is False
        and boundaries.get("current_quarter_exact_sql") == "0_of_6_open"
        and boundaries.get("external_official_required_slot_coverage")
        == "4_of_12_open_release_blocker"
        and boundaries.get("product_acceptance") is False
        and boundaries.get("release") == "not_qualified"
        and all(int(calls.get(key, -1)) == 0 for key in calls),
        "internal_qrels_owner_decision_boundary_invalid",
    )
    return dict(value)


__all__ = [
    "EXPECTED_QRELS_SHA256",
    "EXPECTED_REVIEW_DIGEST",
    "QRELS_REF",
    "SCHEMA_VERSION",
    "S1InternalQrelsOwnerAcceptanceError",
    "materialize_internal_qrels_owner_acceptance",
    "validate_internal_qrels_owner_acceptance",
]
