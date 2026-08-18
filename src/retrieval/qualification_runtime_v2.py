from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifact_spine import sha256_file
from .contracts import (
    EVIDENCE_REQUEST_SCHEMA_VERSION,
    EvidenceRequest,
    FinancialResearchKernel,
    load_evidence_request,
    load_financial_research_kernel,
)
from .evaluation_assets import (
    EVALUATION_INPUT_SCHEMA_VERSION,
    EvaluationInput,
    QualificationPreRegistration,
)
from .query_plan_v2 import QueryFacetPlan, compile_query_facet_plan_for_request
from .route_compiler import (
    QueryObjectFactRoutePolicy,
    RetrievalExecutionPlan,
    compile_retrieval_execution_plan,
    load_query_object_fact_route_policy,
)


QUALIFICATION_RUNTIME_OVERLAY_SCHEMA_VERSION = (
    "fin_ia_s1_vs5_qualification_runtime_overlay_v1_0"
)


class QualificationRuntimeError(ValueError):
    """A VS5 v2 runtime input or provider-neutral overlay is not reproducible."""


@dataclass(frozen=True)
class QualificationRuntimeBundle:
    kernel: FinancialResearchKernel
    route_policy: QueryObjectFactRoutePolicy
    inputs_by_split: Mapping[str, tuple[EvaluationInput, ...]]


def load_qualification_runtime_bundle(
    *,
    repo_root: Path,
    preregistration: QualificationPreRegistration,
    overlay_path: Path,
) -> QualificationRuntimeBundle:
    overlay = _read_json(overlay_path)
    _require(
        overlay.get("schema_version")
        == QUALIFICATION_RUNTIME_OVERLAY_SCHEMA_VERSION,
        "qualification_runtime_overlay_schema_invalid",
    )
    _require(
        overlay.get("status") == "frozen_before_candidate_execution",
        "qualification_runtime_overlay_status_invalid",
    )
    authority = overlay.get("authority")
    _require(
        isinstance(authority, Mapping)
        and authority.get("provider_neutral") is True
        and authority.get("runtime_inputs_exclude_references") is True
        and authority.get("candidate_is_not_evidence") is True
        and authority.get("numeric_fact_authority") is False
        and authority.get("generation_model_calls") == 0
        and authority.get("learned_vector_device") == "cuda"
        and authority.get("learned_vector_precision") == "fp16"
        and authority.get("cpu_vector_fallback_allowed") is False,
        "qualification_runtime_overlay_authority_invalid",
    )

    bound = overlay.get("bound_inputs")
    _require(isinstance(bound, Mapping), "qualification_runtime_bound_inputs_invalid")
    prereg_ref = _validate_bound_ref(repo_root, bound, "preregistration")
    _require(
        prereg_ref.resolve()
        == (repo_root / "eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json").resolve(),
        "qualification_runtime_preregistration_ref_invalid",
    )
    base_kernel_path = _validate_bound_ref(repo_root, bound, "base_kernel")
    route_policy_path = _validate_bound_ref(repo_root, bound, "route_policy")
    _validate_bound_ref(repo_root, bound, "compiled_objects_result")

    base_payload = _read_json(base_kernel_path)
    successor_payload = _apply_overlay(
        base_payload=base_payload,
        overlay=overlay,
        preregistration=preregistration,
    )
    kernel = load_financial_research_kernel(successor_payload)
    route_policy = load_query_object_fact_route_policy(
        _read_json(route_policy_path), kernel
    )
    inputs = _compile_inputs(
        preregistration=preregistration,
        overlay=overlay,
        kernel=kernel,
        route_policy=route_policy,
    )
    return QualificationRuntimeBundle(
        kernel=kernel,
        route_policy=route_policy,
        inputs_by_split={
            split: tuple(row for row in inputs if row.split == split)
            for split in ("valid_temporal", "test_frozen", "holdout_heterogeneous")
        },
    )


