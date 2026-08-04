from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest


PRODUCT_SURFACE_CONTRACT_REF = (
    "fin_0_1_2.s3_t04.verified_final_delivery_surface:v1"
)
FINAL_PREVIEW_VERIFIER_CONTRACT_REF = (
    "fin_0_1_2.s3_t04.local_final_delivery_verifier:v1"
)
FIXTURE_EVIDENCE_QUALIFICATION_CONTRACT_REF = (
    "fin_0_1_2.s3_t04.fixture_evidence_qualification:v1"
)
EXPECTED_CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)
_INTERNAL_DELIVERY_TOKENS = (
    "__company_total__",
    "FY2025-FY",
)
_METRIC_LABELS_ZH_CN = {
    "revenue": "营收",
    "gross_profit": "毛利润",
    "operating_income": "营业利润",
    "gross_margin": "毛利率",
    "operating_margin": "营业利润率",
}


class S3T04ProductSurfaceError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S3T04ProductSurfaceError(code)


def _artifact_map(
    execution_result: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows = execution_result.get("artifacts")
    _require(isinstance(rows, list), "s3_t04_product_artifacts_required")
    mapped: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        _require(
            isinstance(row, Mapping),
            "s3_t04_product_artifact_row_invalid",
        )
        artifact_type = str(row.get("artifact_type") or "")
        payload = row.get("payload")
        _require(
            artifact_type
            and artifact_type not in mapped
            and isinstance(payload, Mapping),
            "s3_t04_product_artifact_payload_invalid",
        )
        mapped[artifact_type] = payload
    return mapped


def _claim_key(ref: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(ref.get("program_cell_id") or ""),
        str(ref.get("local_id") or ref.get("claim_id") or ""),
    )


def _normalize_period(period: str) -> str:
    match = re.fullmatch(r"(FY\d{4})-FY", period)
    return match.group(1) if match else period


def _format_exact_number(value: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise S3T04ProductSurfaceError(
            "s3_t04_delivery_numeric_value_invalid"
        ) from exc
    if number == number.to_integral_value():
        return f"{number:,.0f}"
    return f"{number:f}"


def _canonical_numeric_clause(row: Mapping[str, Any]) -> str:
    operator = {
        "exact": "=",
        "equals": "=",
        "greater_than": ">",
        "greater_than_or_equal": ">=",
        "less_than": "<",
        "less_than_or_equal": "<=",
    }.get(
        str(row.get("comparison_operator") or ""),
        str(row.get("comparison_operator") or ""),
    )
    value = str(row.get("exact_value") or "")
    unit = str(row.get("unit") or "")
    currency = str(row.get("currency") or "")
    if unit == "percent":
        rendered_value = f"{value}%"
    else:
        prefix = f"{currency} " if currency else ""
        rendered_value = f"{prefix}{value} {unit}".strip()
    return (
        f"{row.get('entity_ref')} {row.get('business_scope_ref')} "
        f"{row.get('period')} {row.get('metric_family')} {operator} "
        f"{rendered_value}"
    )


def _delivery_numeric_clause(row: Mapping[str, Any]) -> str:
    operator = {
        "exact": "=",
        "equals": "=",
        "greater_than": ">",
        "greater_than_or_equal": ">=",
        "less_than": "<",
        "less_than_or_equal": "<=",
    }.get(
        str(row.get("comparison_operator") or ""),
        str(row.get("comparison_operator") or ""),
    )
    scope = str(row.get("business_scope_ref") or "")
    if scope == "__company_total__":
        scope = "公司整体"
    period = _normalize_period(str(row.get("period") or ""))
    metric = _METRIC_LABELS_ZH_CN.get(
        str(row.get("metric_family") or ""),
        str(row.get("metric_family") or "").replace("_", " "),
    )
    value = _format_exact_number(str(row.get("exact_value") or ""))
    unit = str(row.get("unit") or "")
    currency = str(row.get("currency") or "")
    if unit == "percent":
        rendered_value = f"{value}%"
    elif currency and unit == currency:
        rendered_value = f"{currency} {value}"
    elif currency and unit:
        rendered_value = f"{currency} {value} {unit}"
    elif unit:
        rendered_value = f"{value} {unit}"
    else:
        rendered_value = value
    return (
        f"{row.get('entity_ref')} {scope} {period} "
        f"{metric} {operator} {rendered_value}"
    )


def _numeric_rows(
    numeric_artifact: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for projection in numeric_artifact.get(
        "case_numeric_authority_projections", ()
    ):
        _require(
            isinstance(projection, Mapping),
            "s3_t04_numeric_projection_invalid",
        )
        for row in projection.get("rows", ()):
            _require(
                isinstance(row, Mapping),
                "s3_t04_numeric_projection_row_invalid",
            )
            ref = str(row.get("numeric_ref") or "")
            _require(
                ref and ref not in rows,
                "s3_t04_numeric_ref_duplicate",
            )
            rows[ref] = row
    return rows


def _fixture_evidence_qualification(
    *,
    evidence_artifact: Mapping[str, Any],
    specialists: Sequence[Mapping[str, Any]],
    input_cells: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    evidence_fact_refs = {
        str(ref)
        for row in evidence_artifact.get("agent_fact_rows", ())
        if isinstance(row, Mapping) and row.get("support_type") == "Evidence"
        for ref in row.get("support_refs", ())
    }
    cell_results: list[dict[str, Any]] = []
    qualified_cells = 0
    for specialist in specialists:
        cell_id = str(specialist.get("program_cell_id") or "")
        input_cell = input_cells[cell_id]
        authority = input_cell.get("authority_refs") or {}
        accepted = {
            str(ref) for ref in authority.get("accepted_evidence_refs", ())
        }
        candidate_only = {
            str(ref)
            for ref in authority.get("candidate_refs_not_evidence", ())
        }
        evidence_facts = [
            row
            for row in specialist.get("fact_layer", ())
            if isinstance(row, Mapping)
            and row.get("support_type") == "Evidence"
        ]
        used_refs = {
            str(ref)
            for row in evidence_facts
            for ref in row.get("support_refs", ())
        }
        _require(
            used_refs.issubset(accepted)
            and accepted.issubset(evidence_fact_refs | used_refs),
            "s3_t04_unqualified_evidence_promotion_detected",
        )
        _require(
            accepted.isdisjoint(candidate_only),
            "s3_t04_candidate_promoted_without_evidence_gate",
        )
        qualified = bool(evidence_facts)
        qualified_cells += int(qualified)
        cell_results.append(
            {
                "program_cell_id": cell_id,
                "qualified_evidence_fact_count": len(evidence_facts),
                "accepted_evidence_refs": sorted(accepted),
                "candidate_refs_not_evidence": sorted(candidate_only),
                "status": (
                    "qualified_promoted_evidence_present"
                    if qualified
                    else "not_qualified_candidate_metadata_or_no_evidence_only"
                ),
            }
        )
    body = {
        "contract_ref": FIXTURE_EVIDENCE_QUALIFICATION_CONTRACT_REF,
        "status": (
            "pass_three_cell_promoted_evidence"
            if qualified_cells == len(EXPECTED_CELLS)
            else "blocked_requires_promoted_evidence_not_candidate_metadata"
        ),
        "qualified_evidence_cells": qualified_cells,
        "total_cells": len(EXPECTED_CELLS),
        "candidate_metadata_promotion_allowed": False,
        "current_numeric_only_fact_cell_does_not_count_as_evidence_cell": True,
        "cells": cell_results,
    }
    return {**body, "qualification_digest": canonical_digest(body)}


def materialize_verified_product_surface(
    *,
    execution_result: Mapping[str, Any],
    input_pack: Mapping[str, Any],
) -> dict[str, Any]:
    """Materialize and locally verify the final analyst-facing T04 surface.

    The function never edits the immutable exact-live artifacts. It converts
    only already-authorized numeric rows into delivery text, specializes WWC
    thresholds from the frozen per-cell product contract, and refuses to turn
    candidate metadata or graph hypotheses into Evidence.
    """

    _require(
        execution_result.get("status") == "success"
        and execution_result.get("business_promotable") is True,
        "s3_t04_successful_exact_result_required",
    )
    artifacts = _artifact_map(execution_result)
    required_types = {
        "bounded_agent_evidence",
        "bounded_agent_judgment",
        "bounded_agent_manifest",
        "bounded_agent_numeric",
        "bounded_agent_report",
        "bounded_agent_verification",
    }
    _require(
        required_types.issubset(artifacts),
        "s3_t04_required_artifacts_missing",
    )
    manifest = artifacts["bounded_agent_manifest"]
    _require(
        manifest.get("case_ticker") == "NVDA",
        "s3_t04_current_case_must_be_NVDA",
    )
    judgment = artifacts["bounded_agent_judgment"]
    specialists = judgment.get("specialist_outputs")
    _require(
        isinstance(specialists, list)
        and tuple(
            str(row.get("program_cell_id") or "") for row in specialists
        )
        == EXPECTED_CELLS,
        "s3_t04_specialist_cell_order_invalid",
    )
    input_rows = input_pack.get("cell_inputs")
    _require(
        isinstance(input_rows, list),
        "s3_t04_input_cells_required",
    )
    input_cells = {
        str(row.get("program_cell_id") or ""): row
        for row in input_rows
        if isinstance(row, Mapping)
    }
    _require(
        tuple(input_cells) == EXPECTED_CELLS,
        "s3_t04_input_cell_order_invalid",
    )
    numeric_rows = _numeric_rows(artifacts["bounded_agent_numeric"])
    source_report = artifacts["bounded_agent_report"].get("report")
    _require(
        isinstance(source_report, Mapping),
        "s3_t04_source_report_required",
    )
    source_sections = {
        str(row.get("program_cell_id") or ""): row
        for row in source_report.get("sections", ())
        if isinstance(row, Mapping)
    }
    _require(
        tuple(source_sections) == EXPECTED_CELLS,
        "s3_t04_report_cell_order_invalid",
    )

    preview_sections: list[dict[str, Any]] = []
    rendered_texts: list[str] = []
    specialized_task_count = 0
    numeric_only_qualification_count = 0
    for specialist in specialists:
        cell_id = str(specialist["program_cell_id"])
        section = source_sections[cell_id]
        rendering_by_claim = {
            _claim_key(row.get("claim_ref") or {}): row
            for row in section.get("claim_renderings", ())
            if isinstance(row, Mapping)
        }
        facts = {
            str(row.get("fact_id") or ""): row
            for row in specialist.get("fact_layer", ())
            if isinstance(row, Mapping)
        }
        claims: list[dict[str, Any]] = []
        for claim in specialist.get("judgment_layer", ()):
            _require(
                isinstance(claim, Mapping),
                "s3_t04_claim_shape_invalid",
            )
            claim_key = (cell_id, str(claim.get("claim_id") or ""))
            source_rendering = rendering_by_claim.get(claim_key)
            _require(
                isinstance(source_rendering, Mapping),
                "s3_t04_claim_rendering_missing",
            )
            numeric_refs = [
                str(ref)
                for fact_id in claim.get("support_fact_ids", ())
                for ref in facts.get(str(fact_id), {}).get("support_refs", ())
                if facts.get(str(fact_id), {}).get("support_type")
                == "Numeric"
            ]
            evidence_refs = [
                str(ref)
                for fact_id in claim.get("support_fact_ids", ())
                for ref in facts.get(str(fact_id), {}).get("support_refs", ())
                if facts.get(str(fact_id), {}).get("support_type")
                == "Evidence"
            ]
            _require(
                all(ref in numeric_rows for ref in numeric_refs),
                "s3_t04_claim_numeric_ref_unknown",
            )
            source_text = str(
                source_rendering.get("rendered_text_zh_cn") or ""
            )
            narrative = source_text
            if numeric_refs:
                canonical_prefix = "；".join(
                    _canonical_numeric_clause(numeric_rows[ref])
                    for ref in numeric_refs
                )
                _require(
                    source_text.startswith(canonical_prefix + "；"),
                    "s3_t04_source_numeric_rendering_not_authority_bound",
                )
                narrative = source_text[len(canonical_prefix) + 1 :]
            numeric_only_qualification_applied = bool(
                numeric_refs and not evidence_refs
            )
            if numeric_only_qualification_applied:
                narrative = (
                    "本地绑定数值事实仅支持上述财务指标，"
                    "不足以单独证明该判断的因果机制。"
                )
                numeric_only_qualification_count += 1
            _require(
                all(token not in narrative for token in _INTERNAL_DELIVERY_TOKENS),
                "s3_t04_internal_token_outside_numeric_prefix",
            )
            delivery_clauses = [
                _delivery_numeric_clause(numeric_rows[ref])
                for ref in numeric_refs
            ]
            delivery_text = "；".join(
                [*delivery_clauses, narrative]
                if delivery_clauses
                else [narrative]
            )
            rendered_texts.append(delivery_text)
            claims.append(
                {
                    "claim_ref": deepcopy(source_rendering["claim_ref"]),
                    "epistemic_status": str(
                        source_rendering.get("epistemic_status") or ""
                    ),
                    "rendered_text_zh_cn": delivery_text,
                    "numeric_support_refs": numeric_refs,
                    "evidence_support_refs": evidence_refs,
                    "numeric_only_qualification_applied": (
                        numeric_only_qualification_applied
                    ),
                    "scope_digest": str(
                        source_rendering.get("scope_digest") or ""
                    ),
                    "qualification_preserved": (
                        source_rendering.get("qualification_preserved") is True
                    ),
                }
            )

        input_cell = input_cells[cell_id]
        runtime_branch = input_cell.get("runtime_branch") or {}
        case_threshold = str(runtime_branch.get("what_would_change") or "").strip()
        _require(
            case_threshold,
            "s3_t04_case_specific_threshold_source_missing",
        )
        tasks: list[dict[str, Any]] = []
        for task in specialist.get("what_would_change", ()):
            _require(
                isinstance(task, Mapping),
                "s3_t04_WWC_task_shape_invalid",
            )
            enriched = deepcopy(dict(task))
            decision_rule = deepcopy(dict(enriched.get("decision_rule") or {}))
            decision_rule["threshold_or_observation"] = case_threshold
            decision_rule["threshold_source"] = (
                "frozen_runtime_branch.what_would_change"
            )
            enriched["decision_rule"] = decision_rule
            tasks.append(enriched)
            specialized_task_count += 1
        preview_sections.append(
            {
                "program_cell_id": cell_id,
                "decision_question": str(
                    runtime_branch.get("decision_question") or ""
                ),
                "claims": claims,
                "what_would_change": tasks,
                "stop_rule": str(runtime_branch.get("stop_rule") or ""),
            }
        )

    preview_body = {
        "contract_ref": PRODUCT_SURFACE_CONTRACT_REF,
        "source_input_digest": str(manifest.get("input_digest") or ""),
        "source_report_digest": canonical_digest(source_report),
        "source_judgment_digest": canonical_digest(judgment),
        "title_zh_cn": str(source_report.get("title_zh_cn") or ""),
        "executive_summary_zh_cn": "；".join(rendered_texts),
        "sections": preview_sections,
        "limitations_zh_cn": list(source_report.get("limitations_zh_cn") or ()),
        "source_calls": 0,
        "tool_calls": 0,
    }
    preview = {
        **preview_body,
        "final_delivery_preview_digest": canonical_digest(preview_body),
    }
    preview_text = json.dumps(preview, ensure_ascii=False, sort_keys=True)
    forbidden_findings = [
        token for token in _INTERNAL_DELIVERY_TOKENS if token in preview_text
    ]
    duplicated_currency = bool(
        re.search(r"\b(USD|EUR|CNY)\s+[0-9,.]+\s+\1\b", preview_text)
    )
    _require(
        not forbidden_findings and not duplicated_currency,
        "s3_t04_final_delivery_surface_not_normalized",
    )
    all_tasks = [
        task
        for section in preview_sections
        for task in section["what_would_change"]
    ]
    _require(
        specialized_task_count == len(all_tasks)
        and specialized_task_count > 0
        and all(
            (task.get("decision_rule") or {}).get("threshold_source")
            == "frozen_runtime_branch.what_would_change"
            and "绑定权威观察"
            not in str(
                (task.get("decision_rule") or {}).get(
                    "threshold_or_observation"
                )
                or ""
            )
            for task in all_tasks
        ),
        "s3_t04_generic_WWC_threshold_not_replaced",
    )
    _require(
        numeric_only_qualification_count
        == sum(
            1
            for section in preview_sections
            for claim in section["claims"]
            if claim["numeric_support_refs"]
            and not claim["evidence_support_refs"]
            and claim["numeric_only_qualification_applied"] is True
            and "不足以单独证明该判断的因果机制"
            in claim["rendered_text_zh_cn"]
        ),
        "s3_t04_numeric_only_epistemic_qualification_missing",
    )
    verifier_body = {
        "contract_ref": FINAL_PREVIEW_VERIFIER_CONTRACT_REF,
        "status": "pass",
        "final_delivery_preview_digest": preview[
            "final_delivery_preview_digest"
        ],
        "bound_source_report_digest": canonical_digest(source_report),
        "bound_source_judgment_digest": canonical_digest(judgment),
        "checks": {
            "case_identity": "pass_NVDA",
            "cell_and_claim_cardinality": "pass",
            "numeric_authority_correspondence": "pass",
            "internal_scope_token_exclusion": "pass",
            "period_label_normalization": "pass",
            "currency_unit_deduplication": "pass",
            "case_specific_WWC_thresholds": "pass",
            "epistemic_qualification_preservation": "pass",
            "numeric_only_support_not_overstated_as_evidence": "pass",
        },
        "machine_verifier_is_human_acceptance": False,
    }
    final_verifier = {
        **verifier_body,
        "verification_digest": canonical_digest(verifier_body),
    }
    fixture = _fixture_evidence_qualification(
        evidence_artifact=artifacts["bounded_agent_evidence"],
        specialists=specialists,
        input_cells=input_cells,
    )
    product_status = (
        "delivery_surface_pass_fixture_evidence_density_block"
        if fixture["status"].startswith("blocked_")
        else "delivery_and_fixture_qualification_pass"
    )
    result_body = {
        "schema_version": "fin_ia_0_1_2_s3_t04_product_surface_result_v1_0",
        "status": product_status,
        "immutable_exact_result_preserved": True,
        "new_model_calls": 0,
        "new_provider_calls": 0,
        "new_network_calls": 0,
        "final_delivery_preview": preview,
        "final_delivery_verification": final_verifier,
        "fixture_evidence_qualification": fixture,
        "owner_acceptance_eligible": fixture["status"].startswith("pass_"),
    }
    return {**result_body, "result_digest": canonical_digest(result_body)}
