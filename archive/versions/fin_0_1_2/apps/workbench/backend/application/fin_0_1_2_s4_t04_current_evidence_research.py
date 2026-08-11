from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any, Mapping, Sequence

from apps.workbench.backend.application.bounded_agent_executor import (
    S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF,
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    S3ThreeCellBoundedAgentInputPack,
)
from apps.workbench.backend.application.case_service import CasePrincipal
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
    predict_work_unit_id,
)
from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (
    S4T01CompiledEntry,
)
from sec_agent.canonical_runtime.models import canonical_digest
from apps.workbench.backend.application.research_runtime import (
    S3ThreeCellPreparedExecution,
    predict_fin01_attempt_and_run_ids,
)


CONTRACT_REF = "fin_0_1_2.S4.T04.current_evidence_agentic_research_input:v1"
PACK_SCHEMA = "fin_ia_0_1_2_s4_t04_current_evidence_pack_v1_0"
EXPECTED_CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)
T03_SUCCESS_CODE = "three_request_current_evidence_candidate_pack_ready"
EVIDENCE_STATEMENT_MAX_CHARS = 300
T04_EXECUTION_ENVELOPE_SCHEMA = (
    "fin_ia_0_1_2_s4_t04_current_evidence_exact_execution_envelope_v1_0"
)
T04_MAXIMUM_INPUT_TOKENS = 108000
T04_INPUT_CAPACITY_CONTRACT_REF = (
    "fin_0_1_2.S4.T04.compiled_node_request_capacity:v1"
)


class Fin012S4T04EvidenceError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _date(value: Any, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise Fin012S4T04EvidenceError(code) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _digest_payload(value: Mapping[str, Any], digest_key: str) -> str:
    return canonical_digest({key: row for key, row in value.items() if key != digest_key})


def _numeric_projection(
    candidate: Mapping[str, Any], *, entity_ref: str
) -> dict[str, Any]:
    excerpt = str(candidate.get("excerpt") or "")
    structured = candidate.get("structured_numeric")
    if isinstance(structured, Mapping):
        metric_name = str(structured.get("metric_name") or "").strip()
        metric_family = str(structured.get("metric_family") or "").strip()
        value = str(structured.get("value") or "").strip()
        unit = str(structured.get("unit") or "").strip()
        period_value = str(structured.get("period") or "").strip()
        filed_value = str(structured.get("source_filed_at") or "").strip()
        published_value = str(structured.get("published_at") or "").strip()
        as_of_value = str(structured.get("as_of_date") or "").strip()
        snapshot_value = str(structured.get("snapshot_at") or "").strip()
        period_role = str(structured.get("period_role") or "").strip()
        period_start = str(structured.get("period_start") or "").strip()
        period_end = str(structured.get("period_end") or "").strip()
        duration_days = str(structured.get("duration_days") or "").strip()
        fiscal_year = str(structured.get("fiscal_year") or "").strip()
        fiscal_period = str(structured.get("fiscal_period") or "").strip()
        raw_fiscal_period = str(structured.get("raw_fiscal_period") or "").strip()
        if (
            metric_family not in {"revenue", "gross_profit", "operating_income"}
            or not metric_name
            or re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value) is None
            or not unit
            or not period_value
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", filed_value) is None
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", published_value) is None
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", as_of_value) is None
            or not snapshot_value
            or period_role != "annual"
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", period_start) is None
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", period_end) is None
            or not duration_days.isdigit()
            or not 330 <= int(duration_days) <= 380
            or not fiscal_year.isdigit()
            or fiscal_period != "FY"
        ):
            raise Fin012S4T04EvidenceError(
                "s4_t04_structured_numeric_candidate_invalid"
            )
    else:
        # The legacy text parser cannot recover duration or distinguish filing,
        # research-cutoff and snapshot time.  It is historical compatibility
        # evidence only and must not be promoted into the current truth chain.
        raise Fin012S4T04EvidenceError(
            "s4_t04_legacy_unstructured_numeric_candidate_not_current_authority"
        )
    payload = {
        "numeric_ref": str(candidate["locator"]),
        "candidate_id": str(candidate["candidate_id"]),
        "entity_ref": entity_ref,
        "program_cell_ids": [str(candidate["program_cell_id"])],
        "metric_name": metric_name.strip(),
        "metric_family": metric_family,
        "value": value,
        "unit": unit,
        "period": period_value,
        "period_role": period_role,
        "period_start": period_start,
        "period_end": period_end,
        "duration_days": duration_days,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "raw_fiscal_period": raw_fiscal_period,
        "source_filed_at": filed_value,
        "published_at": published_value,
        "as_of_date": as_of_value,
        "snapshot_at": snapshot_value,
        "source_url": str(candidate["source_url"]),
        "source_coordinate": str(candidate["locator"]),
        "citation": excerpt,
        "source_snapshot_ref": str(candidate["source_snapshot_ref"]),
        "source_snapshot_digest": str(candidate["source_snapshot_digest"]),
        "parser_adapter": str(candidate["parser_adapter"]),
        "parser_digest": str(candidate["parser_digest"]),
        "exact_value_authority": True,
        "authority_scope": (
            "consolidated_company_total_only_not_segment_product_or_forward_estimate"
        ),
        "writer_citable": False,
    }
    return {**payload, "numeric_row_digest": canonical_digest(payload)}


