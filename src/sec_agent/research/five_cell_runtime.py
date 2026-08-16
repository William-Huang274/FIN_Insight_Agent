from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping, Sequence

from .bounded_finance_loop import compile_finance_judgment_tool
from .current_consumer import (
    CurrentResearchConsumerError,
    compile_current_research_messages,
    validate_current_research_evidence_route,
    validate_current_research_model_text,
)
from .reviewed_evidence_pack import canonical_digest


FIVE_CELL_SYNTHESIS_SCHEMA_VERSION = "fin_ia_five_cell_synthesis_v1_0"
FIVE_CELL_REPORT_SCHEMA_VERSION = "fin_ia_five_cell_research_report_v1_0"

_SYNTHESIS_FIELDS = {
    "overall_judgment",
    "confidence_basis",
    "inference_authority",
    "executive_thesis",
    "cross_cell_mechanism",
    "strongest_counterargument",
    "key_cell_ids",
    "cell_links",
    "evidence_refs",
    "numeric_refs",
    "numeric_relation_refs",
    "remaining_gap_refs",
    "what_would_change",
}
_WWC_FIELDS = {
    "observable",
    "direction",
    "time_horizon",
    "evidence_route",
    "threshold_numeric_ref",
}
_LINK_FIELDS = {
    "from_cell_id",
    "to_cell_id",
    "relation",
    "explanation",
}
_LINK_RELATIONS = {"supports", "limits", "conflicts", "independent"}


class FiveCellResearchError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise FiveCellResearchError(code)


def _unique_strings(
    value: object,
    *,
    allowed: set[str],
    code: str,
    minimum: int = 0,
) -> list[str]:
    _require(isinstance(value, list), code)
    rows = [str(item or "") for item in value]
    _require(
        len(rows) >= minimum
        and len(rows) == len(set(rows))
        and set(rows).issubset(allowed),
        code,
    )
    return rows


def _model_text(
    value: object,
    *,
    maximum: int,
    code: str,
    minimum: int = 12,
) -> str:
    try:
        return validate_current_research_model_text(
            value,
            maximum=maximum,
            code=code,
            minimum=minimum,
        )
    except CurrentResearchConsumerError as exc:
        raise FiveCellResearchError(exc.code) from exc


def _evidence_route(value: object, *, maximum: int, code: str) -> str:
    try:
        return validate_current_research_evidence_route(
            value,
            maximum=maximum,
            code=code,
        )
    except CurrentResearchConsumerError as exc:
        raise FiveCellResearchError(exc.code) from exc


def _cell_ids(research_input: Mapping[str, Any]) -> list[str]:
    values = [str(row["cell_id"]) for row in research_input["cells"]]
    _require(
        len(values) == 5 and len(values) == len(set(values)),
        "five_cell_scope_invalid",
    )
    return values


