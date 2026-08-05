from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s4_t06_current_product_projection import (  # noqa: E402
    CURRENT_PRODUCT_PROJECTION_REGISTRY_REF,
    CURRENT_PRODUCT_PROJECTION_RESOURCE_ID,
    CURRENT_PRODUCT_PROJECTION_SCHEMA,
    CURRENT_PRODUCT_SURFACES,
    validate_current_product_projection_manifest,
)
from scripts.releases.materialize_fin_ia_0_1_2_s4_t06_workbench_current_product_projection_entry_and_dependency_decision import (  # noqa: E402
    CASE_SOURCES,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


DEFAULT_MANIFEST_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t06_a_current_product_projection_"
    "manifest_v1_0.json"
)
DEFAULT_REGISTRY_OUTPUT = ROOT / CURRENT_PRODUCT_PROJECTION_REGISTRY_REF
DEFAULT_IMPLEMENTATION_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t06_a_current_product_projection_"
    "read_only_service_and_api_zero_call_implementation_v1_0.json"
)
ENTRY_DECISION_REF = (
    "configs/releases/fin_ia_0_1_2_s4_t06_workbench_current_product_"
    "projection_entry_and_dependency_decision_v1_0.json"
)
ENTRY_DECISION_DIGEST = (
    "55d06706f2f0bc1210728aa18a5767073f1c90e90ad3bcf36080e49b14c25527"
)


class CurrentProductProjectionMaterializationError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CurrentProductProjectionMaterializationError(code)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentProductProjectionMaterializationError(
            "current_product_projection_source_unreadable"
        ) from exc
    _require(
        isinstance(value, dict),
        "current_product_projection_source_object_required",
    )
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(exact: Mapping[str, Any], artifact_type: str) -> dict[str, Any]:
    rows = [
        row.get("payload")
        for row in exact.get("artifacts") or ()
        if row.get("artifact_type") == artifact_type
    ]
    _require(
        len(rows) == 1 and isinstance(rows[0], dict),
        f"current_product_projection_artifact_missing:{artifact_type}",
    )
    return rows[0]


def _view(case_key: str, surface: str, data: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t06_current_product_projection_view_v1_0"
        ),
        "case_key": case_key,
        "surface": surface,
        "data": dict(data),
    }
    return {**body, "view_digest": canonical_digest(body)}


def _safe_node_receipt(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "node_id": row.get("node_id"),
        "input_digest": row.get("input_digest"),
        "output_digest": row.get("output_digest"),
        "observed_counts": dict(row.get("observed_counts") or {}),
        "version_bindings": dict(row.get("version_bindings") or {}),
    }


def _safe_local_receipt(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "program_cell_id": row.get("program_cell_id"),
        "receipt_digest": row.get("receipt_digest"),
        "eligible_support_count": row.get("eligible_support_count"),
        "visible_support_count": row.get("visible_support_count"),
        "selected_support_count": row.get("selected_support_count"),
        "selected_alias_digest": row.get("selected_alias_digest"),
        "assembled_output_digest": row.get("assembled_output_digest"),
        "model_calls": row.get("model_calls"),
        "provider_calls": row.get("provider_calls"),
        "network_calls": row.get("network_calls"),
    }