def _evidence_projection(
    candidate: Mapping[str, Any], *, entity_ref: str
) -> dict[str, Any]:
    excerpt = str(candidate["excerpt"]).strip()
    bounded_statement = (
        excerpt
        if len(excerpt) <= EVIDENCE_STATEMENT_MAX_CHARS
        else excerpt[: EVIDENCE_STATEMENT_MAX_CHARS - 1].rstrip() + "…"
    )
    source_role = str(candidate["candidate_role"])
    semantic_role = {
        "issuer_demand_statement": "issuer_demand_or_order_signal",
        "issuer_financial_statement": "issuer_financial_statement",
        "issuer_counterevidence_statement": "issuer_counterevidence",
    }.get(source_role)
    if semantic_role is None:
        raise Fin012S4T04EvidenceError("s4_t04_evidence_role_alias_unknown")
    payload = {
        "evidence_ref": f"current_evidence:{candidate['candidate_id']}",
        "candidate_id": str(candidate["candidate_id"]),
        "entity_ref": entity_ref,
        "program_cell_ids": [str(candidate["program_cell_id"])],
        "evidence_role": semantic_role,
        "source_candidate_role": source_role,
        "statement": bounded_statement,
        "title": str(candidate["title"]),
        "published_at": str(candidate["published_at"]),
        "source_url": str(candidate["source_url"]),
        "citation": str(candidate["locator"]),
        "parser_lineage": {
            "source_snapshot_ref": str(candidate["source_snapshot_ref"]),
            "source_snapshot_digest": str(candidate["source_snapshot_digest"]),
            "adapter": str(candidate["parser_adapter"]),
            "parser_digest": str(candidate["parser_digest"]),
        },
        "source_authority_rank": int(candidate["source_authority_rank"]),
        "claim_boundary": (
            "Issuer disclosure supports only the quoted company statement at the cited "
            "period and locator; causal, forward-looking and cross-company conclusions "
            "remain analyst judgments."
        ),
        "writer_citable": True,
        "domain_judgment_eligible": True,
    }
    return {**payload, "evidence_row_digest": canonical_digest(payload)}


def compile_current_nvda_evidence_pack(
    terminal: Mapping[str, Any],
    *,
    terminal_digest: str,
    t01_entry: S4T01CompiledEntry,
) -> dict[str, Any]:
    return compile_current_case_evidence_pack(
        terminal,
        terminal_digest=terminal_digest,
        t01_entry=t01_entry,
        case_key="NVDA",
    )