def compile_five_cell_analysis_messages(
    *,
    research_input: Mapping[str, Any],
    cell_id: str,
) -> tuple[dict[str, str], ...]:
    """Compile one cell-local analysis draft without granting submission authority."""

    strict_messages = compile_current_research_messages(
        research_input,
        required_cell_ids=[cell_id],
        submission_transport="final_tool",
    )
    visible = json.loads(strict_messages[1]["content"])
    rules = list(visible["rules"])
    rules[0] = (
        "Analyze this cell and prepare a concise draft for a later strict "
        "submission. Do not call a tool and do not treat this draft as business truth."
    )
    visible["rules"] = rules
    visible["analysis_stage"] = {
        "model_owns_analysis_and_judgment": True,
        "draft_is_not_a_validated_judgment": True,
        "later_submission_must_use_the_same_cell_local_authority": True,
        "harness_may_not_invent_or_rewrite_a_viewpoint": True,
    }
    return (
        {
            "role": "system",
            "content": (
                "You are a financial research analysis node. Work only from the "
                "cell-local reviewed Evidence, NumericFacts, typed relations, "
                "methods, graph context and gaps below. Separate fact, inference, "
                "alternative explanation and what would change. Produce a concise "
                "analysis draft, not a Tool Call and not a publishable report."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def compile_five_cell_submission(
    *,
    research_input: Mapping[str, Any],
    cell_id: str,
    analysis_draft: str,
) -> tuple[tuple[dict[str, str], ...], dict[str, Any]]:
    """Bind a model-owned draft to the unchanged strict cell contract."""

    draft = str(analysis_draft or "").strip()
    _require(
        24 <= len(draft) <= 16000,
        "five_cell_analysis_draft_invalid",
    )
    strict_messages = compile_current_research_messages(
        research_input,
        required_cell_ids=[cell_id],
        submission_transport="final_tool",
    )
    messages = (
        strict_messages[0],
        strict_messages[1],
        {"role": "assistant", "content": draft},
        {
            "role": "user",
            "content": (
                "Submit the final judgment now by calling the sole "
                "submit_research_judgment tool exactly once. Keep only claims and "
                "references supported by the unchanged cell-local authority above. "
                "The analysis draft is model-owned working text, not evidence; do "
                "not copy any unsupported statement from it."
            ),
        },
    )
    tool = compile_finance_judgment_tool(
        research_input=research_input,
        required_cell_ids=[cell_id],
        strict=True,
    )
    return messages, tool


def _selected_ref_sets(
    *,
    research_input: Mapping[str, Any],
    judgment_output: Mapping[str, Any],
) -> dict[str, set[str]]:
    expected_cells = set(_cell_ids(research_input))
    cells = judgment_output.get("cells")
    _require(
        isinstance(cells, list)
        and len(cells) == 5
        and {str(row.get("cell_id") or "") for row in cells} == expected_cells,
        "five_cell_judgment_coverage_invalid",
    )
    return {
        "cell_ids": expected_cells,
        "evidence_refs": {
            str(use["evidence_ref"])
            for row in cells
            for use in row["evidence_uses"]
        },
        "numeric_refs": {
            str(ref) for row in cells for ref in row["numeric_refs"]
        },
        "numeric_relation_refs": {
            str(ref)
            for row in cells
            for ref in row["numeric_relation_refs"]
        },
        "remaining_gap_refs": {
            str(ref)
            for row in cells
            for ref in row["remaining_gap_refs"]
        },
    }


def _synthesis_view(
    *,
    research_input: Mapping[str, Any],
    judgment_output: Mapping[str, Any],
    structured_deliverable: Mapping[str, Any],
) -> dict[str, Any]:
    selected = _selected_ref_sets(
        research_input=research_input,
        judgment_output=judgment_output,
    )
    cells = []
    for row in structured_deliverable["cells"]:
        cells.append(
            {
                "cell_id": row["cell_id"],
                "title_zh": row["title_zh"],
                "judgment_status": row["judgment_status"],
                "confidence_basis": row["confidence_basis"],
                "inference_authority": row["inference_authority"],
                "thesis_atom": row["thesis_atom"],
                "mechanism_atom": row["mechanism_atom"],
                "counterargument_atom": row["counterargument_atom"],
                "what_would_change": deepcopy(row["what_would_change"]),
                "evidence_uses": deepcopy(row["evidence_uses"]),
                "numeric_refs": list(row["numeric_refs"]),
                "numeric_relation_refs": list(row["numeric_relation_refs"]),
                "remaining_gap_refs": list(row["remaining_gap_refs"]),
                "numeric_facts": deepcopy(row["numeric_facts"]),
                "numeric_relations": deepcopy(row["numeric_relations"]),
            }
        )
    return {
        "schema_version": "fin_ia_five_cell_synthesis_input_v1_0",
        "case_identity": deepcopy(research_input["case_identity"]),
        "research_question": research_input["objective"]["raw_question"],
        "research_input_digest": research_input["research_input_digest"],
        "judgment_output_digest": judgment_output["judgment_output_digest"],
        "cells": cells,
        "allowed_refs": {
            key: sorted(value)
            for key, value in selected.items()
            if key != "cell_ids"
        },
        "authority": {
            "model_may_synthesize_only_validated_cell_judgments": True,
            "model_may_not_upgrade_a_gap_or_context_item_to_fact": True,
            "model_may_not_invent_a_cross_cell_causal_bridge": True,
            "exact_numeric_and_citation_surfaces_are_harness_rendered": True,
            "analysis_draft_is_not_business_truth": True,
            "qualified_human_review_required": True,
        },
    }


def compile_five_cell_synthesis_analysis_messages(
    *,
    research_input: Mapping[str, Any],
    judgment_output: Mapping[str, Any],
    structured_deliverable: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    view = _synthesis_view(
        research_input=research_input,
        judgment_output=judgment_output,
        structured_deliverable=structured_deliverable,
    )
    return (
        {
            "role": "system",
            "content": (
                "You are the lead financial research synthesizer. Integrate the "
                "five independently validated research cells into one coherent "
                "investment-research view. Preserve disagreement and evidence "
                "gaps. Do not turn coexistence into causality, do not invent a "
                "product-to-segment or product-to-company profit bridge, and do "
                "not submit a tool call yet. Produce a concise analysis draft."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                view, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def compile_five_cell_synthesis_submission(
    *,
    research_input: Mapping[str, Any],
    judgment_output: Mapping[str, Any],
    structured_deliverable: Mapping[str, Any],
    analysis_draft: str,
) -> tuple[tuple[dict[str, str], ...], dict[str, Any]]:
    draft = str(analysis_draft or "").strip()
    _require(
        24 <= len(draft) <= 20000,
        "five_cell_synthesis_draft_invalid",
    )
    analysis_messages = compile_five_cell_synthesis_analysis_messages(
        research_input=research_input,
        judgment_output=judgment_output,
        structured_deliverable=structured_deliverable,
    )
    messages = (
        analysis_messages[0],
        analysis_messages[1],
        {"role": "assistant", "content": draft},
        {
            "role": "user",
            "content": (
                "Call submit_five_cell_synthesis exactly once. Map only the "
                "supported parts of your draft into the strict schema. Use only "
                "the validated cell and reference sets above; the draft itself "
                "is not evidence."
            ),
        },
    )
    cell_ids = _cell_ids(research_input)
    selected = _selected_ref_sets(
        research_input=research_input,
        judgment_output=judgment_output,
    )

    def ref_array(refs: set[str]) -> dict[str, Any]:
        item: dict[str, Any] = (
            {"type": "string", "enum": sorted(refs)}
            if refs
            else {"type": "string", "pattern": "^$"}
        )
        value: dict[str, Any] = {
            "type": "array",
            "items": item,
            "uniqueItems": True,
        }
        if not refs:
            value["maxItems"] = 0
        return value

    def strict_object(properties: Mapping[str, Any], required=None):
        return {
            "type": "object",
            "properties": deepcopy(dict(properties)),
            "required": list(required or properties.keys()),
            "additionalProperties": False,
        }

    contract = research_input["model_output_contract"]
    link = strict_object(
        {
            "from_cell_id": {"type": "string", "enum": cell_ids},
            "to_cell_id": {"type": "string", "enum": cell_ids},
            "relation": {"type": "string", "enum": sorted(_LINK_RELATIONS)},
            "explanation": {
                "type": "string",
                "description": "Cross-cell relation without digits, dates, units, refs or citations.",
            },
        }
    )
    wwc = strict_object(
        {
            "observable": {"type": "string"},
            "direction": {
                "type": "string",
                "enum": list(contract["allowed_wwc_directions"]),
            },
            "time_horizon": {"type": "string"},
            "evidence_route": {"type": "string"},
            "threshold_numeric_ref": {
                "type": "string",
                "enum": ["", *sorted(selected["numeric_refs"])],
            },
        }
    )
    parameters = strict_object(
        {
            "overall_judgment": {
                "type": "string",
                "enum": list(contract["allowed_judgment_statuses"]),
            },
            "confidence_basis": {
                "type": "string",
                "enum": list(contract["allowed_confidence_bases"]),
            },
            "inference_authority": {
                "type": "string",
                "enum": list(contract["allowed_inference_authorities"]),
            },
            "executive_thesis": {"type": "string"},
            "cross_cell_mechanism": {"type": "string"},
            "strongest_counterargument": {"type": "string"},
            "key_cell_ids": {
                "type": "array",
                "items": {"type": "string", "enum": cell_ids},
                "minItems": 5,
                "maxItems": 5,
                "uniqueItems": True,
            },
            "cell_links": {
                "type": "array",
                "items": link,
                "minItems": 2,
                "maxItems": 10,
            },
            "evidence_refs": ref_array(selected["evidence_refs"]),
            "numeric_refs": ref_array(selected["numeric_refs"]),
            "numeric_relation_refs": ref_array(
                selected["numeric_relation_refs"]
            ),
            "remaining_gap_refs": ref_array(selected["remaining_gap_refs"]),
            "what_would_change": wwc,
        }
    )
    tool = {
        "type": "function",
        "function": {
            "name": "submit_five_cell_synthesis",
            "description": (
                "Submit one model-owned synthesis over five locally validated research cells."
            ),
            "parameters": parameters,
            "strict": True,
        },
    }
    return messages, tool


def validate_five_cell_synthesis(
    payload: Mapping[str, Any],
    *,
    research_input: Mapping[str, Any],
    judgment_output: Mapping[str, Any],
) -> dict[str, Any]:
    _require(
        isinstance(payload, Mapping) and set(payload) == _SYNTHESIS_FIELDS,
        "five_cell_synthesis_fields_invalid",
    )
    selected = _selected_ref_sets(
        research_input=research_input,
        judgment_output=judgment_output,
    )
    contract = research_input["model_output_contract"]
    overall = str(payload.get("overall_judgment") or "")
    confidence = str(payload.get("confidence_basis") or "")
    inference = str(payload.get("inference_authority") or "")
    _require(
        overall in contract["allowed_judgment_statuses"],
        "five_cell_synthesis_judgment_invalid",
    )
    _require(
        confidence in contract["allowed_confidence_bases"],
        "five_cell_synthesis_confidence_invalid",
    )
    _require(
        inference in contract["allowed_inference_authorities"],
        "five_cell_synthesis_inference_invalid",
    )
    executive = _model_text(
        payload.get("executive_thesis"),
        maximum=720,
        code="five_cell_synthesis_thesis_invalid",
    )
    mechanism = _model_text(
        payload.get("cross_cell_mechanism"),
        maximum=720,
        code="five_cell_synthesis_mechanism_invalid",
    )
    counter = _model_text(
        payload.get("strongest_counterargument"),
        maximum=720,
        code="five_cell_synthesis_counter_invalid",
    )
    cell_ids = _unique_strings(
        payload.get("key_cell_ids"),
        allowed=selected["cell_ids"],
        minimum=5,
        code="five_cell_synthesis_cell_coverage_invalid",
    )
    _require(
        set(cell_ids) == selected["cell_ids"],
        "five_cell_synthesis_cell_coverage_invalid",
    )
    raw_links = payload.get("cell_links")
    _require(
        isinstance(raw_links, list) and 2 <= len(raw_links) <= 10,
        "five_cell_synthesis_links_invalid",
    )
    links: list[dict[str, str]] = []
    signatures: set[tuple[str, str, str]] = set()
    for raw in raw_links:
        _require(
            isinstance(raw, Mapping) and set(raw) == _LINK_FIELDS,
            "five_cell_synthesis_links_invalid",
        )
        source = str(raw.get("from_cell_id") or "")
        target = str(raw.get("to_cell_id") or "")
        relation = str(raw.get("relation") or "")
        signature = (source, target, relation)
        _require(
            source in selected["cell_ids"]
            and target in selected["cell_ids"]
            and source != target
            and relation in _LINK_RELATIONS
            and signature not in signatures,
            "five_cell_synthesis_links_invalid",
        )
        signatures.add(signature)
        links.append(
            {
                "from_cell_id": source,
                "to_cell_id": target,
                "relation": relation,
                "explanation": _model_text(
                    raw.get("explanation"),
                    maximum=360,
                    code="five_cell_synthesis_link_text_invalid",
                ),
            }
        )
    evidence_refs = _unique_strings(
        payload.get("evidence_refs"),
        allowed=selected["evidence_refs"],
        code="five_cell_synthesis_evidence_refs_invalid",
    )
    numeric_refs = _unique_strings(
        payload.get("numeric_refs"),
        allowed=selected["numeric_refs"],
        code="five_cell_synthesis_numeric_refs_invalid",
    )
    relation_refs = _unique_strings(
        payload.get("numeric_relation_refs"),
        allowed=selected["numeric_relation_refs"],
        code="five_cell_synthesis_numeric_relation_refs_invalid",
    )
    gap_refs = _unique_strings(
        payload.get("remaining_gap_refs"),
        allowed=selected["remaining_gap_refs"],
        code="five_cell_synthesis_gap_refs_invalid",
    )
    raw_wwc = payload.get("what_would_change")
    _require(
        isinstance(raw_wwc, Mapping) and set(raw_wwc) == _WWC_FIELDS,
        "five_cell_synthesis_wwc_invalid",
    )
    threshold = str(raw_wwc.get("threshold_numeric_ref") or "")
    _require(
        not threshold or threshold in selected["numeric_refs"],
        "five_cell_synthesis_wwc_threshold_invalid",
    )
    wwc = {
        "observable": _model_text(
            raw_wwc.get("observable"),
            maximum=300,
            code="five_cell_synthesis_wwc_observable_invalid",
        ),
        "direction": str(raw_wwc.get("direction") or ""),
        "time_horizon": _model_text(
            raw_wwc.get("time_horizon"),
            maximum=160,
            code="five_cell_synthesis_wwc_horizon_invalid",
            minimum=4,
        ),
        "evidence_route": _evidence_route(
            raw_wwc.get("evidence_route"),
            maximum=240,
            code="five_cell_synthesis_wwc_route_invalid",
        ),
        "threshold_numeric_ref": threshold or None,
    }
    _require(
        wwc["direction"] in contract["allowed_wwc_directions"],
        "five_cell_synthesis_wwc_direction_invalid",
    )
    trusted = {
        "schema_version": FIVE_CELL_SYNTHESIS_SCHEMA_VERSION,
        "research_input_digest": research_input["research_input_digest"],
        "judgment_output_digest": judgment_output["judgment_output_digest"],
        "overall_judgment": overall,
        "confidence_basis": confidence,
        "inference_authority": inference,
        "executive_thesis": executive,
        "cross_cell_mechanism": mechanism,
        "strongest_counterargument": counter,
        "key_cell_ids": cell_ids,
        "cell_links": links,
        "evidence_refs": evidence_refs,
        "numeric_refs": numeric_refs,
        "numeric_relation_refs": relation_refs,
        "remaining_gap_refs": gap_refs,
        "what_would_change": wwc,
    }
    return {**trusted, "synthesis_digest": canonical_digest(trusted)}


def compile_five_cell_report(
    *,
    research_input: Mapping[str, Any],
    structured_deliverable: Mapping[str, Any],
    synthesis: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = {
        str(row["evidence_ref"]): row
        for row in research_input["evidence_cards"]
    }
    numeric = {
        str(row["numeric_ref"]): row
        for row in research_input["numeric_fact_cards"]
    }
    relations = {
        str(row["numeric_relation_ref"]): row
        for row in research_input["numeric_relation_cards"]
    }
    gaps = {
        str(row["gap_ref"]): row
        for row in research_input["residual_gap_cards"]
    }
    unsigned = {
        "schema_version": FIVE_CELL_REPORT_SCHEMA_VERSION,
        "status": "five_cell_internal_research_report_compiled",
        "case_identity": deepcopy(research_input["case_identity"]),
        "research_question": research_input["objective"]["raw_question"],
        "research_input_digest": research_input["research_input_digest"],
        "cell_workpaper_digest": structured_deliverable["deliverable_digest"],
        "cells": deepcopy(structured_deliverable["cells"]),
        "synthesis": deepcopy(dict(synthesis)),
        "synthesis_rendered": {
            "evidence": [deepcopy(evidence[ref]) for ref in synthesis["evidence_refs"]],
            "numeric_facts": [deepcopy(numeric[ref]) for ref in synthesis["numeric_refs"]],
            "numeric_relations": [
                deepcopy(relations[ref])
                for ref in synthesis["numeric_relation_refs"]
            ],
            "remaining_gaps": [deepcopy(gaps[ref]) for ref in synthesis["remaining_gap_refs"]],
        },
        "rendering_authority": {
            "model_authored_cells_and_synthesis": True,
            "harness_rendered_identity_numeric_citations_and_gaps": True,
            "harness_generated_research_conclusion": False,
            "qualified_human_review_required": True,
            "product_publication": False,
        },
        "known_boundary": (
            "This is an internal five-cell candidate report. Contract validity "
            "does not prove financial L1, absolute content quality, paired gain, "
            "qualified-human acceptance, generalization, S3 acceptance or release."
        ),
    }
    return {**unsigned, "report_digest": canonical_digest(unsigned)}


__all__ = [
    "FIVE_CELL_REPORT_SCHEMA_VERSION",
    "FIVE_CELL_SYNTHESIS_SCHEMA_VERSION",
    "FiveCellResearchError",
    "compile_five_cell_analysis_messages",
    "compile_five_cell_report",
    "compile_five_cell_submission",
    "compile_five_cell_synthesis_analysis_messages",
    "compile_five_cell_synthesis_submission",
    "validate_five_cell_synthesis",
]
