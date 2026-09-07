from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .evidence_role import EVIDENCE_ROLES
from .query_plan import canonical_digest
from .temporal import reporting_temporal_projection


EVIDENCE_OBJECT_VIEW_SCHEMA_VERSION = "fin_ia_evidence_object_view_v1_2"
EVIDENCE_OBJECT_ANNOTATION_SCHEMA_VERSION = (
    "fin_ia_evidence_object_annotation_v1_0"
)
EVIDENCE_QUERY_RELATION_SCHEMA_VERSION = "fin_ia_evidence_query_relation_v1_0"

OBJECT_FORMS = frozenset(
    {
        "claim",
        "metric_table",
        "parent_context",
        "mixed_source_segment",
        "navigation_or_boilerplate",
    }
)
FACT_STATES = frozenset(
    {
        "reported_observed",
        "management_guidance",
        "management_risk_or_hypothesis",
        "contractual_commitment",
        "standing_business_description",
        "point_in_time_snapshot",
        "not_applicable",
        "mixed",
    }
)
DIRECTNESS_STATES = frozenset(
    {
        "subject_direct",
        "evidence_owner_direct_bounded_readthrough",
        "indirect_industry_context",
        "context_only",
        "not_supportive",
    }
)
BACKGROUND_STATES = frozenset(
    {
        "core_evidence",
        "bounded_context",
        "background_only",
        "boilerplate_or_navigation",
    }
)
RELEVANCE_JUDGEMENTS = frozenset({"positive", "hard_negative", "unjudged"})
FOCUS_BINDING_MODES = frozenset(
    {
        "exact_text",
        "offset_bound_text",
        "bounded_text",
        "balanced_table",
        "full_source_segment",
        "parent_context",
    }
)

_ANNOTATION_ONLY_KEYS = frozenset(
    {
        "role_labels",
        "fact_state_labels",
        "directness",
        "background_state",
        "relevance_judgement",
        "business_rationale_zh",
        "label_authority",
    }
)
_SURFACE_ONLY_KEYS = frozenset(
    {
        "surface_text",
        "surface_digest",
        "source_record_digest",
        "parent_context",
    }
)


