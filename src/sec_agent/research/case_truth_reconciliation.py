from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping, Sequence

from .reviewed_evidence_pack import canonical_digest


CASE_TRUTH_PACKET_SCHEMA_VERSION = "fin_ia_case_truth_packet_v1_0"
CASE_TRUTH_MODEL_VIEW_SCHEMA_VERSION = "fin_ia_case_truth_model_view_v1_0"
CASE_TRUTH_DOCUMENT_SCHEMA_VERSION = "fin_ia_case_truth_claim_document_v1_0"
CASE_TRUTH_RECONCILIATION_SCHEMA_VERSION = (
    "fin_ia_case_truth_semantic_reconciliation_v1_0"
)

_ASSERTED_STATES = {
    "present_in_current_case",
    "not_visible_in_current_cell",
    "absent_from_current_case",
    "unresolved_or_partially_covered",
}
_COVERAGE_STATUSES = {
    "claims_mapped",
    "no_case_truth_claim",
    "material_claim_unmapped",
}
_ATOM_FIELDS = ("thesis_atom", "mechanism_atom", "counterargument_atom")
_SYNTHESIS_FIELDS = (
    "executive_thesis",
    "cross_cell_mechanism",
    "strongest_counterargument",
)


class CaseTruthReconciliationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CaseTruthReconciliationError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _rows(value: object, code: str) -> list[Mapping[str, Any]]:
    _require(
        isinstance(value, list) and all(isinstance(row, Mapping) for row in value),
        code,
    )
    return list(value)


def _strings(value: object, code: str) -> list[str]:
    _require(isinstance(value, list), code)
    output = [str(row or "") for row in value]
    _require("" not in output and len(output) == len(set(output)), code)
    return output


def _facet_alias(slot_id: str, facet_id: str) -> str:
    return f"TRUTH::FACET::{slot_id}::{facet_id}"


def _numeric_alias(ref: str) -> str:
    return f"TRUTH::NUMERIC::{ref}"


def _relation_alias(ref: str) -> str:
    return f"TRUTH::RELATION::{ref}"


def _qualitative_alias(ref: str) -> str:
    return f"TRUTH::QUALITATIVE::{ref}"


def _bridge_alias(ref: str) -> str:
    return f"TRUTH::BRIDGE::{ref}"


