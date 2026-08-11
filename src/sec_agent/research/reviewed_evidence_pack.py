from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


REVIEWED_EVIDENCE_PACK_SCHEMA = "fin_ia_0_1_3_s1_local_evidence_pack_v1_0"
REVIEWED_EVIDENCE_PACK_CONTRACT = (
    "fin_0_1_3.S1.candidate_to_local_evidence_pack:v1"
)


class ReviewedEvidencePackError(ValueError):
    """A reviewed Evidence Pack failed its immutable product contract."""

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
        raise ReviewedEvidencePackError(code)


def validate_reviewed_evidence_pack(pack: Mapping[str, Any]) -> None:
    """Validate the product-facing, immutable reviewed Evidence Pack surface.

    Generation and historical experiment code deliberately live outside this
    module.  The current Workbench depends only on this compact read contract.
    """

    normalized = deepcopy(dict(pack))
    digest = str(normalized.pop("pack_payload_digest", ""))
    _require(
        normalized.get("schema_version") == REVIEWED_EVIDENCE_PACK_SCHEMA
        and normalized.get("contract_ref") == REVIEWED_EVIDENCE_PACK_CONTRACT
        and digest == canonical_digest(normalized),
        "reviewed_evidence_pack_payload_digest_invalid",
    )
    evidence = [dict(row) for row in normalized.get("evidence_items") or ()]
    rejected = [dict(row) for row in normalized.get("rejected_items") or ()]
    gaps = [dict(row) for row in normalized.get("residual_gaps") or ()]
    evidence_targets = [str(row.get("target_id") or "") for row in evidence]
    rejected_targets = [str(row.get("target_id") or "") for row in rejected]
    _require(
        evidence
        and gaps
        and len(evidence_targets) == len(set(evidence_targets))
        and len(rejected_targets) == len(set(rejected_targets))
        and not (set(evidence_targets) & set(rejected_targets)),
        "reviewed_evidence_pack_target_partition_invalid",
    )
    for row in evidence:
        _require(
            row.get("writer_citable") is True
            and row.get("causal_attribution_authorized") is False
            and row.get("slot_bindings")
            and str(row.get("publication_date") or "")
            <= str(row.get("research_as_of") or ""),
            "reviewed_evidence_pack_evidence_boundary_invalid",
        )
        if row.get("disposition") == "accepted_bounded_context_evidence":
            _require(
                row.get("evidence_role")
                == "counterparty_or_ecosystem_readthrough"
                and all(
                    str(binding.get("claim_boundary_zh") or "")
                    for binding in row["slot_bindings"]
                ),
                "reviewed_evidence_pack_context_boundary_invalid",
            )
        if row.get("object_type") == "metric":
            metric = dict(row.get("structured_metric") or {})
            authority = dict(metric.get("currency_unit_authority") or {})
            _require(
                metric.get("table_path")
                and str(metric.get("raw_value") or "")
                and authority.get("status")
                in {
                    "source_and_child_consistent",
                    "non_monetary_dimension_preserved",
                },
                "reviewed_evidence_pack_metric_authority_invalid",
            )
    _require(
        all(row.get("writer_citable") is False for row in rejected)
        and all(row.get("gap_code") and row.get("slot_id") for row in gaps),
        "reviewed_evidence_pack_rejection_or_gap_boundary_invalid",
    )


__all__ = [
    "REVIEWED_EVIDENCE_PACK_CONTRACT",
    "REVIEWED_EVIDENCE_PACK_SCHEMA",
    "ReviewedEvidencePackError",
    "canonical_bytes",
    "canonical_digest",
    "file_sha256",
    "validate_reviewed_evidence_pack",
]