def _apply_overlay(
    *,
    base_payload: Mapping[str, Any],
    overlay: Mapping[str, Any],
    preregistration: QualificationPreRegistration,
) -> dict[str, Any]:
    payload = deepcopy(dict(base_payload))
    extensions = overlay.get("source_type_extensions")
    _require(
        isinstance(extensions, list) and extensions,
        "qualification_runtime_source_extensions_invalid",
    )
    extension_types: list[str] = []
    for row in extensions:
        _require(
            isinstance(row, Mapping)
            and str(row.get("source_type") or "").strip()
            and row.get("preserve_original_source_identity") is True
            and row.get("candidate_authority_only") is True,
            "qualification_runtime_source_extension_invalid",
        )
        extension_types.append(str(row["source_type"]).strip())
    _require(
        len(extension_types) == len(set(extension_types)),
        "qualification_runtime_source_extension_duplicate",
    )
    for slot in payload.get("evidence_slots") or ():
        source_types = list(slot.get("source_types") or ())
        source_types.extend(value for value in extension_types if value not in source_types)
        slot["source_types"] = source_types

    packs = overlay.get("industry_packs")
    cases = overlay.get("case_profiles")
    _require(
        isinstance(packs, list) and packs and isinstance(cases, list) and cases,
        "qualification_runtime_profiles_invalid",
    )
    existing_packs = {str(row.get("pack_id") or "") for row in payload["industry_packs"]}
    existing_cases = {str(row.get("case_key") or "").upper() for row in payload["cases"]}
    _require(
        not existing_packs.intersection(str(row.get("pack_id") or "") for row in packs)
        and not existing_cases.intersection(
            str(row.get("case_key") or "").upper() for row in cases
        ),
        "qualification_runtime_profile_overlaps_base",
    )
    payload["industry_packs"].extend(deepcopy(packs))
    payload["cases"].extend(deepcopy(cases))

    expected_cases = {row.case_key for row in preregistration.cases}
    overlay_cases = {str(row.get("case_key") or "").upper() for row in cases}
    _require(
        overlay_cases == expected_cases,
        "qualification_runtime_case_coverage_invalid",
    )
    for spec in preregistration.cases:
        row = next(
            item for item in cases if str(item.get("case_key") or "").upper() == spec.case_key
        )
        subject = row.get("subject") or {}
        _require(
            str(subject.get("ticker") or "").upper() == spec.case_key
            and str(subject.get("legal_name") or "") == spec.legal_name
            and str(row.get("industry_pack_id") or "") == spec.industry_group,
            f"qualification_runtime_case_identity_drift:{spec.case_key}",
        )
    return payload