def compile_current_case_evidence_pack(
    terminal: Mapping[str, Any],
    *,
    terminal_digest: str,
    t01_entry: S4T01CompiledEntry,
    case_key: str,
) -> dict[str, Any]:
    """Promote only independently gated T03 candidates into a T04 input pack."""

    if (
        terminal.get("status") != "success"
        or terminal.get("code") != T03_SUCCESS_CODE
        or terminal.get("case_key") != case_key
        or terminal.get("T04_consumption_authorized") is not True
        or terminal.get("writer_citable_in_T03") is not False
        or terminal.get("domain_judgment_eligible_in_T03") is not False
        or t01_entry.request.case_key != case_key
    ):
        raise Fin012S4T04EvidenceError("s4_t04_terminal_or_case_boundary_invalid")
    results = terminal.get("request_results")
    if not isinstance(results, list) or len(results) != 3:
        raise Fin012S4T04EvidenceError("s4_t04_terminal_request_topology_invalid")
    by_cell: dict[str, Mapping[str, Any]] = {}
    evidence_rows: list[dict[str, Any]] = []
    numeric_rows: list[dict[str, Any]] = []
    source_snapshots: dict[str, dict[str, Any]] = {}
    candidate_ids: set[str] = set()
    cutoff = _date(t01_entry.request.as_of, "s4_t04_case_as_of_invalid")
    for result in results:
        request = result.get("request")
        if not isinstance(request, Mapping):
            raise Fin012S4T04EvidenceError("s4_t04_request_missing")
        cell_id = str(request.get("program_cell_id") or "")
        if cell_id in by_cell or cell_id not in EXPECTED_CELLS:
            raise Fin012S4T04EvidenceError("s4_t04_request_cell_invalid")
        candidates = result.get("accepted_candidates")
        if (
            result.get("status") != "current_evidence_candidates_ready"
            or result.get("typed_gap_codes") != []
            or not isinstance(candidates, list)
            or len(candidates) != 6
        ):
            raise Fin012S4T04EvidenceError("s4_t04_cell_candidate_pack_incomplete")
        by_cell[cell_id] = result
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise Fin012S4T04EvidenceError("s4_t04_candidate_shape_invalid")
            candidate_id = str(candidate.get("candidate_id") or "")
            if (
                candidate_id in candidate_ids
                or candidate.get("entity_ref") != case_key
                or candidate.get("program_cell_id") != cell_id
                or candidate.get("writer_citable") is not False
                or candidate.get("domain_judgment_eligible") is not False
                or not str(candidate.get("source_url") or "").startswith("https://")
                or not candidate.get("locator")
                or not re.fullmatch(r"[0-9a-f]{64}", str(candidate.get("source_snapshot_digest") or ""))
                or not re.fullmatch(r"[0-9a-f]{64}", str(candidate.get("parser_digest") or ""))
                or _date(candidate.get("published_at"), "s4_t04_candidate_date_invalid") > cutoff
            ):
                raise Fin012S4T04EvidenceError("s4_t04_candidate_gate_regression")
            candidate_ids.add(candidate_id)
            snapshot_digest = str(candidate["source_snapshot_digest"])
            source_snapshots.setdefault(
                snapshot_digest,
                {
                    "source_snapshot_ref": str(candidate["source_snapshot_ref"]),
                    "source_snapshot_digest": snapshot_digest,
                    "capture_kind": "T03_local_rows_before_projection",
                },
            )
            if candidate.get("exact_value_authority") is True:
                numeric_rows.append(
                    _numeric_projection(candidate, entity_ref=case_key)
                )
            else:
                evidence_rows.append(
                    _evidence_projection(candidate, entity_ref=case_key)
                )
    if tuple(sorted(by_cell)) != tuple(sorted(EXPECTED_CELLS)):
        raise Fin012S4T04EvidenceError("s4_t04_cell_set_invalid")
    if len(evidence_rows) != 15 or len(numeric_rows) != 3:
        raise Fin012S4T04EvidenceError("s4_t04_evidence_numeric_partition_invalid")

    typed_gaps = [
        {
            "program_cell_ids": ["demand_authenticity_and_sustainability"],
            "gap_code": "current_issuer_evidence_does_not_prove_future_demand_sustainability",
            "cannot_infer": "future order durability or deployment conversion",
        },
        {
            "program_cell_ids": ["value_and_profit_capture"],
            "gap_code": "company_total_numeric_does_not_attribute_AI_segment_profit_capture",
            "cannot_infer": "Data Center or accelerator product margin and incremental profit",
        },
        {
            "program_cell_ids": ["bottleneck_counterevidence_and_what_would_change"],
            "gap_code": "issuer_counterevidence_is_not_independent_external_corroboration",
            "cannot_infer": "independent probability or magnitude of bottlenecks",
        },
    ]
    body = {
        "schema_version": PACK_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "status": f"current_{case_key}_T03_candidates_promoted_for_T04_input_only",
        "case_key": case_key,
        "as_of": t01_entry.request.as_of,
        "natural_objective": t01_entry.request.objective,
        "t01_entry_digest": t01_entry.receipt.entry_digest,
        "t03_run_id": str(terminal["run_id"]),
        "t03_attempt_id": str(terminal["attempt_id"]),
        "t03_terminal_digest": terminal_digest,
        "source_snapshots": sorted(source_snapshots.values(), key=lambda row: row["source_snapshot_digest"]),
        "evidence_rows": sorted(evidence_rows, key=lambda row: row["evidence_ref"]),
        "numeric_rows": sorted(numeric_rows, key=lambda row: row["numeric_ref"]),
        "typed_gaps": typed_gaps,
        "promotion_boundary": {
            "T03_raw_candidates_rewritten": False,
            "T04_input_writer_citable_evidence_count": len(evidence_rows),
            "T04_exact_numeric_authority_count": len(numeric_rows),
            "model_generated_evidence": False,
            "rejected_candidate_promoted": False,
            "graph_context_promoted_as_evidence": False,
            "business_artifacts_created": 0,
        },
        "observed_counts": {
            "T03_accepted_candidates": 18,
            "T04_evidence_rows": len(evidence_rows),
            "T04_numeric_rows": len(numeric_rows),
            "typed_gaps": len(typed_gaps),
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
        },
    }
    return {**body, "evidence_pack_digest": canonical_digest(body)}