class EvidenceRoleContractError(ValueError):
    """Raised when an object/annotation contract would weaken lineage or labels."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise EvidenceRoleContractError(code)


def _nonempty_strings(value: object, code: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), code)
    normalized = tuple(str(item).strip() for item in value)
    _require(all(normalized), code)
    _require(len(normalized) == len(set(normalized)), code)
    _require(allow_empty or bool(normalized), code)
    return normalized


def _balanced_table(text: str) -> bool:
    starts = text.count("[TABLE_START")
    ends = text.count("[TABLE_END]")
    return starts == ends and starts > 0


def _surface_from_locator(
    record: Mapping[str, Any],
    parent: Mapping[str, Any],
    *,
    object_form: str,
    locator: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    mode = str(locator.get("mode") or "")
    _require(mode in FOCUS_BINDING_MODES, "evidence_object_locator_mode_invalid")
    raw_text = str(record.get("text") or "")
    _require(raw_text, "evidence_object_source_text_missing")

    if mode == "exact_text":
        surface = str(locator.get("text") or "")
        _require(surface and raw_text.count(surface) == 1, "evidence_object_exact_text_not_unique")
        start = raw_text.index(surface)
        binding = {"mode": mode, "char_start": start, "char_end": start + len(surface)}
    elif mode == "offset_bound_text":
        start = locator.get("char_start")
        end = locator.get("char_end")
        _require(
            isinstance(start, int)
            and not isinstance(start, bool)
            and isinstance(end, int)
            and not isinstance(end, bool)
            and 0 <= start < end <= len(raw_text),
            "evidence_object_offset_bounds_invalid",
        )
        surface = raw_text[start:end]
        expected_digest = str(locator.get("surface_digest") or "")
        _require(
            len(expected_digest) == 64
            and canonical_digest(surface) == expected_digest,
            "evidence_object_offset_surface_drift",
        )
        binding = {"mode": mode, "char_start": start, "char_end": end}
    elif mode == "bounded_text":
        start_text = str(locator.get("start_text") or "")
        end_text = str(locator.get("end_text") or "")
        _require(start_text and end_text, "evidence_object_bounded_markers_missing")
        _require(raw_text.count(start_text) == 1, "evidence_object_start_marker_not_unique")
        start = raw_text.index(start_text)
        end_start = raw_text.find(end_text, start + len(start_text))
        _require(end_start >= 0, "evidence_object_end_marker_missing")
        end = end_start + len(end_text)
        surface = raw_text[start:end]
        binding = {"mode": mode, "char_start": start, "char_end": end}
    elif mode == "balanced_table":
        table_id = str(locator.get("table_id") or "").strip()
        _require(table_id, "evidence_object_table_id_missing")
        marker = f"[TABLE_START id={table_id} "
        _require(raw_text.count(marker) == 1, "evidence_object_table_start_not_unique")
        start = raw_text.index(marker)
        end_start = raw_text.find("[TABLE_END]", start)
        _require(end_start >= 0, "evidence_object_table_end_missing")
        end = end_start + len("[TABLE_END]")
        surface = raw_text[start:end]
        _require(_balanced_table(surface), "evidence_object_table_unbalanced")
        binding = {
            "mode": mode,
            "table_id": table_id,
            "char_start": start,
            "char_end": end,
        }
    elif mode == "full_source_segment":
        surface = raw_text
        binding = {"mode": mode, "char_start": 0, "char_end": len(raw_text)}
    else:
        parent_context = {
            "ticker": str(parent.get("ticker") or ""),
            "company": str(parent.get("company") or ""),
            "source_type": str(parent.get("source_type") or ""),
            "source_tier": str(parent.get("source_tier") or ""),
            "publication_date": str(parent.get("publication_date") or ""),
            "period_end": str(parent.get("period_end") or ""),
            "fiscal_year": parent.get("fiscal_year"),
            "section": str(record.get("section") or ""),
            "subsection": str(record.get("subsection") or ""),
        }
        surface = "\n".join(
            f"{key}: {value}" for key, value in parent_context.items() if value not in {None, ""}
        )
        _require(surface, "evidence_object_parent_context_empty")
        binding = {"mode": mode, "parent_context": parent_context}

    if object_form == "metric_table":
        _require(mode == "balanced_table", "evidence_object_metric_table_binding_invalid")
    if object_form == "claim":
        _require(
            mode in {"exact_text", "offset_bound_text", "bounded_text"},
            "evidence_object_claim_binding_invalid",
        )
        _require("[TABLE_START" not in surface, "evidence_object_claim_contains_table")
    if object_form == "parent_context":
        _require(mode == "parent_context", "evidence_object_parent_binding_invalid")
    if object_form == "mixed_source_segment":
        _require(mode == "full_source_segment", "evidence_object_mixed_binding_invalid")
    if object_form == "navigation_or_boilerplate":
        _require(
            mode in {"exact_text", "bounded_text", "balanced_table"},
            "evidence_object_navigation_binding_invalid",
        )
    return surface, binding


@dataclass(frozen=True)
class EvidenceObjectView:
    schema_version: str
    object_view_id: str
    object_key: str
    object_form: str
    source_record_id: str
    source_record_digest: str
    parent_document_id: str
    parent_document_digest: str
    ticker: str
    company: str
    source_type: str
    source_tier: str
    publication_date: str
    period_end: str
    fiscal_year: int | None
    section: str
    subsection: str
    surface_text: str
    surface_digest: str
    focus_binding: Mapping[str, Any]
    temporal_binding: Mapping[str, Any]
    candidate_not_evidence: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_object_view(
    *,
    object_key: str,
    object_form: str,
    locator: Mapping[str, Any],
    record: Mapping[str, Any],
    parent: Mapping[str, Any],
) -> EvidenceObjectView:
    _require(object_key.strip() == object_key and bool(object_key), "evidence_object_key_invalid")
    _require(object_form in OBJECT_FORMS, "evidence_object_form_invalid")
    source_record_id = str(record.get("evidence_id") or "")
    parent_document_id = str((record.get("metadata") or {}).get("parent_document_id") or "")
    _require(source_record_id, "evidence_object_source_record_id_missing")
    _require(parent_document_id, "evidence_object_parent_document_id_missing")
    _require(parent_document_id == str(parent.get("document_id") or ""), "evidence_object_parent_mismatch")
    temporal = reporting_temporal_projection(record)
    effective_parent = {
        **dict(parent),
        "period_end": temporal["reporting_period_end"],
        "fiscal_year": temporal["reporting_fiscal_year"],
    }
    surface, focus_binding = _surface_from_locator(
        record,
        effective_parent,
        object_form=object_form,
        locator=locator,
    )
    source_record_digest = canonical_digest(record)
    parent_document_digest = canonical_digest(parent)
    identity = {
        "object_key": object_key,
        "object_form": object_form,
        "source_record_id": source_record_id,
        "source_record_digest": source_record_digest,
        "parent_document_id": parent_document_id,
        "parent_document_digest": parent_document_digest,
        "surface_digest": canonical_digest(surface),
        "focus_binding": focus_binding,
    }
    return EvidenceObjectView(
        schema_version=EVIDENCE_OBJECT_VIEW_SCHEMA_VERSION,
        object_view_id=f"EOV::{canonical_digest(identity)[:24]}",
        object_key=object_key,
        object_form=object_form,
        source_record_id=source_record_id,
        source_record_digest=source_record_digest,
        parent_document_id=parent_document_id,
        parent_document_digest=parent_document_digest,
        ticker=str(record.get("ticker") or ""),
        company=str(record.get("company") or ""),
        source_type=str(record.get("source_type") or ""),
        source_tier=str(record.get("source_tier") or ""),
        publication_date=str(record.get("publication_date") or ""),
        period_end=str(temporal["reporting_period_end"] or ""),
        fiscal_year=(
            temporal["reporting_fiscal_year"]
            if isinstance(temporal["reporting_fiscal_year"], int)
            else None
        ),
        section=str(record.get("section") or ""),
        subsection=str(record.get("subsection") or ""),
        surface_text=surface,
        surface_digest=canonical_digest(surface),
        focus_binding=focus_binding,
        temporal_binding=temporal,
        candidate_not_evidence=True,
    )


def build_object_annotation(
    *,
    object_view: Mapping[str, Any],
    role_labels: object,
    fact_state_labels: object,
    reason_codes: object,
    label_authority: str,
) -> dict[str, Any]:
    roles = _nonempty_strings(role_labels, "evidence_object_roles_invalid", allow_empty=True)
    facts = _nonempty_strings(fact_state_labels, "evidence_object_fact_states_invalid")
    reasons = _nonempty_strings(reason_codes, "evidence_object_reason_codes_invalid")
    _require(set(roles).issubset(EVIDENCE_ROLES), "evidence_object_role_unknown")
    _require(set(facts).issubset(FACT_STATES), "evidence_object_fact_state_unknown")
    _require(bool(label_authority.strip()), "evidence_object_label_authority_missing")
    if str(object_view.get("object_form")) == "parent_context":
        _require(not roles, "evidence_object_parent_context_role_leakage")
        _require(facts == ("not_applicable",), "evidence_object_parent_context_fact_state_invalid")
    value = {
        "schema_version": EVIDENCE_OBJECT_ANNOTATION_SCHEMA_VERSION,
        "object_view_id": str(object_view["object_view_id"]),
        "object_view_digest": canonical_digest(object_view),
        "object_form": str(object_view["object_form"]),
        "role_labels": list(roles),
        "fact_state_labels": list(facts),
        "reason_codes": list(reasons),
        "label_authority": label_authority.strip(),
        "evidence_promoted": False,
    }
    _require(not (_SURFACE_ONLY_KEYS & set(value)), "evidence_object_annotation_surface_leakage")
    return value


def build_query_relation(
    *,
    review_id: str,
    qrel: Mapping[str, Any],
    object_view: Mapping[str, Any],
    relevance_judgement: str,
    directness: str,
    background_state: str,
    reason_codes: object,
    business_rationale_zh: str,
    label_authority: str,
) -> dict[str, Any]:
    _require(review_id.strip() == review_id and bool(review_id), "evidence_relation_review_id_invalid")
    _require(relevance_judgement in RELEVANCE_JUDGEMENTS, "evidence_relation_judgement_invalid")
    _require(directness in DIRECTNESS_STATES, "evidence_relation_directness_invalid")
    _require(background_state in BACKGROUND_STATES, "evidence_relation_background_invalid")
    reasons = _nonempty_strings(reason_codes, "evidence_relation_reason_codes_invalid")
    _require(bool(business_rationale_zh.strip()), "evidence_relation_rationale_missing")
    _require(bool(label_authority.strip()), "evidence_relation_authority_missing")
    object_form = str(object_view.get("object_form") or "")
    if object_form == "parent_context":
        _require(relevance_judgement == "unjudged", "evidence_relation_parent_context_must_be_unjudged")
        _require(directness == "context_only", "evidence_relation_parent_context_directness_invalid")
    if relevance_judgement == "positive":
        _require(directness not in {"context_only", "not_supportive"}, "evidence_relation_positive_directness_invalid")
        _require(
            background_state in {"core_evidence", "bounded_context"},
            "evidence_relation_positive_background_invalid",
        )
    if relevance_judgement == "hard_negative":
        _require(background_state != "core_evidence", "evidence_relation_negative_core_invalid")
    value = {
        "schema_version": EVIDENCE_QUERY_RELATION_SCHEMA_VERSION,
        "review_id": review_id,
        "qrel_id": str(qrel.get("qrel_id") or ""),
        "case_key": str(qrel.get("case_key") or ""),
        "subject_ticker": str(qrel.get("subject_ticker") or ""),
        "evidence_slot_id": str(qrel.get("evidence_slot_id") or ""),
        "evidence_owner_ticker": str(qrel.get("evidence_owner_ticker") or ""),
        "relationship_direction": str(qrel.get("relationship_direction") or ""),
        "object_view_id": str(object_view["object_view_id"]),
        "object_view_digest": canonical_digest(object_view),
        "relevance_judgement": relevance_judgement,
        "directness": directness,
        "background_state": background_state,
        "reason_codes": list(reasons),
        "business_rationale_zh": business_rationale_zh.strip(),
        "label_authority": label_authority.strip(),
        "candidate_not_evidence": True,
        "evidence_promoted": False,
    }
    _require(not (_SURFACE_ONLY_KEYS & set(value)), "evidence_relation_surface_leakage")
    return value


def assert_object_view_is_label_free(value: Mapping[str, Any]) -> None:
    _require(
        not (_ANNOTATION_ONLY_KEYS & set(value)),
        "evidence_object_view_label_leakage",
    )


__all__ = [
    "BACKGROUND_STATES",
    "DIRECTNESS_STATES",
    "EVIDENCE_OBJECT_ANNOTATION_SCHEMA_VERSION",
    "EVIDENCE_OBJECT_VIEW_SCHEMA_VERSION",
    "EVIDENCE_QUERY_RELATION_SCHEMA_VERSION",
    "EvidenceObjectView",
    "EvidenceRoleContractError",
    "FACT_STATES",
    "FOCUS_BINDING_MODES",
    "OBJECT_FORMS",
    "RELEVANCE_JUDGEMENTS",
    "assert_object_view_is_label_free",
    "build_evidence_object_view",
    "build_object_annotation",
    "build_query_relation",
]