def _compile_inputs(
    *,
    preregistration: QualificationPreRegistration,
    overlay: Mapping[str, Any],
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
) -> list[EvaluationInput]:
    raw_routes = overlay.get("proposition_routes")
    _require(
        isinstance(raw_routes, list) and raw_routes,
        "qualification_runtime_proposition_routes_invalid",
    )
    routes = {
        str(row.get("proposition_id") or ""): row
        for row in raw_routes
        if isinstance(row, Mapping)
    }
    expected = {
        proposition.proposition_id
        for case in preregistration.cases
        for proposition in case.propositions
    }
    _require(
        set(routes) == expected and len(routes) == len(raw_routes),
        "qualification_runtime_proposition_route_coverage_invalid",
    )
    source_result_ref = str(
        (overlay.get("bound_inputs") or {})["compiled_objects_result_ref"]
    )
    output: list[EvaluationInput] = []
    for case in preregistration.cases:
        profile = kernel.cases[case.case_key]
        source_types = tuple(dict.fromkeys(row.form_type for row in case.source_targets))
        fiscal_years = tuple(sorted({row.fiscal_year for row in case.source_targets}))
        for proposition in case.propositions:
            route = routes[proposition.proposition_id]
            _require(
                str(route.get("case_key") or "").upper() == case.case_key,
                f"qualification_runtime_proposition_case_drift:{proposition.proposition_id}",
            )
            request_payload = {
                "schema_version": EVIDENCE_REQUEST_SCHEMA_VERSION,
                "request_id": f"ER::VS5::{case.case_key}::{proposition.proposition_id}",
                "cell_id": f"S1::VS5::{proposition.proposition_id}",
                "requester_role": "qualification_researcher",
                "evidence_domain": str(route["evidence_domain"]),
                "case_key": case.case_key,
                "subject_ticker": case.case_key,
                "research_as_of": profile.research_as_of.isoformat(),
                "target_entities": [case.case_key],
                "requested_facet_ids": list(route["requested_facet_ids"]),
                "metric_intents": list(route.get("metric_intents") or ()),
                "product_intents": list(route.get("product_intents") or ()),
                "period": {
                    "start_date": route.get("start_date"),
                    "end_date": route.get("end_date"),
                    "fiscal_years": list(route.get("fiscal_years") or fiscal_years),
                },
                "granularity": "claim_table_and_bounded_context",
                "unit": "issuer_reported_native_unit",
                "acceptable_sources": list(source_types),
                "acceptable_proxy": bool(route.get("acceptable_proxy", False)),
                "forbidden_proxy": list(
                    route.get("forbidden_proxy")
                    or (
                        "wrong issuer",
                        "wrong fiscal period",
                        "generic risk without proposition linkage",
                    )
                ),
                "stop_condition": "all requested facets have candidates or typed failure receipts",
                "clarification_policy": "return_typed_gap",
            }
            request = load_evidence_request(request_payload, kernel)
            plan = compile_query_facet_plan_for_request(kernel, request)
            execution = compile_retrieval_execution_plan(
                route_policy,
                request,
                fact_store_availability={
                    "company_financial_fact_mart": False,
                    "market_snapshot_fact_mart": False,
                },
            )
            runtime_input = {
                "case_identity": {
                    "case_key": case.case_key,
                    "legal_name": case.legal_name,
                    "industry_group": case.industry_group,
                    "jurisdiction": case.jurisdiction,
                    "accounting_basis": case.accounting_basis,
                },
                "research_as_of": profile.research_as_of.isoformat(),
                "question_zh": proposition.question_zh,
                "evidence_request": request.as_dict(),
                "query_facet_plan": plan.as_dict(),
                "retrieval_execution_plan": execution.as_dict(),
                "authority": {
                    "candidate_is_not_evidence": True,
                    "numeric_fact_authority": False,
                    "references_visible_to_runtime": False,
                },
            }
            output.append(
                EvaluationInput(
                    schema_version=EVALUATION_INPUT_SCHEMA_VERSION,
                    example_id=f"VS5::{case.case_key}::{proposition.proposition_id}",
                    split=case.split,
                    responsibility_axes=("S1-C", "S1-G", "S1-H", "S1-I"),
                    vertical_slices=("VS5",),
                    evaluation_unit="candidate_quality",
                    case_role=case.case_role,
                    source_fixture_refs=(source_result_ref,),
                    runtime_input=runtime_input,
                )
            )
    _require(len(output) == 30, "qualification_runtime_input_count_invalid")
    return output


def _validate_bound_ref(repo_root: Path, bound: Mapping[str, Any], prefix: str) -> Path:
    ref = str(bound.get(f"{prefix}_ref") or "").replace("\\", "/")
    expected = str(bound.get(f"{prefix}_sha256") or "")
    _require(ref and len(expected) == 64, f"qualification_runtime_binding_invalid:{prefix}")
    path = repo_root / ref
    _require(path.is_file(), f"qualification_runtime_binding_missing:{prefix}")
    _require(
        sha256_file(path) == expected,
        f"qualification_runtime_binding_drift:{prefix}",
    )
    return path


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"qualification_runtime_json_object_required:{path.name}")
    return value


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise QualificationRuntimeError(code)


__all__ = [
    "QUALIFICATION_RUNTIME_OVERLAY_SCHEMA_VERSION",
    "QualificationRuntimeBundle",
    "QualificationRuntimeError",
    "load_qualification_runtime_bundle",
]