def validate_current_nvda_evidence_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    return validate_current_case_evidence_pack(pack, case_key="NVDA")


def validate_current_case_evidence_pack(
    pack: Mapping[str, Any], *, case_key: str | None = None
) -> dict[str, Any]:
    normalized = deepcopy(dict(pack))
    expected_case = case_key or str(normalized.get("case_key") or "")
    if expected_case not in {"DELL", "MU", "NVDA"}:
        raise Fin012S4T04EvidenceError("s4_t04_evidence_pack_case_invalid")
    if (
        normalized.get("schema_version") != PACK_SCHEMA
        or normalized.get("contract_ref") != CONTRACT_REF
        or normalized.get("case_key") != expected_case
        or normalized.get("status")
        != f"current_{expected_case}_T03_candidates_promoted_for_T04_input_only"
        or normalized.get("evidence_pack_digest") != _digest_payload(normalized, "evidence_pack_digest")
        or len(normalized.get("evidence_rows") or ()) != 15
        or len(normalized.get("numeric_rows") or ()) != 3
        or len(normalized.get("typed_gaps") or ()) != 3
    ):
        raise Fin012S4T04EvidenceError("s4_t04_evidence_pack_invalid")
    cutoff = _date(normalized["as_of"], "s4_t04_pack_as_of_invalid")
    evidence_refs = [str(row.get("evidence_ref") or "") for row in normalized["evidence_rows"]]
    numeric_refs = [str(row.get("numeric_ref") or "") for row in normalized["numeric_rows"]]
    if (
        len(set(evidence_refs)) != len(evidence_refs)
        or len(set(numeric_refs)) != len(numeric_refs)
        or any(
            row.get("entity_ref") != expected_case
            or row.get("writer_citable") is not True
            or row.get("domain_judgment_eligible") is not True
            or row.get("evidence_row_digest") != _digest_payload(row, "evidence_row_digest")
            or len(str(row.get("statement") or "")) > EVIDENCE_STATEMENT_MAX_CHARS
            or tuple(row.get("program_cell_ids") or ()) not in tuple((cell,) for cell in EXPECTED_CELLS)
            or not str(row.get("source_url") or "").startswith("https://")
            or not row.get("citation")
            or _date(row.get("published_at"), "s4_t04_pack_evidence_date_invalid") > cutoff
            for row in normalized["evidence_rows"]
        )
        or any(
            row.get("entity_ref") != expected_case
            or row.get("exact_value_authority") is not True
            or row.get("writer_citable") is not False
            or row.get("numeric_row_digest") != _digest_payload(row, "numeric_row_digest")
            or tuple(row.get("program_cell_ids") or ()) != ("value_and_profit_capture",)
            or not str(row.get("source_url") or "").startswith("https://")
            or not row.get("source_coordinate")
            or _date(row.get("source_filed_at"), "s4_t04_pack_numeric_date_invalid") > cutoff
            for row in normalized["numeric_rows"]
        )
    ):
        raise Fin012S4T04EvidenceError("s4_t04_pack_authority_invalid")
    return normalized


def _rows_for(rows: Sequence[Mapping[str, Any]], cell_id: str) -> list[dict[str, Any]]:
    return [deepcopy(dict(row)) for row in rows if cell_id in row.get("program_cell_ids", ())]