def _case_projection(case_key: str, source: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("owner", "evidence", "exact", "surface"):
        _require(
            _sha256(source[key]) == source[f"{key}_sha256"],
            f"current_product_projection_{case_key.lower()}_{key}_drift",
        )
    owner = _load(source["owner"])
    evidence = _load(source["evidence"])
    exact = _load(source["exact"])
    surface = _load(source["surface"])
    _require(
        evidence.get("case_key") == case_key
        and evidence.get("evidence_pack_digest") == source["evidence_digest"],
        f"current_product_projection_{case_key.lower()}_evidence_invalid",
    )
    _require(
        exact.get("status") == "success"
        and exact.get("business_promotable") is True
        and len(exact.get("artifacts") or ()) == 9,
        f"current_product_projection_{case_key.lower()}_exact_invalid",
    )
    _require(
        surface.get("record_digest") == source["surface_digest"]
        and surface.get("product_surface", {}).get("case_ticker") == case_key,
        f"current_product_projection_{case_key.lower()}_surface_invalid",
    )
    _require(
        owner.get("decision_digest") == source["owner_digest"]
        and owner.get("owner_decision", {}).get("material_gain_accepted") is True,
        f"current_product_projection_{case_key.lower()}_owner_invalid",
    )

    manifest_artifact = _artifact(exact, "bounded_agent_manifest")
    workpaper_artifact = _artifact(exact, "bounded_agent_workpaper")
    trace_artifact = _artifact(exact, "bounded_agent_trace")
    product_surface = surface["product_surface"]
    terminal = exact["terminal"]
    runtime = manifest_artifact.get("s4_case_runtime") or {}
    interaction_topology = manifest_artifact.get("interaction_topology") or {}
    formal = owner.get("source_formal_assessment") or {}
    preserved = owner.get("preserved_boundaries") or {}
    scoped_identity_surface = dict(
        workpaper_artifact.get("scoped_identity_surface") or {}
    )
    scoped_identity_surface["local_id_cross_cell_ambiguity_counts"] = (
        scoped_identity_surface.pop(
            "raw_local_id_cross_cell_ambiguity_counts", {}
        )
    )

    views = {
        "case": _view(
            case_key,
            "case",
            {
                "ticker": case_key,
                "as_of": evidence["as_of"],
                "natural_objective": evidence["natural_objective"],
                "status": "owner_accepted_current_R2",
                "accepted_product_scope": owner["owner_decision"][
                    "accepted_product_scope"
                ],
                "method_id": runtime.get("method_id"),
                "program_cell_ids": list(
                    manifest_artifact.get("program_cell_ids") or ()
                ),
                "counts": {
                    "evidence": len(evidence["evidence_rows"]),
                    "numeric": len(evidence["numeric_rows"]),
                    "typed_gaps": len(evidence["typed_gaps"]),
                    "approved_graph_edges": 0,
                    "business_artifacts": len(exact["artifacts"]),
                },
            },
        ),
        "run": _view(
            case_key,
            "run",
            {
                "execution_identity": terminal.get("execution_identity"),
                "admission_id": manifest_artifact.get("admission_id"),
                "status": terminal.get("status"),
                "phase": terminal.get("phase"),
                "code": terminal.get("code"),
                "business_promotable": terminal.get("business_promotable"),
                "input_digest": manifest_artifact.get("input_digest"),
                "input_head_digest": manifest_artifact.get("input_head_digest"),
                "lineage_digest": manifest_artifact.get("lineage_digest"),
                "interaction_topology": dict(interaction_topology),
                "observed_budget": dict(terminal.get("observed_budget") or {}),
                "terminal_result_digest": exact.get("terminal_object", {}).get(
                    "digest"
                ),
                "raw_content_exposed": False,
            },
        ),
        "evidence": _view(
            case_key,
            "evidence",
            {
                "evidence_pack_digest": evidence["evidence_pack_digest"],
                "rows": list(evidence["evidence_rows"]),
            },
        ),
        "numeric": _view(
            case_key,
            "numeric",
            {
                "evidence_pack_digest": evidence["evidence_pack_digest"],
                "rows": list(evidence["numeric_rows"]),
                "exact_scope_required": True,
            },
        ),
        "graph": _view(
            case_key,
            "graph",
            {
                "status": "typed_empty_no_approved_current_graph_evidence",
                "nodes": [],
                "edges": [],
                "reason": (
                    "approved_current_evidence_pack_contains_no_graph_evidence"
                ),
            },
        ),
        "gaps": _view(
            case_key,
            "gaps",
            {
                "rows": list(evidence["typed_gaps"]),
                "gap_count": len(evidence["typed_gaps"]),
            },
        ),
        "workpaper": _view(
            case_key,
            "workpaper",
            {
                "entity_label": workpaper_artifact.get("entity_label"),
                "input_digest": workpaper_artifact.get("input_digest"),
                "cross_cell_lead_digest": workpaper_artifact.get(
                    "cross_cell_lead_digest"
                ),
                "scoped_identity_surface": scoped_identity_surface,
                "cells": list(workpaper_artifact.get("cells") or ()),
            },
        ),
        "report": _view(
            case_key,
            "report",
            {
                "final_delivery_preview": dict(
                    product_surface["final_delivery_preview"]
                ),
                "verification": {
                    "status": product_surface["final_delivery_verification"].get(
                        "status"
                    ),
                    "checks": dict(
                        product_surface["final_delivery_verification"].get(
                            "checks"
                        )
                        or {}
                    ),
                    "verification_digest": product_surface[
                        "final_delivery_verification"
                    ].get("verification_digest"),
                },
            },
        ),
        "trace": _view(
            case_key,
            "trace",
            {
                "terminal": {
                    "status": terminal.get("status"),
                    "phase": terminal.get("phase"),
                    "code": terminal.get("code"),
                    "artifact_count": terminal.get("artifact_count"),
                    "capture_count": terminal.get("capture_count"),
                },
                "interaction_topology": dict(
                    trace_artifact.get("interaction_topology") or {}
                ),
                "lineage": dict(trace_artifact.get("lineage") or {}),
                "local_fact_receipts": [
                    _safe_local_receipt(row)
                    for row in trace_artifact.get("local_fact_receipts") or ()
                ],
                "node_receipts": [
                    _safe_node_receipt(row)
                    for row in trace_artifact.get("node_receipts") or ()
                ],
                "raw_content_exposed": False,
            },
        ),
        "quality": _view(
            case_key,
            "quality",
            {
                "layered_assessment": dict(surface["layered_assessment"]),
                "current_evidence_qualification": dict(
                    product_surface["fixture_evidence_qualification"]
                ),
                "formal_assessment": {
                    "assessment_digest": formal.get("assessment_digest"),
                    "L1_L2_L3_L4": list(formal.get("L1_L2_L3_L4") or ()),
                },
                "owner_decision": dict(owner["owner_decision"]),
                "preserved_boundaries": dict(preserved),
                "deferred_quality_findings": {
                    key: value
                    for key, value in preserved.items()
                    if str(key).startswith("RC_")
                },
            },
        ),
    }
    _require(
        tuple(views) == CURRENT_PRODUCT_SURFACES,
        "current_product_projection_surface_order_invalid",
    )
    body = {
        "case_key": case_key,
        "source_anchors": {
            "evidence_pack": {
                "ref": source["evidence"].relative_to(ROOT).as_posix(),
                "sha256": source["evidence_sha256"],
                "digest": source["evidence_digest"],
            },
            "exact_result": {
                "sha256": source["exact_sha256"],
                "terminal_result_digest": exact.get("terminal_object", {}).get(
                    "digest"
                ),
            },
            "verified_product_surface": {
                "ref": source["surface"].relative_to(ROOT).as_posix(),
                "sha256": source["surface_sha256"],
                "digest": source["surface_digest"],
            },
            "owner_decision": {
                "ref": source["owner"].relative_to(ROOT).as_posix(),
                "sha256": source["owner_sha256"],
                "digest": source["owner_digest"],
            },
        },
        "views": views,
    }
    return {**body, "case_projection_digest": canonical_digest(body)}


def materialize_manifest() -> dict[str, Any]:
    entry = _load(ROOT / ENTRY_DECISION_REF)
    _require(
        entry.get("decision_digest") == ENTRY_DECISION_DIGEST
        and entry.get("recommended_next")
        == "FIN-0.1.2-S4-T06-A-THREE-CASE-CURRENT-PRODUCT-PROJECTION-MANIFEST-READ-ONLY-SERVICE-AND-API-ZERO-CALL-IMPLEMENTATION",
        "current_product_projection_entry_authority_invalid",
    )
    cases = [
        _case_projection(case_key, CASE_SOURCES[case_key])
        for case_key in ("DELL", "MU", "NVDA")
    ]
    body = {
        "schema_version": CURRENT_PRODUCT_PROJECTION_SCHEMA,
        "manifest_id": "FIN-0.1.2-S4-T06-A-CURRENT-PRODUCT-PROJECTION-R1",
        "recorded_at": "2026-08-05T20:10:00+08:00",
        "projection_mode": "current",
        "status": "engineering_projection_manifest_read_only",
        "source_entry_decision": {
            "ref": ENTRY_DECISION_REF,
            "digest": ENTRY_DECISION_DIGEST,
        },
        "cases": cases,
        "observed_counts": {
            "cases": 3,
            "evidence_rows": 45,
            "numeric_rows": 9,
            "typed_gaps": 9,
            "approved_graph_edges": 0,
            "business_artifacts": 27,
            "owner_acceptances": 3,
        },
        "hard_boundaries": {
            "fixture_fallback": False,
            "raw_capture_product_exposure": False,
            "mutable_business_truth_write": False,
            "invented_graph_edges": False,
            "model_provider_network_source_calls": 0,
            "qualified_human_review": False,
            "frontend_integration": False,
            "request_repair_actions": False,
        },
    }
    return validate_current_product_projection_manifest(
        {**body, "manifest_digest": canonical_digest(body)}
    )


def materialize_registry(manifest_path: Path) -> dict[str, Any]:
    relative = manifest_path.resolve().relative_to(ROOT).as_posix()
    value = manifest_path.read_bytes()
    row = {
        "resource_id": CURRENT_PRODUCT_PROJECTION_RESOURCE_ID,
        "repo_relative_path": relative,
        "sha256": hashlib.sha256(value).hexdigest(),
        "bytes": len(value),
        "classification": "current_product_read_only_projection_manifest",
        "consumer_ids": [
            "apps.workbench.current_product_projection.read_only_service"
        ],
        "load_phase": "S4_T06_A_current_product_projection",
        "required": True,
        "source_owner": (
            "apps.workbench.backend.application."
            "fin_0_1_2_s4_t06_current_product_projection"
        ),
    }
    canonical_rows = [row]
    canonical_bytes = json.dumps(
        canonical_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "schema_version": "fin_ia_0_1_3_runtime_resource_registry_v1_0",
        "registry_id": (
            "FIN-0.1.2-S4-T06-A-CURRENT-PRODUCT-PROJECTION-REGISTRY-R1"
        ),
        "status": "tracked_typed_runtime_resource_authority",
        "policy": {
            "registry_is_source_of_truth": True,
            "static_scanner_is_detector_only": True,
            "direct_unregistered_runtime_read_fails_closed": True,
            "missing_unknown_duplicate_or_digest_drift_fails_closed": True,
            "permutation_or_cross_version_fails_closed": True,
            "ignored_untracked_codex_runtime_and_git_forbidden": True,
            "traversal_and_symlink_escape_forbidden": True,
        },
        "detector_python_refs": [
            "apps/workbench/backend/application/"
            "fin_0_1_2_s4_t06_current_product_projection.py"
        ],
        "resource_count": 1,
        "resource_bytes": len(value),
        "resource_canonical_digest": hashlib.sha256(canonical_bytes).hexdigest(),
        "resources": canonical_rows,
    }


def materialize_implementation_record(
    manifest: Mapping[str, Any],
    manifest_path: Path,
    registry_path: Path,
) -> dict[str, Any]:
    source_refs = [
        "apps/workbench/backend/app.py",
        "apps/workbench/backend/api/v1/current_product.py",
        (
            "apps/workbench/backend/application/"
            "fin_0_1_2_s4_t06_current_product_projection.py"
        ),
        (
            "scripts/releases/"
            "materialize_fin_ia_0_1_2_s4_t06_a_current_product_projection_manifest.py"
        ),
        (
            "tests/contract/"
            "test_fin_0_1_2_s4_t06_a_current_product_projection.py"
        ),
        manifest_path.resolve().relative_to(ROOT).as_posix(),
        registry_path.resolve().relative_to(ROOT).as_posix(),
    ]
    bindings = [
        {
            "ref": ref,
            "sha256": _sha256(ROOT / ref),
            "bytes": (ROOT / ref).stat().st_size,
        }
        for ref in source_refs
    ]
    body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t06_a_current_product_projection_read_only_"
            "service_and_api_zero_call_implementation_v1_0"
        ),
        "recorded_at": "2026-08-05T20:35:00+08:00",
        "status": "T06_A_engineering_pass_read_only_current_projection_available",
        "source_entry_decision": {
            "ref": ENTRY_DECISION_REF,
            "digest": ENTRY_DECISION_DIGEST,
        },
        "product_increment": {
            "current_cases": ["DELL", "MU", "NVDA"],
            "projection_surfaces": list(CURRENT_PRODUCT_SURFACES),
            "api_paths": [
                "GET /api/v1/current-product/cases",
                "GET /api/v1/current-product/cases/{case_key}",
                "GET /api/v1/current-product/cases/{case_key}/{surface}",
            ],
            "explicit_mode": "current",
            "required_permission": "current_product:read",
            "fixture_case_service_required": False,
            "frontend_integrated": False,
            "request_repair_available": False,
        },
        "manifest": {
            "ref": manifest_path.resolve().relative_to(ROOT).as_posix(),
            "digest": manifest["manifest_digest"],
            "sha256": _sha256(manifest_path),
            "bytes": manifest_path.stat().st_size,
            "current_three_case_evidence_numeric_gap_graph_artifact_owner": [
                45,
                9,
                9,
                0,
                27,
                3,
            ],
        },
        "code_and_contract_bindings": bindings,
        "verification": {
            "focused_T06_A_contracts": "12 passed",
            "current_T06_A_T05_Case_regression": "55 passed",
            "historical_fixture_RC_P36_127_regression": "1 passed / 10 failed",
            "historical_fixture_failure_set_changed": False,
            "manifest_regeneration_exact": True,
            "service_defensive_copy": True,
            "cross_case_digest_graph_raw_mutations_fail_closed": True,
            "current_API_methods": ["GET"],
            "new_model_provider_network_source_tool_calls": [0, 0, 0, 0, 0],
            "new_business_runtime_writes": 0,
        },
        "issue_disposition": {
            "RC_P36_126": "root_cause_fixed_by_T06_A_product_integration_pending_T06_B",
            "RC_P36_127": "unchanged_open_owned_by_T06_B_mode_isolation",
            "RC_P36_119_125": "unchanged_deferred_T08_T10_S5",
            "RC_P36_115": "unchanged_deferred_S5",
        },
        "acceptance_boundary": {
            "S4_T06_A_engineering": "pass",
            "S4_T06_current_backend_projection": "available_read_only",
            "S4_T06_B": "not_started",
            "S4_T06_product_acceptance": False,
            "qualified_human_review": False,
            "S4_T07": "not_entered",
            "S5": "not_entered",
            "release": "not_qualified",
            "production": "not_qualified",
        },
        "recommended_next": (
            "FIN-0.1.2-S4-T06-B-WORKBENCH-FRONTEND-CURRENT-MODE-"
            "CURRENT-FIXTURE-RUNTIME-ISOLATION-AND-BROWSER-MUTATION-"
            "ZERO-CALL-IMPLEMENTATION"
        ),
    }
    return {**body, "record_digest": canonical_digest(body)}


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == encoded:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--registry-output", type=Path, default=DEFAULT_REGISTRY_OUTPUT)
    parser.add_argument(
        "--implementation-output",
        type=Path,
        default=DEFAULT_IMPLEMENTATION_OUTPUT,
    )
    args = parser.parse_args()
    manifest_path = args.manifest_output.resolve()
    registry_path = args.registry_output.resolve()
    implementation_path = args.implementation_output.resolve()
    manifest = materialize_manifest()
    _write_atomic(manifest_path, manifest)
    registry = materialize_registry(manifest_path)
    _write_atomic(registry_path, registry)
    implementation = materialize_implementation_record(
        manifest, manifest_path, registry_path
    )
    _write_atomic(implementation_path, implementation)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "manifest": manifest_path.as_posix(),
                "manifest_digest": manifest["manifest_digest"],
                "registry": registry_path.as_posix(),
                "implementation": implementation_path.as_posix(),
                "implementation_digest": implementation["record_digest"],
                "cases": len(manifest["cases"]),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
