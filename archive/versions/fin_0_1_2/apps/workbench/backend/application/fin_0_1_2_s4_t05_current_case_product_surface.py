from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from apps.workbench.backend.application.fin_0_1_2_s3_t04_product_surface import (
    S3T04ProductSurfaceError,
    materialize_verified_product_surface_for_case,
    validate_verified_product_surface,
)
from sec_agent.canonical_runtime.models import canonical_digest


CURRENT_CASE_PRODUCT_SURFACE_CONTRACT_REF = (
    "fin_0_1_2.s4_t05.current_case_verified_final_delivery_surface:v1"
)
CURRENT_CASE_FINAL_PREVIEW_VERIFIER_CONTRACT_REF = (
    "fin_0_1_2.s4_t05.current_case_local_final_delivery_verifier:v1"
)
CURRENT_CASE_RESULT_SCHEMA_VERSION = (
    "fin_ia_0_1_2_s4_t05_current_case_product_surface_result_v1_0"
)
SUPPORTED_CASE_TICKERS = frozenset({"DELL", "MU", "NVDA"})
CURRENT_CASE_DETERMINISTIC_BASELINE_CONTRACT_REF = (
    "fin_0_1_2.s4_t05.current_case_deterministic_baseline:v1"
)


class S4T05CurrentCaseProductSurfaceError(S3T04ProductSurfaceError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T05CurrentCaseProductSurfaceError(code)


def _artifact_map(
    execution_result: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows = execution_result.get("artifacts")
    _require(isinstance(rows, list), "s4_t05_product_surface_artifacts_required")
    mapped: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        _require(
            isinstance(row, Mapping) and isinstance(row.get("payload"), Mapping),
            "s4_t05_product_surface_artifact_invalid",
        )
        artifact_type = str(row.get("artifact_type") or "")
        _require(
            artifact_type != "" and artifact_type not in mapped,
            "s4_t05_product_surface_artifact_type_invalid",
        )
        mapped[artifact_type] = row["payload"]
    return mapped


def _validate_source_case_binding(
    *,
    execution_result: Mapping[str, Any],
    input_pack: Mapping[str, Any],
    expected_case_ticker: str,
) -> None:
    _require(
        expected_case_ticker in SUPPORTED_CASE_TICKERS,
        "s4_t05_product_surface_case_not_supported",
    )
    artifacts = _artifact_map(execution_result)
    manifest = artifacts.get("bounded_agent_manifest") or {}
    input_digest = str(input_pack.get("input_digest") or "")
    _require(
        input_pack.get("company") == expected_case_ticker
        and manifest.get("case_ticker") == expected_case_ticker
        and manifest.get("input_digest") == input_digest
        and input_digest != "",
        "s4_t05_product_surface_case_or_input_identity_mismatch",
    )
    input_body = {
        key: value for key, value in input_pack.items() if key != "input_digest"
    }
    _require(
        canonical_digest(input_body) == input_digest,
        "s4_t05_product_surface_input_digest_mismatch",
    )
    for payload in artifacts.values():
        if "input_digest" in payload:
            _require(
                payload.get("input_digest") == input_digest,
                "s4_t05_product_surface_artifact_input_digest_mismatch",
            )
        runtime = payload.get("s4_case_runtime")
        if isinstance(runtime, Mapping):
            _require(
                runtime.get("case_ticker") == expected_case_ticker,
                "s4_t05_product_surface_runtime_case_identity_mismatch",
            )
    for artifact_type in ("bounded_agent_workpaper", "bounded_agent_verification"):
        payload = artifacts.get(artifact_type) or {}
        _require(
            payload.get("entity_label") == expected_case_ticker,
            "s4_t05_product_surface_artifact_case_identity_mismatch",
        )
    numeric = artifacts.get("bounded_agent_numeric") or {}
    _require(
        all(
            row.get("entity_ref") == expected_case_ticker
            for projection in numeric.get(
                "case_numeric_authority_projections", ()
            )
            if isinstance(projection, Mapping)
            for row in projection.get("rows", ())
            if isinstance(row, Mapping)
        ),
        "s4_t05_product_surface_numeric_case_identity_mismatch",
    )
    report = (artifacts.get("bounded_agent_report") or {}).get("report") or {}
    _require(
        expected_case_ticker in str(report.get("title_zh_cn") or ""),
        "s4_t05_product_surface_report_case_identity_mismatch",
    )


def materialize_current_case_verified_product_surface(
    *,
    execution_result: Mapping[str, Any],
    input_pack: Mapping[str, Any],
    expected_case_ticker: str,
) -> dict[str, Any]:
    """Render a DELL/MU/NVDA delivery without changing exact-live artifacts."""

    _validate_source_case_binding(
        execution_result=execution_result,
        input_pack=input_pack,
        expected_case_ticker=expected_case_ticker,
    )
    result = materialize_verified_product_surface_for_case(
        execution_result=execution_result,
        input_pack=input_pack,
        expected_case_ticker=expected_case_ticker,
        current_surface_contract_ref=CURRENT_CASE_PRODUCT_SURFACE_CONTRACT_REF,
        current_verifier_contract_ref=(
            CURRENT_CASE_FINAL_PREVIEW_VERIFIER_CONTRACT_REF
        ),
        current_result_schema_version=CURRENT_CASE_RESULT_SCHEMA_VERSION,
        include_explicit_case_binding=True,
    )
    return validate_current_case_verified_product_surface(
        result,
        expected_case_ticker=expected_case_ticker,
    )


def validate_current_case_verified_product_surface(
    result: Mapping[str, Any],
    *,
    expected_case_ticker: str,
) -> dict[str, Any]:
    validated = validate_verified_product_surface(result)
    preview = validated["final_delivery_preview"]
    verifier = validated["final_delivery_verification"]
    _require(
        validated.get("schema_version") == CURRENT_CASE_RESULT_SCHEMA_VERSION
        and validated.get("case_ticker") == expected_case_ticker
        and preview.get("contract_ref")
        == CURRENT_CASE_PRODUCT_SURFACE_CONTRACT_REF
        and preview.get("case_ticker") == expected_case_ticker
        and verifier.get("contract_ref")
        == CURRENT_CASE_FINAL_PREVIEW_VERIFIER_CONTRACT_REF
        and verifier.get("bound_case_ticker") == expected_case_ticker
        and (verifier.get("checks") or {}).get("case_identity")
        == f"pass_{expected_case_ticker}",
        "s4_t05_product_surface_final_case_binding_invalid",
    )
    return deepcopy(dict(validated))


def materialize_current_case_deterministic_baseline(
    *,
    input_pack: Mapping[str, Any],
    expected_case_ticker: str,
    execution_identity: str,
) -> dict[str, Any]:
    """Build a distinct zero-call authority-inventory baseline."""

    input_digest = str(input_pack.get("input_digest") or "")
    input_head_digest = str(input_pack.get("input_head_digest") or "")
    _require(
        expected_case_ticker in SUPPORTED_CASE_TICKERS
        and input_pack.get("company") == expected_case_ticker
        and input_digest != ""
        and input_head_digest != ""
        and execution_identity != "",
        "s4_t05_deterministic_baseline_identity_invalid",
    )
    identity_seed = canonical_digest(
        {
            "contract_ref": CURRENT_CASE_DETERMINISTIC_BASELINE_CONTRACT_REF,
            "case_ticker": expected_case_ticker,
            "input_digest": input_digest,
            "execution_identity": execution_identity,
        }
    )
    cells = []
    for row in input_pack.get("cell_inputs", ()):
        authority = row.get("authority_refs") or {}
        cells.append(
            {
                "program_cell_id": str(row.get("program_cell_id") or ""),
                "decision_question": str(
                    (row.get("runtime_branch") or {}).get("decision_question")
                    or ""
                ),
                "accepted_evidence_refs": sorted(
                    str(ref)
                    for ref in authority.get("accepted_evidence_refs", ())
                ),
                "numeric_refs": sorted(
                    str(ref) for ref in authority.get("numeric_refs", ())
                ),
                "candidate_refs_not_evidence": sorted(
                    str(ref)
                    for ref in authority.get("candidate_refs_not_evidence", ())
                ),
                "deterministic_output_boundary": (
                    "authority_inventory_only_no_claim_or_causal_inference"
                ),
            }
        )
    _require(len(cells) == 3, "s4_t05_deterministic_baseline_cells_invalid")
    artifact_body = {
        "contract_ref": CURRENT_CASE_DETERMINISTIC_BASELINE_CONTRACT_REF,
        "case_ticker": expected_case_ticker,
        "input_digest": input_digest,
        "input_head_digest": input_head_digest,
        "case_id": str(input_pack.get("case_id") or ""),
        "case_version": int(input_pack.get("case_version") or 0),
        "as_of": str(input_pack.get("as_of") or ""),
        "program_cells": cells,
        "claims": [],
        "cross_cell_dependencies": [],
        "conflict_adjudications": [],
        "remaining_gaps": [],
        "what_would_change": [],
        "hard_boundary": (
            "The baseline inventories approved authority only and does not "
            "manufacture judgment, causal synthesis or delivery prose."
        ),
    }
    artifact = {
        "artifact_type": "bounded_deterministic_baseline",
        "payload": {
            **artifact_body,
            "artifact_digest": canonical_digest(artifact_body),
        },
    }
    body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t05_current_case_deterministic_baseline_result_v1_0"
        ),
        "status": "success",
        "business_promotable": False,
        "case_ticker": expected_case_ticker,
        "execution_identity": execution_identity,
        "work_unit_id": f"wu_s4_t05_baseline_{identity_seed[:20]}",
        "attempt_id": f"attempt_s4_t05_baseline_{identity_seed[20:40]}",
        "research_run_id": f"research_run_s4_t05_baseline_{identity_seed[40:60]}",
        "input_digest": input_digest,
        "input_head_digest": input_head_digest,
        "artifacts": [artifact],
        "terminal": {
            "status": "success",
            "phase": "complete",
            "code": "s4_t05_zero_call_deterministic_baseline_success",
        },
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "business_writes": 0,
            "artifacts": 1,
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


def validate_current_case_pair_readiness(
    *,
    exact_result: Mapping[str, Any],
    baseline_result: Mapping[str, Any],
    surface_result: Mapping[str, Any],
    expected_case_ticker: str,
) -> dict[str, Any]:
    baseline_body = {
        key: value
        for key, value in baseline_result.items()
        if key != "result_digest"
    }
    _require(
        baseline_result.get("result_digest") == canonical_digest(baseline_body),
        "s4_t05_deterministic_baseline_digest_mismatch",
    )
    artifacts = _artifact_map(exact_result)
    manifest = artifacts.get("bounded_agent_manifest") or {}
    comparison = artifacts.get("agent_fallback_comparison") or {}
    validated_surface = validate_current_case_verified_product_surface(
        surface_result,
        expected_case_ticker=expected_case_ticker,
    )
    shared_head = (comparison.get("paired_baseline_contract") or {}).get(
        "shared_input_head_digest"
    )
    _require(
        exact_result.get("status") == "success"
        and exact_result.get("business_promotable") is True
        and baseline_result.get("status") == "success"
        and baseline_result.get("business_promotable") is False
        and manifest.get("case_ticker") == expected_case_ticker
        and baseline_result.get("case_ticker") == expected_case_ticker,
        "s4_t05_pair_terminal_or_case_invalid",
    )
    _require(
        manifest.get("input_digest")
        == comparison.get("paired_input_digest")
        == baseline_result.get("input_digest")
        and shared_head == baseline_result.get("input_head_digest"),
        "s4_t05_pair_input_binding_mismatch",
    )
    _require(
        comparison.get("agent_research_run_id")
        != baseline_result.get("research_run_id")
        and len(exact_result.get("artifacts") or ()) == 9
        and len(baseline_result.get("artifacts") or ()) == 1,
        "s4_t05_pair_runs_or_artifacts_not_distinct",
    )
    body = {
        "status": "ready_for_formal_paired_assessment",
        "case_ticker": expected_case_ticker,
        "same_input_digest": str(baseline_result["input_digest"]),
        "same_input_head_digest": str(baseline_result["input_head_digest"]),
        "agent_research_run_id": str(comparison["agent_research_run_id"]),
        "deterministic_research_run_id": str(
            baseline_result["research_run_id"]
        ),
        "runs_are_distinct": True,
        "agent_artifact_count": 9,
        "deterministic_artifact_count": 1,
        "final_delivery_preview_digest": validated_surface[
            "final_delivery_preview"
        ]["final_delivery_preview_digest"],
        "formal_paired_assessment_performed": False,
        "owner_decision_performed": False,
    }
    return {**body, "readiness_digest": canonical_digest(body)}