def _current_numeric_input(
    baseline_numeric: Mapping[str, Any],
    current_rows: Sequence[Mapping[str, Any]],
    typed_gaps: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebind the proven NVDA calculation surface to current T03 lineage."""

    current_by_ref = {str(row["numeric_ref"]): row for row in current_rows}
    selected: list[dict[str, Any]] = []
    old_to_new: dict[str, str] = {}
    for baseline_row in baseline_numeric.get("selected_financial_rows", ()):
        source_ref = str(baseline_row.get("evidence_ref") or "")
        current = current_by_ref.get(source_ref)
        selector = deepcopy(dict(baseline_row.get("selector") or {}))
        if (
            current is None
            or str(baseline_row.get("normalized_value")) != str(current.get("value"))
            or selector.get("entity_ref") != "NVDA"
            or str(selector.get("metric_family")) != str(current.get("metric_family"))
        ):
            raise Fin012S4T04EvidenceError(
                "s4_t04_numeric_baseline_not_current_terminal_exact"
            )
        row_body = {
            "numeric_ref": source_ref,
            "selector": selector,
            "entity_ref": "NVDA",
            "metric_family": str(current["metric_family"]),
            "period": str(selector["period"]),
            "source_period_label": str(current["period"]),
            "source_candidate_id": str(current["candidate_id"]),
            "evidence_ref": source_ref,
            "source_coordinate": str(current["source_coordinate"]),
            "source_url": str(current["source_url"]),
            "source_filed_at": str(current["source_filed_at"]),
            "source_snapshot_ref": str(current["source_snapshot_ref"]),
            "source_snapshot_digest": str(current["source_snapshot_digest"]),
            "parser_adapter": str(current["parser_adapter"]),
            "parser_digest": str(current["parser_digest"]),
            "normalized_value": str(current["value"]),
            "scale_multiplier": 1,
            "exact_value_authority": True,
            "selection_status": "exact_current_source_match",
            "authority_scope": str(current["authority_scope"]),
            "writer_citable": False,
        }
        row_digest = canonical_digest(row_body)
        row_id = f"s4_t04_current_financial_row_{row_digest[:24]}"
        old_to_new[str(baseline_row["financial_row_id"])] = row_id
        selected.append(
            {
                "financial_row_id": row_id,
                "financial_row_digest": row_digest,
                **row_body,
            }
        )
    if len(selected) != 3 or len(current_by_ref) != 3:
        raise Fin012S4T04EvidenceError("s4_t04_current_numeric_cardinality_invalid")

    derived: list[dict[str, Any]] = []
    for baseline_metric in baseline_numeric.get("derived_metrics", ()):
        metric_body = deepcopy(dict(baseline_metric))
        metric_body.pop("derived_metric_id", None)
        metric_body.pop("derived_metric_digest", None)
        inputs: list[dict[str, Any]] = []
        for item in metric_body.get("inputs", ()):
            updated = deepcopy(dict(item))
            old_ref = str(updated.get("financial_row_ref") or "")
            if old_ref not in old_to_new:
                raise Fin012S4T04EvidenceError(
                    "s4_t04_derived_metric_input_not_current"
                )
            updated["financial_row_ref"] = old_to_new[old_ref]
            inputs.append(updated)
        metric_body["inputs"] = inputs
        metric_body["entity_ref"] = "NVDA"
        metric_body["period"] = str(selected[0]["period"])
        metric_body["authority_scope"] = (
            "deterministically_recomputed_from_current_T03_exact_company_totals"
        )
        metric_digest = canonical_digest(metric_body)
        derived.append(
            {
                "derived_metric_id": (
                    f"s4_t04_current_derived_metric_{metric_digest[:24]}"
                ),
                "derived_metric_digest": metric_digest,
                **metric_body,
            }
        )
    if len(derived) != 2:
        raise Fin012S4T04EvidenceError("s4_t04_current_derived_metric_cardinality_invalid")

    fundamental = deepcopy(dict(baseline_numeric.get("fundamental_decision_cell") or {}))
    fundamental.pop("fundamental_cell_id", None)
    fundamental.pop("fundamental_cell_digest", None)
    fundamental.update(
        {
            "selected_financial_row_refs": [row["financial_row_id"] for row in selected],
            "derived_metric_refs": [row["derived_metric_id"] for row in derived],
            "availability": "current_exact_company_total_numeric_with_typed_segment_gap",
            "typed_cannot_infer": [str(row["gap_code"]) for row in typed_gaps],
            "support_boundary": (
                "Current SEC CompanyFacts rows support consolidated FY2025 margins only; "
                "AI product and segment profit attribution remains prohibited."
            ),
        }
    )
    fundamental_digest = canonical_digest(fundamental)
    return {
        "fundamental_decision_cell": {
            "fundamental_cell_id": f"s4_t04_current_fundamental_{fundamental_digest[:24]}",
            "fundamental_cell_digest": fundamental_digest,
            **fundamental,
        },
        "selected_financial_rows": selected,
        "derived_metrics": derived,
    }


def compile_current_nvda_agent_input(
    baseline: S3ThreeCellBoundedAgentInputPack,
    pack: Mapping[str, Any],
    *,
    t01_entry: S4T01CompiledEntry,
    verifier_input_contract_ref: str = (
        S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF
    ),
) -> S3ThreeCellBoundedAgentInputPack:
    """Replace the historical fixture fact surface while preserving proven Agent contracts."""

    current = validate_current_nvda_evidence_pack(pack)
    if baseline.company != "NVDA" or t01_entry.request.case_key != "NVDA":
        raise Fin012S4T04EvidenceError("s4_t04_baseline_case_invalid")
    baseline_cells = {str(row["program_cell_id"]): row for row in baseline.cell_inputs}
    t01_cells = {str(row["program_cell_id"]): str(row["objective"]) for row in t01_entry.request.program_cells}
    cells: list[dict[str, Any]] = []
    baseline_value = baseline_cells["value_and_profit_capture"]["numeric_input"]

    for cell_id in baseline.program_cell_ids:
        base = baseline_cells[cell_id]
        evidence_rows = _rows_for(current["evidence_rows"], cell_id)
        numeric_rows = _rows_for(current["numeric_rows"], cell_id)
        gaps = _rows_for(current["typed_gaps"], cell_id)
        evidence_refs = sorted(str(row["evidence_ref"]) for row in evidence_rows)
        numeric_refs = sorted(str(row["numeric_ref"]) for row in numeric_rows)
        promotion_payload = {
            "program_cell_id": cell_id,
            "decision": "accept_current_issuer_bound_rows_for_T04_input",
            "accepted_evidence_refs": evidence_refs,
            "numeric_refs": numeric_refs,
            "typed_gap_codes": [str(row["gap_code"]) for row in gaps],
            "evidence_gate_owner_ref": CONTRACT_REF,
            "runtime_promotion_authorized": True,
            "writer_citable": True,
            "judgment_eligible": True,
            "persistence_authorized": False,
        }
        promotion = {
            **promotion_payload,
            "assessment_id": f"s4_t04_promotion_{canonical_digest(promotion_payload)[:24]}",
            "assessment_digest": canonical_digest(promotion_payload),
        }
        candidate_payload = {
            "program_cell_id": cell_id,
            "status": "current_source_grounded_rows_approved_for_T04_input",
            "candidates": evidence_rows,
            "candidate_count": len(evidence_rows),
            "request_digest": canonical_digest(
                (current["t03_terminal_digest"], cell_id)
            ),
            "execution_admission": "T03_exact_live_consumed_terminal_bound",
            "persistence_admission": "T04_business_execution_required",
        }
        candidate_bundle = {
            **candidate_payload,
            "bundle_id": f"s4_t04_candidate_bundle_{canonical_digest(candidate_payload)[:24]}",
            "bundle_digest": canonical_digest(candidate_payload),
        }
        if cell_id == "value_and_profit_capture":
            numeric_input = _current_numeric_input(baseline_value, numeric_rows, gaps)
            numeric_authority_refs = [
                str(row["numeric_ref"])
                for row in numeric_input["selected_financial_rows"]
            ] + [
                str(row["derived_metric_id"])
                for row in numeric_input["derived_metrics"]
            ]
        else:
            numeric_input = deepcopy(base["numeric_input"])
            numeric_authority_refs = []
        cells.append(
            {
                "program_cell_id": cell_id,
                "runtime_branch": {
                    "program_cell_id": cell_id,
                    "owner_role": base["runtime_branch"].get("owner_role"),
                    "decision_question": t01_cells[cell_id],
                    "branch_state": "current_source_grounded_exact_input_ready",
                    "observation": {
                        "accepted_evidence_count": len(evidence_rows),
                        "exact_numeric_count": len(numeric_rows),
                        "typed_gap_count": len(gaps),
                    },
                },
                "role_contexts": [
                    {
                        "target_node": "domain_specialist",
                        "authority": {
                            "case_ticker": "NVDA",
                            "current_evidence_pack_digest": current["evidence_pack_digest"],
                            "source_or_numeric_rows_admitted": len(evidence_rows) + len(numeric_rows),
                        },
                    },
                    {
                        "target_node": "evidence_operator",
                        "authority": {
                            "T03_terminal_digest": current["t03_terminal_digest"],
                            "network_execution_authorized": False,
                        },
                    },
                ],
                "evidence_input": {
                    "program_cell_id": cell_id,
                    "route_outcome": "T03_current_rows_promoted_by_T04_gate",
                    "candidate_bundle": candidate_bundle,
                    "promotion_assessment": promotion,
                    "sourcehunter_boundary": {
                        "status": "already_executed_in_bound_T03_terminal",
                        "terminal_digest": current["t03_terminal_digest"],
                        "exact_network_admission_required": False,
                        "network_execution_authorized": False,
                        "external_tool_execution_authorized": False,
                    },
                },
                "numeric_input": numeric_input,
                "graph_context_input": {
                    "decision_cell": {
                        "program_cell_id": cell_id,
                        "typed_gaps": [str(row["gap_code"]) for row in gaps],
                    },
                    "product_industry_inputs": [],
                    "skill_contracts": [],
                    "graph_edges": [],
                    "market_price_in_contexts": [],
                    "risk_contexts": [
                        row for row in evidence_rows
                        if row["evidence_role"] == "issuer_counterevidence"
                    ],
                },
                "authority_refs": {
                    "accepted_evidence_refs": evidence_refs,
                    "numeric_refs": sorted(numeric_authority_refs),
                    "candidate_refs_not_evidence": [],
                    "graph_context_refs_not_evidence": [],
                },
            }
        )

    input_head_digest = canonical_digest(
        (
            t01_entry.receipt.entry_digest,
            current["evidence_pack_digest"],
            baseline.case_id,
            baseline.case_version,
        )
    )
    lineage = deepcopy(baseline.lineage)
    lineage["T02_runtime_plan"] = {
        "version_ref": t01_entry.runtime_binding.contract_ref,
        "digest": t01_entry.receipt.entry_digest,
    }
    lineage["T03_evidence_route_plan"] = {
        "version_ref": "fin_0_1_2.S4.T03.live_current_search_terminal:v1",
        "digest": str(current["t03_terminal_digest"]),
    }
    lineage["T04_financial_pack"] = {
        "version_ref": CONTRACT_REF,
        "digest": str(current["evidence_pack_digest"]),
    }
    lineage["T05_graph_pack"] = {
        "version_ref": "fin_0_1_2.S4.T04.context_only_empty_graph:v1",
        "digest": canonical_digest((current["evidence_pack_digest"], "no_graph_promotion")),
    }
    paired = deepcopy(baseline.paired_baseline_contract)
    paired["shared_input_head_digest"] = input_head_digest
    verifier_contract = deepcopy(baseline.verifier_contract)
    if verifier_input_contract_ref == (
        S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF
    ):
        verifier_contract.update(
            {
                "input_contract_ref": verifier_input_contract_ref,
                "request_capacity_contract_ref": T04_INPUT_CAPACITY_CONTRACT_REF,
                "full_local_payload_remains_validation_authority": True,
                "model_view_omits_repeated_runtime_projections_only": True,
            }
        )
    elif verifier_input_contract_ref != "fin01.s3.owner_grade_verifier_input:v2":
        raise Fin012S4T04EvidenceError(
            "s4_t04_verifier_input_contract_unsupported"
        )
    draft = baseline.model_copy(
        update={
            "query": t01_entry.request.objective,
            "as_of": t01_entry.request.as_of,
            "decision_surface_contract_ref": CONTRACT_REF,
            "input_head_digest": input_head_digest,
            "lineage": lineage,
            "cell_inputs": tuple(cells),
            "verifier_contract": verifier_contract,
            "paired_baseline_contract": paired,
            "s4_case_runtime": None,
        }
    )
    return draft.model_copy(
        update={
            "input_digest": canonical_digest(
                draft.model_dump(mode="json", exclude={"input_digest"})
            )
        }
    )


def prepare_current_nvda_agent_execution(
    baseline: S3ThreeCellPreparedExecution,
    pack: Mapping[str, Any],
    *,
    t01_entry: S4T01CompiledEntry,
    principal: CasePrincipal,
    execution_identity: str,
    attempt_no: int = 1,
    verifier_input_contract_ref: str = (
        S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF
    ),
) -> S3ThreeCellPreparedExecution:
    """Bind the current T04 input to fresh WorkUnit/Attempt/Run identities."""

    if not execution_identity.strip():
        raise Fin012S4T04EvidenceError("s4_t04_execution_identity_missing")
    first = compile_current_nvda_agent_input(
        baseline.input_pack,
        pack,
        t01_entry=t01_entry,
        verifier_input_contract_ref=verifier_input_contract_ref,
    )
    second = compile_current_nvda_agent_input(
        baseline.input_pack,
        pack,
        t01_entry=t01_entry,
        verifier_input_contract_ref=verifier_input_contract_ref,
    )
    if first.model_dump(mode="json") != second.model_dump(mode="json"):
        raise Fin012S4T04EvidenceError("s4_t04_current_input_double_compile_mismatch")
    work_unit_id = predict_work_unit_id(
        tenant_id=principal.tenant_id,
        project_id=principal.project_id,
        case_id=first.case_id,
        contract_version_id=CONTRACT_REF,
        work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        execution_identity=execution_identity,
    )
    attempt_id, research_run_id = predict_fin01_attempt_and_run_ids(
        work_unit_id=work_unit_id,
        execution_profile_version_ref=S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
        attempt_no=attempt_no,
    )
    digest_payload = {
        "case_id": first.case_id,
        "case_version": first.case_version,
        "decision_surface_contract_ref": CONTRACT_REF,
        "work_unit_id": work_unit_id,
        "attempt_id": attempt_id,
        "research_run_id": research_run_id,
        "execution_identity": execution_identity,
        "input_digest": first.input_digest,
    }
    return S3ThreeCellPreparedExecution(
        **digest_payload,
        input_pack=first,
        preparation_digest=canonical_digest(digest_payload),
        observed_counts={
            "canonical_writes": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
    )


def compile_current_t04_execution_envelope(
    prepared: S3ThreeCellPreparedExecution,
    pack: Mapping[str, Any],
    *,
    admission_ref: str,
    maximum_input_tokens: int = T04_MAXIMUM_INPUT_TOKENS,
) -> dict[str, Any]:
    """Compile the exact-once T04 adapter envelope consumed by the proven runner."""

    current = validate_current_nvda_evidence_pack(pack)
    if prepared.input_pack.lineage["T04_financial_pack"]["digest"] != current[
        "evidence_pack_digest"
    ]:
        raise Fin012S4T04EvidenceError("s4_t04_envelope_pack_lineage_mismatch")
    hard_budget = {
        "semantic_model_calls": 9,
        "provider_calls": 9,
        "execution_network_calls": 9,
        "maximum_transport_attempts_per_call": 1,
        "retry_budget": 0,
        "fallback_budget": 0,
        "provider_hopping_budget": 0,
        "maximum_input_tokens": maximum_input_tokens,
        "maximum_output_tokens": 10000,
        "maximum_total_cost_usd": 0.06,
        "maximum_wall_clock_seconds": 900,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_case_head_writes": 0,
        "failed_output_business_promotions": 0,
    }
    body = {
        "schema_version": T04_EXECUTION_ENVELOPE_SCHEMA,
        "status": "fresh_T04_exact_execution_not_started",
        "admission_ref": admission_ref,
        "current_evidence": {
            "evidence_pack_digest": current["evidence_pack_digest"],
            "t03_terminal_digest": current["t03_terminal_digest"],
            "evidence_numeric_gap_counts": [
                len(current["evidence_rows"]),
                len(current["numeric_rows"]),
                len(current["typed_gaps"]),
            ],
        },
        "fresh_t03": {
            "execution_identity": prepared.execution_identity,
            "work_unit_id": prepared.work_unit_id,
            "attempt_id": prepared.attempt_id,
            "research_run_id": prepared.research_run_id,
            "input_digest": prepared.input_digest,
            "preparation_digest": prepared.preparation_digest,
        },
        "hard_budget": hard_budget,
        **(
            {
                "input_capacity_contract": {
                    "contract_ref": T04_INPUT_CAPACITY_CONTRACT_REF,
                    "maximum_input_tokens": T04_MAXIMUM_INPUT_TOKENS,
                    "cost_derived_absolute_maximum_input_tokens": 117931,
                    "pricing_assumption_usd_per_million": {
                        "input_cache_miss": 0.435,
                        "output": 0.87,
                    },
                    "reserved_maximum_output_tokens": 10000,
                    "maximum_total_cost_usd": 0.06,
                    "minimum_cost_headroom_usd": 0.00432,
                    "requires_zero_call_full_chain_capacity_proof": True,
                }
            }
            if maximum_input_tokens == T04_MAXIMUM_INPUT_TOKENS
            else {}
        ),
        "observed_counts": {
            "credential_reads_or_probes": 0,
            "admissions_consumed": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "business_artifacts": 0,
        },
        "business_promotable": False,
    }
    return {**body, "envelope_digest": canonical_digest(body)}


__all__ = [
    "CONTRACT_REF",
    "Fin012S4T04EvidenceError",
    "compile_current_case_evidence_pack",
    "compile_current_nvda_agent_input",
    "compile_current_nvda_evidence_pack",
    "compile_current_t04_execution_envelope",
    "prepare_current_nvda_agent_execution",
    "validate_current_nvda_evidence_pack",
    "validate_current_case_evidence_pack",
]
