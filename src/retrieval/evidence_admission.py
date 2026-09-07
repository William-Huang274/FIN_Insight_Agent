from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .query_plan import canonical_digest


ADMISSION_PACKET_SCHEMA_VERSION = (
    "fin_ia_s1_qualified_human_evidence_admission_packet_v1_0"
)


class EvidenceAdmissionError(ValueError):
    """Raised when a human Evidence-admission packet loses exact lineage."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise EvidenceAdmissionError(code)


def _index_unique(
    rows: Iterable[Mapping[str, Any]], field: str, code: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        key = str(row.get(field) or "")
        _require(key and key not in result, code)
        result[key] = row
    return result


def _bounded_excerpt(value: Any, *, limit: int = 1200) -> str:
    text = " ".join(str(value or "").split())
    _require(bool(text), "evidence_admission_candidate_text_missing")
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _source_projection(
    *,
    compiled: Mapping[str, Any],
    source_records: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], str]:
    base = dict(compiled.get("base_object_view") or {})
    lineage_ids = sorted(
        {
            str(item)
            for item in compiled.get("lineage_source_record_ids") or ()
            if str(item)
        }
    )
    _require(lineage_ids, "evidence_admission_source_lineage_missing")
    records = []
    for source_id in lineage_ids:
        record = source_records.get(source_id)
        _require(record is not None, "evidence_admission_source_record_missing")
        records.append(dict(record))
    primary = records[0]
    source = {
        "source_record_ids": lineage_ids,
        "evidence_owner_ticker": str(
            base.get("ticker") or primary.get("ticker") or ""
        ).upper(),
        "company": base.get("company") or primary.get("company"),
        "source_type": base.get("source_type") or primary.get("source_type"),
        "source_tier": base.get("source_tier") or primary.get("source_tier"),
        "publication_date": base.get("publication_date")
        or primary.get("publication_date"),
        "period_end": base.get("period_end") or primary.get("period_end"),
        "section": base.get("section") or primary.get("section"),
        "subsection": base.get("subsection") or primary.get("subsection"),
        "source_url": primary.get("source_url"),
        "license_scope": primary.get("license_scope"),
        "redistributable": bool(primary.get("redistributable")),
        "bounded_excerpt": _bounded_excerpt(
            compiled.get("model_text") or base.get("surface_text")
        ),
    }
    _require(
        source["evidence_owner_ticker"]
        and source["source_type"]
        and source["publication_date"]
        and source["source_url"],
        "evidence_admission_source_binding_incomplete",
    )
    lineage_digest = canonical_digest(
        {
            "source_record_ids": lineage_ids,
            "source_record_digests": sorted(
                str(record.get("metadata", {}).get("source_record_digest") or "")
                for record in records
            ),
            "compiled_object_id": compiled.get("compiled_object_id"),
        }
    )
    return source, lineage_digest


def compile_qualified_human_admission_packet(
    *,
    current_case_results: Sequence[Mapping[str, Any]],
    compiled_objects: Iterable[Mapping[str, Any]],
    source_records: Iterable[Mapping[str, Any]],
    recorded_at: str,
) -> dict[str, Any]:
    """Compile exact candidate-to-proposition review work without promotion.

    The packet contains only candidates already selected by the immutable S1
    readiness results.  It neither invents a label nor lets ranking scores become
    Evidence.  A qualified human must decide every candidate/proposition binding.
    """

    compiled_by_id = _index_unique(
        compiled_objects,
        "compiled_object_id",
        "evidence_admission_compiled_object_duplicate",
    )
    source_by_id = _index_unique(
        source_records,
        "evidence_id",
        "evidence_admission_source_record_duplicate",
    )
    cases: list[dict[str, Any]] = []
    candidate_binding_count = 0
    requirement_count = 0
    for raw_case in current_case_results:
        case = dict(raw_case)
        case_key = str(case.get("case_key") or "").upper()
        readiness = dict(case.get("pack_readiness") or {})
        _require(case_key, "evidence_admission_case_identity_missing")
        request_rows: list[dict[str, Any]] = []
        for raw_request in readiness.get("requests") or ():
            request = dict(raw_request)
            pending: list[dict[str, Any]] = []
            for raw_requirement in request.get("requirements") or ():
                requirement = dict(raw_requirement)
                if requirement.get("readiness_state") != "blocked_by_evidence_admission":
                    continue
                selected = [
                    str(item)
                    for item in requirement.get("selected_candidate_ids") or ()
                    if str(item)
                ]
                _require(
                    selected,
                    "evidence_admission_pending_requirement_without_candidate",
                )
                candidates: list[dict[str, Any]] = []
                for candidate_id in selected:
                    compiled = compiled_by_id.get(candidate_id)
                    _require(
                        compiled is not None,
                        "evidence_admission_selected_candidate_missing",
                    )
                    source, lineage_digest = _source_projection(
                        compiled=compiled,
                        source_records=source_by_id,
                    )
                    item_body = {
                        "candidate_or_evidence_ref": candidate_id,
                        "compiled_object_kind": compiled.get("object_kind"),
                        "numeric_authority": False,
                        "candidate_is_not_evidence": True,
                        "source_lineage_digest": lineage_digest,
                        "source": source,
                    }
                    candidates.append(
                        {
                            **item_body,
                            "candidate_admission_item_digest": canonical_digest(
                                item_body
                            ),
                        }
                    )
                    candidate_binding_count += 1
                pending.append(
                    {
                        "requirement_id": requirement.get("requirement_id"),
                        "facet_id": requirement.get("facet_id"),
                        "evidence_role": requirement.get("role"),
                        "target_entities": requirement.get("target_entities") or [],
                        "metric_ids": requirement.get("metric_ids") or [],
                        "product_ids": requirement.get("product_ids") or [],
                        "candidate_count": len(candidates),
                        "candidates": candidates,
                    }
                )
                requirement_count += 1
            if pending:
                request_rows.append(
                    {
                        "request_id": request.get("request_id"),
                        "slot_id": request.get("slot_id"),
                        "facet_id": request.get("facet_id"),
                        "business_question_zh": request.get(
                            "business_question_zh"
                        ),
                        "pending_requirement_count": len(pending),
                        "requirements": pending,
                    }
                )
        cases.append(
            {
                "case_key": case_key,
                "request_count": len(request_rows),
                "pending_requirement_count": sum(
                    row["pending_requirement_count"] for row in request_rows
                ),
                "requests": request_rows,
            }
        )
    body = {
        "schema_version": ADMISSION_PACKET_SCHEMA_VERSION,
        "status": "qualified_human_evidence_admission_packet_ready_no_promotion",
        "recorded_at": recorded_at,
        "case_count": len(cases),
        "pending_request_count": sum(row["request_count"] for row in cases),
        "pending_requirement_count": requirement_count,
        "candidate_binding_count": candidate_binding_count,
        "cases": cases,
        "review_instruction_zh": (
            "逐个判断该精确候选能否在当前公司、期间、来源角色和命题下成为 Evidence；"
            "accept/reject/needs_review 均需原因。表格候选不因此获得 NumericFact 权威。"
        ),
        "authority": {
            "candidate_is_evidence": False,
            "numeric_fact_authority": False,
            "automatic_promotion": False,
            "qualified_human_receipt_required": True,
            "public_information_gap_authority": False,
            "S1_qualification_authority": False,
        },
    }
    return {**body, "packet_digest": canonical_digest(body)}


def candidate_binding_index(
    packet: Mapping[str, Any],
) -> dict[tuple[str, str, str, str], dict[str, str]]:
    _require(
        packet.get("schema_version") == ADMISSION_PACKET_SCHEMA_VERSION,
        "evidence_admission_packet_schema_invalid",
    )
    body = dict(packet)
    digest = str(body.pop("packet_digest", ""))
    _require(
        digest == canonical_digest(body),
        "evidence_admission_packet_digest_invalid",
    )
    result: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for case in packet.get("cases") or ():
        case_key = str(case.get("case_key") or "").upper()
        for request in case.get("requests") or ():
            request_id = str(request.get("request_id") or "")
            for requirement in request.get("requirements") or ():
                requirement_id = str(requirement.get("requirement_id") or "")
                for candidate in requirement.get("candidates") or ():
                    candidate_ref = str(
                        candidate.get("candidate_or_evidence_ref") or ""
                    )
                    key = (case_key, request_id, requirement_id, candidate_ref)
                    _require(
                        all(key) and key not in result,
                        "evidence_admission_packet_candidate_binding_duplicate",
                    )
                    result[key] = {
                        "candidate_admission_item_digest": str(
                            candidate.get("candidate_admission_item_digest") or ""
                        ),
                        "source_lineage_digest": str(
                            candidate.get("source_lineage_digest") or ""
                        ),
                    }
    return result


__all__ = [
    "ADMISSION_PACKET_SCHEMA_VERSION",
    "EvidenceAdmissionError",
    "candidate_binding_index",
    "compile_qualified_human_admission_packet",
]