def compile_case_truth_packet(
    research_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile case-wide presence, visibility and typed absence authority.

    This compiler does not infer facts from prose.  It projects only reviewed
    Evidence bindings, authoritative NumericFacts/relations, source-bound
    qualitative facts, typed gaps and already-compiled bridge boundaries.
    """

    case_identity = _mapping(
        research_input.get("case_identity"), "case_truth_identity_missing"
    )
    case_key = str(case_identity.get("case_key") or "").upper()
    ticker = str(case_identity.get("subject_ticker") or "").upper()
    research_as_of = str(case_identity.get("research_as_of") or "")
    research_input_digest = str(research_input.get("research_input_digest") or "")
    _require(
        case_key and ticker and research_as_of and research_input_digest,
        "case_truth_binding_missing",
    )

    presence: dict[str, dict[str, Any]] = {}
    seen_evidence_refs: set[str] = set()

    for evidence in _rows(
        research_input.get("evidence_cards"), "case_truth_evidence_cards_invalid"
    ):
        evidence_ref = str(evidence.get("evidence_ref") or "")
        owner = str(evidence.get("evidence_owner_ticker") or "").upper()
        _require(
            evidence_ref and owner and evidence_ref not in seen_evidence_refs,
            "case_truth_evidence_identity_invalid",
        )
        seen_evidence_refs.add(evidence_ref)
        for binding in _rows(
            evidence.get("slot_bindings"), "case_truth_slot_bindings_invalid"
        ):
            slot_id = str(binding.get("slot_id") or "")
            facets = _strings(
                binding.get("facet_ids"), "case_truth_facet_ids_invalid"
            )
            _require(slot_id, "case_truth_slot_id_missing")
            for facet_id in facets:
                alias = _facet_alias(slot_id, facet_id)
                row = presence.setdefault(
                    alias,
                    {
                        "truth_alias": alias,
                        "truth_kind": "reviewed_evidence_facet",
                        "slot_id": slot_id,
                        "facet_id": facet_id,
                        "evidence_refs": set(),
                        "owner_tickers": set(),
                        "publication_dates": set(),
                        "reporting_period_ends": set(),
                        "business_meanings_zh": set(),
                        "claim_boundaries_zh": set(),
                    },
                )
                row["evidence_refs"].add(evidence_ref)
                row["owner_tickers"].add(owner)
                for source_key, target_key in (
                    ("publication_date", "publication_dates"),
                    ("source_reporting_period_end", "reporting_period_ends"),
                ):
                    value = str(evidence.get(source_key) or "")
                    if value:
                        row[target_key].add(value)
                for source_key, target_key in (
                    ("business_meaning_zh", "business_meanings_zh"),
                    ("claim_boundary_zh", "claim_boundaries_zh"),
                ):
                    value = str(binding.get(source_key) or "")
                    if value:
                        row[target_key].add(value)

    seen_numeric_refs: set[str] = set()
    for numeric in _rows(
        research_input.get("numeric_fact_cards"),
        "case_truth_numeric_cards_invalid",
    ):
        ref = str(numeric.get("numeric_ref") or "")
        _require(
            ref and ref not in seen_numeric_refs,
            "case_truth_numeric_ref_missing",
        )
        seen_numeric_refs.add(ref)
        owner = str(numeric.get("ticker") or "").upper()
        _require(owner, "case_truth_numeric_owner_missing")
        alias = _numeric_alias(ref)
        presence[alias] = {
            "truth_alias": alias,
            "truth_kind": "numeric_fact",
            "numeric_refs": {ref},
            "owner_tickers": {owner},
            "metric_id": str(numeric.get("metric_id") or ""),
            "period_end": str(numeric.get("period_end") or ""),
            "fiscal_period": str(numeric.get("fiscal_period") or ""),
            "fiscal_year": numeric.get("fiscal_year"),
            "unit": str(numeric.get("unit") or ""),
        }

    seen_relation_refs: set[str] = set()
    for relation in _rows(
        research_input.get("numeric_relation_cards"),
        "case_truth_relation_cards_invalid",
    ):
        ref = str(relation.get("numeric_relation_ref") or "")
        _require(
            ref and ref not in seen_relation_refs,
            "case_truth_relation_ref_missing",
        )
        seen_relation_refs.add(ref)
        owner = str(relation.get("ticker") or "").upper()
        _require(owner, "case_truth_relation_owner_missing")
        alias = _relation_alias(ref)
        presence[alias] = {
            "truth_alias": alias,
            "truth_kind": "numeric_relation",
            "numeric_relation_refs": {ref},
            "owner_tickers": {owner},
            "metric_id": str(relation.get("metric_id") or ""),
            "relation_type": str(relation.get("relation_type") or ""),
            "current_period_end": str(relation.get("current_period_end") or ""),
            "comparison_period_end": str(
                relation.get("comparison_period_end") or ""
            ),
            "direction": str(relation.get("direction") or ""),
            "unit": str(relation.get("unit") or ""),
        }

    seen_qualitative_refs: set[str] = set()
    for qualitative in _rows(
        research_input.get("source_bound_qualitative_fact_cards") or [],
        "case_truth_qualitative_cards_invalid",
    ):
        ref = str(qualitative.get("qualitative_fact_ref") or "")
        _require(
            ref and ref not in seen_qualitative_refs,
            "case_truth_qualitative_ref_missing",
        )
        seen_qualitative_refs.add(ref)
        alias = _qualitative_alias(ref)
        presence[alias] = {
            "truth_alias": alias,
            "truth_kind": "source_bound_qualitative_fact",
            "qualitative_fact_refs": {ref},
            "owner_tickers": {case_key},
            "metric_id": str(qualitative.get("metric_id") or ""),
            "period_end": str(qualitative.get("period_end") or ""),
            "display_surface_zh": str(
                qualitative.get("display_surface_zh") or ""
            ),
            "qualifier_zh": str(qualitative.get("qualifier_zh") or ""),
        }

    gap_by_alias_rows: dict[str, dict[str, Any]] = {}
    gaps_by_ref: dict[str, Mapping[str, Any]] = {}
    for gap in _rows(
        research_input.get("residual_gap_cards"), "case_truth_gap_cards_invalid"
    ):
        gap_ref = str(gap.get("gap_ref") or "")
        slot_id = str(gap.get("slot_id") or "")
        facet_id = str(gap.get("facet_id") or "")
        gap_code = str(gap.get("gap_code") or "")
        _require(
            gap_ref and slot_id and facet_id and gap_code,
            "case_truth_gap_identity_invalid",
        )
        _require(gap_ref not in gaps_by_ref, "case_truth_gap_ref_duplicate")
        gaps_by_ref[gap_ref] = gap
        alias = _facet_alias(slot_id, facet_id)
        coexistence = alias in presence
        row = gap_by_alias_rows.setdefault(
            alias,
            {
                "truth_alias": alias,
                "truth_kind": "typed_gap",
                "slot_id": slot_id,
                "facet_id": facet_id,
                "gap_refs": set(),
                "gap_codes": set(),
                "coverage_state": (
                    "present_with_typed_gap" if coexistence else "typed_gap_only"
                ),
                "case_absence_authorized": not coexistence,
                "business_reasons_zh": set(),
            },
        )
        row["gap_refs"].add(gap_ref)
        row["gap_codes"].add(gap_code)
        reason = str(gap.get("business_reason_zh") or "")
        if reason:
            row["business_reasons_zh"].add(reason)

    bridge_boundaries: dict[str, dict[str, Any]] = {}
    cells = _rows(research_input.get("cells"), "case_truth_cells_invalid")
    cell_ids = [str(cell.get("cell_id") or "") for cell in cells]
    _require(
        "" not in cell_ids and len(cell_ids) == len(set(cell_ids)),
        "case_truth_cell_id_missing",
    )
    cells.sort(key=lambda row: str(row["cell_id"]))
    for cell in cells:
        cell_id = str(cell.get("cell_id") or "")
        card = cell.get("claim_relation_card")
        if not isinstance(card, Mapping):
            continue
        combinations = _rows(
            card.get("allowed_combinations"),
            "case_truth_claim_relations_invalid",
        )
        for relation in combinations:
            if not (
                relation.get("causal_bridge_authority") == "bridge_unavailable"
                or relation.get("claim_relation") == "bridge_not_established"
            ):
                continue
            ref = str(relation.get("claim_relation_ref") or "")
            required_gaps = _strings(
                relation.get("required_gap_refs"),
                "case_truth_bridge_gap_refs_invalid",
            )
            _require(
                ref and required_gaps and set(required_gaps).issubset(gaps_by_ref),
                "case_truth_bridge_boundary_invalid",
            )
            alias = _bridge_alias(ref)
            row = bridge_boundaries.setdefault(
                alias,
                {
                    "truth_alias": alias,
                    "truth_kind": "typed_bridge_boundary",
                    "claim_relation_ref": ref,
                    "claim_subject": str(relation.get("claim_subject") or ""),
                    "claim_outcome": str(relation.get("claim_outcome") or ""),
                    "claim_relation": str(relation.get("claim_relation") or ""),
                    "required_gap_refs": sorted(required_gaps),
                    "cell_ids": set(),
                    "coverage_state": "typed_gap_only",
                    "case_absence_authorized": True,
                },
            )
            _require(
                row["claim_relation_ref"] == ref
                and row["claim_subject"]
                == str(relation.get("claim_subject") or "")
                and row["claim_outcome"]
                == str(relation.get("claim_outcome") or "")
                and row["claim_relation"]
                == str(relation.get("claim_relation") or "")
                and row["required_gap_refs"] == sorted(required_gaps),
                "case_truth_bridge_boundary_drift",
            )
            row["cell_ids"].add(cell_id)

    def freeze(row: Mapping[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in row.items():
            output[key] = sorted(value) if isinstance(value, set) else deepcopy(value)
        return output

    presence_catalog = [freeze(presence[key]) for key in sorted(presence)]
    gap_catalog = [
        freeze(gap_by_alias_rows[key]) for key in sorted(gap_by_alias_rows)
    ]
    bridge_catalog = [
        freeze(bridge_boundaries[key]) for key in sorted(bridge_boundaries)
    ]

    presence_by_alias = {row["truth_alias"]: row for row in presence_catalog}
    gap_by_alias: dict[str, list[dict[str, Any]]] = {}
    for row in gap_catalog:
        gap_by_alias.setdefault(str(row["truth_alias"]), []).append(row)

    visibility = []
    for cell in cells:
        cell_id = str(cell.get("cell_id") or "")
        _require(cell_id, "case_truth_cell_id_missing")
        evidence_refs = set(cell.get("allowed_evidence_refs") or [])
        numeric_refs = set(cell.get("allowed_numeric_refs") or [])
        relation_refs = set(cell.get("allowed_numeric_relation_refs") or [])
        qualitative_refs = set(cell.get("allowed_qualitative_fact_refs") or [])
        visible_presence: set[str] = set()
        for alias, row in presence_by_alias.items():
            if (
                evidence_refs.intersection(row.get("evidence_refs") or [])
                or numeric_refs.intersection(row.get("numeric_refs") or [])
                or relation_refs.intersection(row.get("numeric_relation_refs") or [])
                or qualitative_refs.intersection(
                    row.get("qualitative_fact_refs") or []
                )
            ):
                visible_presence.add(alias)
        visible_gap_refs = set(cell.get("visible_gap_refs") or [])
        visible_gap_aliases = {
            alias
            for alias, rows in gap_by_alias.items()
            if any(visible_gap_refs.intersection(row["gap_refs"]) for row in rows)
        }
        visible_bridge_aliases = {
            alias
            for alias, row in bridge_boundaries.items()
            if cell_id in row["cell_ids"]
        }
        visibility.append(
            {
                "cell_id": cell_id,
                "visible_presence_aliases": sorted(visible_presence),
                "not_visible_presence_aliases": sorted(
                    set(presence_by_alias) - visible_presence
                ),
                "visible_gap_aliases": sorted(visible_gap_aliases),
                "visible_bridge_boundary_aliases": sorted(
                    visible_bridge_aliases
                ),
            }
        )

    all_truth_aliases = sorted(
        set(presence_by_alias)
        | {str(row["truth_alias"]) for row in gap_catalog}
        | set(bridge_boundaries)
    )
    _require(all_truth_aliases, "case_truth_catalog_empty")
    unsigned = {
        "schema_version": CASE_TRUTH_PACKET_SCHEMA_VERSION,
        "case_identity": {
            "case_key": case_key,
            "subject_ticker": ticker,
            "research_as_of": research_as_of,
        },
        "research_input_digest": research_input_digest,
        "presence_catalog": presence_catalog,
        "typed_gap_catalog": gap_catalog,
        "typed_bridge_boundary_catalog": bridge_catalog,
        "cell_visibility_matrix": visibility,
        "all_truth_aliases": all_truth_aliases,
        "authority": {
            "reviewed_presence_is_harness_compiled": True,
            "case_absence_requires_typed_gap_or_bridge_boundary": True,
            "cell_invisibility_is_not_case_absence": True,
            "presence_and_residual_gap_may_coexist": True,
            "semantic_reconciler_may_classify_but_not_create_truth": True,
            "phrase_regex_is_not_truth_authority": True,
        },
        "coverage_receipt": {
            "reviewed_evidence_ref_count": len(
                {
                    ref
                    for row in presence_catalog
                    for ref in row.get("evidence_refs") or []
                }
            ),
            "numeric_fact_ref_count": len(
                {
                    ref
                    for row in presence_catalog
                    for ref in row.get("numeric_refs") or []
                }
            ),
            "numeric_relation_ref_count": len(
                {
                    ref
                    for row in presence_catalog
                    for ref in row.get("numeric_relation_refs") or []
                }
            ),
            "typed_gap_ref_count": len(gaps_by_ref),
            "typed_bridge_boundary_count": len(bridge_catalog),
            "cell_count": len(visibility),
        },
    }
    return {**unsigned, "case_truth_packet_digest": canonical_digest(unsigned)}


def validate_case_truth_packet(
    packet: Mapping[str, Any], *, research_input: Mapping[str, Any]
) -> dict[str, Any]:
    expected = compile_case_truth_packet(research_input)
    _require(
        dict(packet) == expected,
        "case_truth_packet_binding_drift",
    )
    return expected


def compile_case_truth_model_view(
    case_truth_packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Project the full local authority packet into a compact model view."""

    packet_digest = str(case_truth_packet.get("case_truth_packet_digest") or "")
    _require(
        packet_digest
        and packet_digest
        == canonical_digest(
            {
                key: deepcopy(value)
                for key, value in case_truth_packet.items()
                if key != "case_truth_packet_digest"
            }
        ),
        "case_truth_model_view_packet_invalid",
    )
    by_kind = {
        "reviewed_evidence_facet": {
            "evidence_refs",
            "owner_tickers",
            "publication_dates",
            "reporting_period_ends",
            "business_meanings_zh",
            "claim_boundaries_zh",
        },
        "numeric_fact": {
            "owner_tickers",
            "metric_id",
            "period_end",
            "fiscal_period",
            "fiscal_year",
            "unit",
        },
        "numeric_relation": {
            "owner_tickers",
            "metric_id",
            "relation_type",
            "current_period_end",
            "comparison_period_end",
            "direction",
            "unit",
        },
        "source_bound_qualitative_fact": {
            "owner_tickers",
            "metric_id",
            "period_end",
            "display_surface_zh",
            "qualifier_zh",
        },
    }
    presence_groups: dict[str, dict[str, Any]] = {}
    for row in _rows(
        case_truth_packet.get("presence_catalog"),
        "case_truth_presence_catalog_invalid",
    ):
        kind = str(row.get("truth_kind") or "")
        _require(kind in by_kind, "case_truth_presence_kind_invalid")
        shared = {
            "truth_kind": kind,
            **{
                key: deepcopy(row[key])
                for key in sorted(by_kind[kind])
                if key in row
            },
        }
        group_key = canonical_digest(shared)
        group = presence_groups.setdefault(
            group_key,
            {**shared, "truth_aliases": []},
        )
        group["truth_aliases"].append(str(row["truth_alias"]))
    presence_view = []
    for group_key in sorted(presence_groups):
        group = presence_groups[group_key]
        group["truth_aliases"] = sorted(set(group["truth_aliases"]))
        presence_view.append(group)
    projected_aliases = sorted(
        alias for row in presence_view for alias in row["truth_aliases"]
    )
    authority_presence_aliases = sorted(
        str(row["truth_alias"])
        for row in case_truth_packet["presence_catalog"]
    )
    _require(
        projected_aliases == authority_presence_aliases,
        "case_truth_model_view_presence_alias_drift",
    )
    visibility_view = []
    for row in _rows(
        case_truth_packet.get("cell_visibility_matrix"),
        "case_truth_visibility_matrix_invalid",
    ):
        visibility_view.append(
            {
                "cell_id": str(row.get("cell_id") or ""),
                "visible_presence_aliases": list(
                    row.get("visible_presence_aliases") or []
                ),
                "visible_gap_aliases": list(row.get("visible_gap_aliases") or []),
                "visible_bridge_boundary_aliases": list(
                    row.get("visible_bridge_boundary_aliases") or []
                ),
            }
        )
    unsigned = {
        "schema_version": CASE_TRUTH_MODEL_VIEW_SCHEMA_VERSION,
        "case_truth_packet_digest": packet_digest,
        "case_identity": deepcopy(case_truth_packet["case_identity"]),
        "presence_catalog": presence_view,
        "typed_gap_catalog": deepcopy(case_truth_packet["typed_gap_catalog"]),
        "typed_bridge_boundary_catalog": deepcopy(
            case_truth_packet["typed_bridge_boundary_catalog"]
        ),
        "cell_visibility_matrix": visibility_view,
        "authority": {
            "presence_rows_may_group_multiple_truth_aliases": True,
            "cell_invisibility_is_not_case_absence": True,
            "case_absence_requires_typed_gap_or_bridge_boundary": True,
            "presence_and_residual_gap_may_coexist": True,
            "semantic_reconciler_may_classify_but_not_create_truth": True,
        },
    }
    return {**unsigned, "case_truth_model_view_digest": canonical_digest(unsigned)}


def _claim_surface(
    *,
    surface_id: str,
    cell_id: str | None,
    field: str,
    text: object,
    truth_assertion_required: bool,
) -> dict[str, Any]:
    value = str(text or "").strip()
    _require(value, "case_truth_claim_surface_text_missing")
    binding = {
        "claim_surface_id": surface_id,
        "cell_id": cell_id,
        "field": field,
        "text": value,
        "truth_assertion_required": truth_assertion_required,
    }
    return {**binding, "claim_surface_digest": canonical_digest(binding)}


def compile_cell_judgment_claim_document(
    judgment_output: Mapping[str, Any],
) -> dict[str, Any]:
    cells = _rows(
        judgment_output.get("cells"), "case_truth_judgment_cells_invalid"
    )
    _require(len(cells) == 5, "case_truth_judgment_cell_coverage_invalid")
    surfaces = []
    seen_cells: set[str] = set()
    for cell in cells:
        cell_id = str(cell.get("cell_id") or "")
        _require(
            cell_id and cell_id not in seen_cells,
            "case_truth_judgment_cell_coverage_invalid",
        )
        seen_cells.add(cell_id)
        for field in _ATOM_FIELDS:
            surfaces.append(
                _claim_surface(
                    surface_id=f"{cell_id}::{field}",
                    cell_id=cell_id,
                    field=field,
                    text=cell.get(field),
                    truth_assertion_required=True,
                )
            )
    binding_digest = str(judgment_output.get("judgment_output_digest") or "")
    _require(binding_digest, "case_truth_judgment_digest_missing")
    unsigned = {
        "schema_version": CASE_TRUTH_DOCUMENT_SCHEMA_VERSION,
        "document_kind": "cell_judgments",
        "binding_digest": binding_digest,
        "claim_surfaces": surfaces,
    }
    return {**unsigned, "claim_document_digest": canonical_digest(unsigned)}


def compile_synthesis_claim_document(
    synthesis: Mapping[str, Any],
) -> dict[str, Any]:
    surfaces = [
        _claim_surface(
            surface_id=f"SYNTHESIS::{field}",
            cell_id=None,
            field=field,
            text=synthesis.get(field),
            truth_assertion_required=True,
        )
        for field in _SYNTHESIS_FIELDS
    ]
    links = _rows(synthesis.get("cell_links"), "case_truth_synthesis_links_invalid")
    for index, link in enumerate(links):
        relation = str(link.get("relation") or "")
        explanation = str(link.get("explanation") or "")
        surfaces.append(
            _claim_surface(
                surface_id=f"SYNTHESIS::cell_link::{index}",
                cell_id=None,
                field="cell_link",
                text=(
                    f"from_cell_id={link.get('from_cell_id')}; "
                    f"to_cell_id={link.get('to_cell_id')}; "
                    f"relation={relation}; explanation={explanation}"
                ),
                truth_assertion_required=True,
            )
        )
    wwc = _mapping(
        synthesis.get("what_would_change"), "case_truth_synthesis_wwc_invalid"
    )
    surfaces.append(
        _claim_surface(
            surface_id="SYNTHESIS::what_would_change::observable",
            cell_id=None,
            field="what_would_change_observable",
            text=wwc.get("observable"),
            truth_assertion_required=False,
        )
    )
    binding_digest = str(synthesis.get("synthesis_digest") or "")
    _require(binding_digest, "case_truth_synthesis_digest_missing")
    unsigned = {
        "schema_version": CASE_TRUTH_DOCUMENT_SCHEMA_VERSION,
        "document_kind": "synthesis",
        "binding_digest": binding_digest,
        "claim_surfaces": surfaces,
    }
    return {**unsigned, "claim_document_digest": canonical_digest(unsigned)}


def compile_case_truth_reconciliation_submission(
    *,
    case_truth_packet: Mapping[str, Any],
    claim_document: Mapping[str, Any],
) -> tuple[tuple[dict[str, str], ...], dict[str, Any]]:
    aliases = _strings(
        case_truth_packet.get("all_truth_aliases"),
        "case_truth_alias_catalog_invalid",
    )
    surfaces = _rows(
        claim_document.get("claim_surfaces"),
        "case_truth_claim_surfaces_invalid",
    )
    surface_ids = [str(row.get("claim_surface_id") or "") for row in surfaces]
    surface_digests = [str(row.get("claim_surface_digest") or "") for row in surfaces]
    _require(
        "" not in surface_ids
        and "" not in surface_digests
        and len(surface_ids) == len(set(surface_ids)),
        "case_truth_claim_surface_identity_invalid",
    )
    view = {
        "task": "semantic_case_truth_reconciliation_only",
        "case_truth_packet": compile_case_truth_model_view(case_truth_packet),
        "claim_document": deepcopy(dict(claim_document)),
        "rules": [
            "Classify every supplied claim surface; do not write or repair research.",
            "Map every material assertion about whether a fact, metric, relation or bridge exists, is absent, is locally invisible or remains unresolved.",
            "Split bundled assertions across distinct truth aliases.",
            "Use no_case_truth_claim only when truth_assertion_required is false and the surface makes no material presence, absence, visibility or unresolved-coverage assertion.",
            "Use material_claim_unmapped when a material assertion has no exact truth alias; never invent an alias.",
            "The Harness truth packet, not this classifier, remains final fact and absence authority.",
        ],
    }
    messages = (
        {
            "role": "system",
            "content": (
                "You are a semantic reconciliation node, not a financial "
                "researcher or writer. Exhaustively classify the supplied "
                "surfaces against the immutable case truth aliases. Split "
                "bundled claims. Submit exactly one tool call and add no facts."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                view, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )

    assertion = {
        "type": "object",
        "properties": {
            "truth_alias": {"type": "string", "enum": aliases},
            "asserted_state": {
                "type": "string",
                "enum": sorted(_ASSERTED_STATES),
            },
        },
        "required": ["truth_alias", "asserted_state"],
        "additionalProperties": False,
    }
    surface = {
        "type": "object",
        "properties": {
            "claim_surface_id": {"type": "string", "enum": surface_ids},
            "claim_surface_digest": {
                "type": "string",
                "enum": surface_digests,
            },
            "coverage_status": {
                "type": "string",
                "enum": sorted(_COVERAGE_STATUSES),
            },
            "assertions": {"type": "array", "items": assertion},
        },
        "required": [
            "claim_surface_id",
            "claim_surface_digest",
            "coverage_status",
            "assertions",
        ],
        "additionalProperties": False,
    }
    tool = {
        "type": "function",
        "function": {
            "name": "submit_case_truth_reconciliation",
            "description": (
                "Classify claim surfaces against immutable case truth aliases."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "surface_assertions": {
                        "type": "array",
                        "items": surface,
                        "minItems": len(surfaces),
                        "maxItems": len(surfaces),
                    }
                },
                "required": ["surface_assertions"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
    return messages, tool


def validate_case_truth_reconciliation(
    payload: Mapping[str, Any],
    *,
    case_truth_packet: Mapping[str, Any],
    claim_document: Mapping[str, Any],
) -> dict[str, Any]:
    _require(
        isinstance(payload, Mapping) and set(payload) == {"surface_assertions"},
        "case_truth_reconciliation_fields_invalid",
    )
    packet_digest = str(case_truth_packet.get("case_truth_packet_digest") or "")
    document_digest = str(claim_document.get("claim_document_digest") or "")
    _require(
        packet_digest
        and document_digest
        and packet_digest
        == canonical_digest(
            {
                key: deepcopy(value)
                for key, value in case_truth_packet.items()
                if key != "case_truth_packet_digest"
            }
        )
        and document_digest
        == canonical_digest(
            {
                key: deepcopy(value)
                for key, value in claim_document.items()
                if key != "claim_document_digest"
            }
        ),
        "case_truth_reconciliation_binding_missing",
    )
    presence = {
        str(row["truth_alias"]): row
        for row in _rows(
            case_truth_packet.get("presence_catalog"),
            "case_truth_presence_catalog_invalid",
        )
    }
    gaps: dict[str, list[Mapping[str, Any]]] = {}
    for row in _rows(
        case_truth_packet.get("typed_gap_catalog"),
        "case_truth_gap_catalog_invalid",
    ):
        gaps.setdefault(str(row["truth_alias"]), []).append(row)
    bridges = {
        str(row["truth_alias"]): row
        for row in _rows(
            case_truth_packet.get("typed_bridge_boundary_catalog"),
            "case_truth_bridge_catalog_invalid",
        )
    }
    all_aliases = set(
        _strings(
            case_truth_packet.get("all_truth_aliases"),
            "case_truth_alias_catalog_invalid",
        )
    )
    _require(
        all_aliases == set(presence) | set(gaps) | set(bridges),
        "case_truth_alias_catalog_drift",
    )
    visibility: dict[str, dict[str, set[str]]] = {}
    for row in _rows(
        case_truth_packet.get("cell_visibility_matrix"),
        "case_truth_visibility_matrix_invalid",
    ):
        cell_id = str(row.get("cell_id") or "")
        _require(
            cell_id and cell_id not in visibility,
            "case_truth_visibility_matrix_invalid",
        )
        visibility[cell_id] = {
            "presence": set(row.get("visible_presence_aliases") or []),
            "gaps": set(row.get("visible_gap_aliases") or []),
            "bridges": set(row.get("visible_bridge_boundary_aliases") or []),
        }
    source_surfaces = {
        str(row["claim_surface_id"]): row
        for row in _rows(
            claim_document.get("claim_surfaces"),
            "case_truth_claim_surfaces_invalid",
        )
    }
    submitted = _rows(
        payload.get("surface_assertions"),
        "case_truth_reconciliation_surfaces_invalid",
    )
    _require(
        len(submitted) == len(source_surfaces),
        "case_truth_reconciliation_surface_coverage_invalid",
    )
    by_surface: dict[str, Mapping[str, Any]] = {}
    for row in submitted:
        _require(
            set(row)
            == {
                "claim_surface_id",
                "claim_surface_digest",
                "coverage_status",
                "assertions",
            },
            "case_truth_reconciliation_surface_fields_invalid",
        )
        surface_id = str(row.get("claim_surface_id") or "")
        _require(
            surface_id in source_surfaces and surface_id not in by_surface,
            "case_truth_reconciliation_surface_identity_invalid",
        )
        source = source_surfaces[surface_id]
        _require(
            str(row.get("claim_surface_digest") or "")
            == str(source.get("claim_surface_digest") or ""),
            "case_truth_reconciliation_surface_digest_drift",
        )
        by_surface[surface_id] = row
    _require(
        set(by_surface) == set(source_surfaces),
        "case_truth_reconciliation_surface_coverage_invalid",
    )

    findings: list[dict[str, Any]] = []
    trusted_surfaces = []
    assertion_count = 0
    for surface_id, source in source_surfaces.items():
        row = by_surface[surface_id]
        status = str(row.get("coverage_status") or "")
        _require(status in _COVERAGE_STATUSES, "case_truth_coverage_status_invalid")
        assertions = _rows(
            row.get("assertions"), "case_truth_assertions_invalid"
        )
        if status == "no_case_truth_claim":
            _require(not assertions, "case_truth_no_claim_with_assertions")
            if source.get("truth_assertion_required") is True:
                findings.append(
                    {
                        "finding_code": "required_material_surface_unmapped",
                        "claim_surface_id": surface_id,
                        "truth_alias": None,
                        "asserted_state": None,
                        "authoritative_state": "unmapped",
                    }
                )
        elif status == "claims_mapped":
            _require(bool(assertions), "case_truth_mapped_claims_missing")
        else:
            findings.append(
                {
                    "finding_code": "material_claim_unmapped",
                    "claim_surface_id": surface_id,
                    "truth_alias": None,
                    "asserted_state": None,
                    "authoritative_state": "unmapped",
                }
            )
        seen_aliases: set[str] = set()
        trusted_assertions = []
        for assertion in assertions:
            _require(
                set(assertion) == {"truth_alias", "asserted_state"},
                "case_truth_assertion_fields_invalid",
            )
            alias = str(assertion.get("truth_alias") or "")
            asserted = str(assertion.get("asserted_state") or "")
            _require(
                alias in all_aliases
                and alias not in seen_aliases
                and asserted in _ASSERTED_STATES,
                "case_truth_assertion_invalid",
            )
            seen_aliases.add(alias)
            assertion_count += 1
            has_presence = alias in presence
            has_gap = alias in gaps
            has_bridge = alias in bridges
            absence_authorized = (
                not has_presence
                and (
                    any(bool(item.get("case_absence_authorized")) for item in gaps.get(alias, []))
                    or bool(bridges.get(alias, {}).get("case_absence_authorized"))
                )
            )
            cell_id = source.get("cell_id")
            cell_visibility = visibility.get(str(cell_id), {}) if cell_id else {}
            locally_visible = (
                alias in cell_visibility.get("presence", set()) if cell_id else True
            )
            authoritative = (
                "present_with_typed_gap"
                if has_presence and (has_gap or has_bridge)
                else "present_in_current_case"
                if has_presence
                else "absent_from_current_case"
                if absence_authorized
                else "unresolved_without_absence_authority"
                if has_gap or has_bridge
                else "unknown"
            )
            finding_code = ""
            if asserted == "present_in_current_case" and not has_presence:
                finding_code = "asserted_present_without_reviewed_presence"
            elif (
                asserted == "present_in_current_case"
                and cell_id
                and not locally_visible
            ):
                finding_code = "asserted_present_outside_cell_visibility"
            elif asserted == "not_visible_in_current_cell" and not (
                cell_id and has_presence and not locally_visible
            ):
                finding_code = "asserted_cell_local_invisibility_invalid"
            elif asserted == "absent_from_current_case" and not absence_authorized:
                finding_code = (
                    "asserted_absent_but_present_in_case"
                    if has_presence
                    else "asserted_absent_without_typed_authority"
                )
            elif asserted == "unresolved_or_partially_covered" and not (
                has_gap or has_bridge
            ):
                finding_code = "asserted_unresolved_without_typed_gap"
            if finding_code:
                findings.append(
                    {
                        "finding_code": finding_code,
                        "claim_surface_id": surface_id,
                        "truth_alias": alias,
                        "asserted_state": asserted,
                        "authoritative_state": authoritative,
                    }
                )
            trusted_assertions.append(
                {
                    "truth_alias": alias,
                    "asserted_state": asserted,
                    "authoritative_state": authoritative,
                    "locally_visible": locally_visible,
                }
            )
        trusted_surfaces.append(
            {
                "claim_surface_id": surface_id,
                "claim_surface_digest": source["claim_surface_digest"],
                "coverage_status": status,
                "assertions": trusted_assertions,
            }
        )

    eligible = not findings
    unsigned = {
        "schema_version": CASE_TRUTH_RECONCILIATION_SCHEMA_VERSION,
        "status": (
            "case_truth_reconciled" if eligible else "case_truth_reconciliation_blocked"
        ),
        "case_truth_packet_digest": packet_digest,
        "claim_document_kind": str(claim_document.get("document_kind") or ""),
        "claim_document_binding_digest": str(
            claim_document.get("binding_digest") or ""
        ),
        "claim_document_digest": document_digest,
        "surface_assertion_count": assertion_count,
        "claim_surfaces_checked": len(trusted_surfaces),
        "surface_assertions": trusted_surfaces,
        "findings": findings,
        "downstream_eligible": eligible,
        "authority": {
            "semantic_classifier_created_financial_truth": False,
            "semantic_classifier_authored_or_repaired_research": False,
            "local_case_truth_adjudication_is_final": True,
            "qualified_human_content_review_still_required": True,
        },
    }
    return {
        **unsigned,
        "truth_reconciliation_digest": canonical_digest(unsigned),
    }


def require_eligible_truth_reconciliation(
    receipt: Mapping[str, Any],
    *,
    case_truth_packet: Mapping[str, Any],
    claim_document: Mapping[str, Any],
) -> None:
    unsigned = {
        key: deepcopy(value)
        for key, value in receipt.items()
        if key != "truth_reconciliation_digest"
    }
    _require(
        receipt.get("schema_version") == CASE_TRUTH_RECONCILIATION_SCHEMA_VERSION
        and receipt.get("status") == "case_truth_reconciled"
        and receipt.get("downstream_eligible") is True
        and receipt.get("findings") == []
        and receipt.get("case_truth_packet_digest")
        == case_truth_packet.get("case_truth_packet_digest")
        and receipt.get("claim_document_kind")
        == claim_document.get("document_kind")
        and receipt.get("claim_document_binding_digest")
        == claim_document.get("binding_digest")
        and receipt.get("claim_document_digest")
        == claim_document.get("claim_document_digest")
        and receipt.get("truth_reconciliation_digest") == canonical_digest(unsigned),
        "case_truth_reconciliation_not_eligible",
    )


__all__: Sequence[str] = (
    "CASE_TRUTH_DOCUMENT_SCHEMA_VERSION",
    "CASE_TRUTH_MODEL_VIEW_SCHEMA_VERSION",
    "CASE_TRUTH_PACKET_SCHEMA_VERSION",
    "CASE_TRUTH_RECONCILIATION_SCHEMA_VERSION",
    "CaseTruthReconciliationError",
    "compile_case_truth_packet",
    "compile_case_truth_model_view",
    "compile_case_truth_reconciliation_submission",
    "compile_cell_judgment_claim_document",
    "compile_synthesis_claim_document",
    "require_eligible_truth_reconciliation",
    "validate_case_truth_packet",
    "validate_case_truth_reconciliation",
)
