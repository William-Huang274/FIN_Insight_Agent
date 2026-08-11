from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


CASE_SOURCES = {
    "DELL": {
        "owner": ROOT / "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_owner_acceptance_and_closeout_v1_0.json",
        "owner_sha256": "4853130573d8431c7c57fa2dc4d8d6a3b249810a4a78ff1b5201375083ad471a",
        "owner_digest": "a03a10716d816d32835f6e691057a43c439e9f6675c8e53f7db0eeb37d836468",
        "evidence": ROOT / "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_evidence_pack_v1_0.json",
        "evidence_sha256": "34ad6a388e08c7b8518487902f2934a2d046131676d519c5f84a28bc157ec3ae",
        "evidence_digest": "2a3379f08c2207f914ddd4ca7e8b656f8a860847a2a7d660f845f35eed469502",
        "exact": ROOT / ".codex_runtime/fin012-s4-t05b-dell-agent-exact-live-r1/execution-result.json",
        "exact_sha256": "b4edc0927e958b812c5e5dd04d982defa97e64255d24e3a569e5311b78f5dd32",
        "surface": ROOT / "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_verified_product_surface_and_paired_readiness_v1_0.json",
        "surface_sha256": "9d3395ae846c43d3e72d5151e98f710821fe1b4a07d1faa3f7ead177fd7593ef",
        "surface_digest": "9bb1cfa91c35980fbc1cc323fb0fe996298595c86f1128fec5a37e9c4072a529",
    },
    "MU": {
        "owner": ROOT / "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_owner_acceptance_and_closeout_v1_0.json",
        "owner_sha256": "bee72100a29c004928a27cd1136ca0da91dd0d94a11f9b1bc8e5693fe1cb391d",
        "owner_digest": "70fc169f38cd4ee73a6be057c089894bc3dae02c19ab4e2ed016398b86265912",
        "evidence": ROOT / "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_current_evidence_pack_v1_0.json",
        "evidence_sha256": "805ca00b088ee73b292cc384a47577480c60b0e710d4cb166ebfebbc6b979ff4",
        "evidence_digest": "ef1895fe4c113c5e2d952178fc715fb3f5a4eb1ca30a784431c74cf744df433d",
        "exact": ROOT / ".codex_runtime/fin012-s4-t05c-mu-agent-exact-live-r1/execution-result.json",
        "exact_sha256": "c7bdf239e3f6fe1e980be856448ae7549e3401276c91805444b41e39cd1b3602",
        "surface": ROOT / "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_verified_product_surface_and_paired_readiness_v1_0.json",
        "surface_sha256": "a4f5d9e26f408484e1aa234323e28269360a66d41128485b0a7d50d0992c4e58",
        "surface_digest": "c9608e312fe7bf6e3b77ba86b50b533456461c45297060311cc3fc85dea15272",
    },
    "NVDA": {
        "owner": ROOT / "configs/releases/fin_ia_0_1_2_s4_t05_d_nvda_owner_acceptance_and_closeout_v1_0.json",
        "owner_sha256": "8d5cabe1449067e98582580dc21608ed53b4a2cc3d0a1100bd1b29657f3a5cf4",
        "owner_digest": "4e15a44d442cd42dc6c16edd61510d8a3518048eae63456904d153888c467a9d",
        "evidence": ROOT / "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_pack_v1_0.json",
        "evidence_sha256": "9fd5484d403814b59fd497b85c0904836571caaae439207438e295dc554aecd2",
        "evidence_digest": "fdc1a10010f0d47ba7be5b420fc5cac860c3044d6690696463865ecce4b7bf65",
        "exact": ROOT / ".codex_runtime/fin012-s4-t05d-nvda-post-transfer-agent-exact-live-r1/execution-result.json",
        "exact_sha256": "200907cf4c0f6a58748b12f44a4c874ff0b53bd74fe69e22e2d28d117f72bbc4",
        "surface": ROOT / "configs/releases/fin_ia_0_1_2_s4_t05_d_nvda_verified_product_surface_and_paired_readiness_v1_0.json",
        "surface_sha256": "3ad7528dffdee0cdcd726c641981662930459565b683444a42863cce8a8cd9e0",
        "surface_digest": "6b6098cc17817e2f1fd9636262144060a300ce7edb8071b79f4f4e84b3931ec8",
    },
}

DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t06_workbench_current_product_"
    "projection_entry_and_dependency_decision_v1_0.json"
)


class S4T06WorkbenchEntryDecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06WorkbenchEntryDecisionError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t06_entry_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case_inventory(ticker: str, source: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("owner", "evidence", "exact", "surface"):
        _require(
            _sha256(source[key]) == source[f"{key}_sha256"],
            f"s4_t06_entry_{ticker.lower()}_{key}_drift",
        )
    owner = _load(source["owner"])
    evidence = _load(source["evidence"])
    exact = _load(source["exact"])
    surface = _load(source["surface"])
    _require(
        owner.get("decision_digest") == source["owner_digest"]
        and owner.get("owner_decision", {}).get("material_gain_accepted") is True,
        f"s4_t06_entry_{ticker.lower()}_owner_not_accepted",
    )
    _require(
        evidence.get("case_key") == ticker
        and evidence.get("evidence_pack_digest") == source["evidence_digest"]
        and len(evidence.get("evidence_rows") or ()) == 15
        and len(evidence.get("numeric_rows") or ()) == 3
        and len(evidence.get("typed_gaps") or ()) == 3,
        f"s4_t06_entry_{ticker.lower()}_evidence_shape_invalid",
    )
    _require(
        exact.get("status") == "success"
        and exact.get("business_promotable") is True
        and len(exact.get("artifacts") or ()) == 9
        and len(exact.get("capture_objects") or ()) == 9,
        f"s4_t06_entry_{ticker.lower()}_exact_result_invalid",
    )
    _require(
        surface.get("record_digest") == source["surface_digest"],
        f"s4_t06_entry_{ticker.lower()}_surface_drift",
    )
    artifact_types = [row.get("artifact_type") for row in exact["artifacts"]]
    _require(
        artifact_types
        == [
            "bounded_agent_manifest",
            "bounded_agent_evidence",
            "bounded_agent_numeric",
            "bounded_agent_judgment",
            "bounded_agent_workpaper",
            "bounded_agent_report",
            "bounded_agent_trace",
            "bounded_agent_verification",
            "agent_fallback_comparison",
        ],
        f"s4_t06_entry_{ticker.lower()}_artifact_topology_invalid",
    )
    approved_graph_evidence = sum(
        "graph" in json.dumps(row, ensure_ascii=False).lower()
        for row in evidence["evidence_rows"]
    )
    return {
        "ticker": ticker,
        "case_key": evidence["case_key"],
        "as_of": evidence["as_of"],
        "natural_objective": evidence["natural_objective"],
        "evidence_pack_ref": source["evidence"].relative_to(ROOT).as_posix(),
        "evidence_pack_digest": source["evidence_digest"],
        "evidence_numeric_typed_gap": [15, 3, 3],
        "approved_graph_evidence": approved_graph_evidence,
        "graph_product_state": (
            "approved_current_graph_evidence_available"
            if approved_graph_evidence
            else "typed_empty_no_approved_current_graph_evidence"
        ),
        "exact_result_ref": source["exact"].relative_to(ROOT).as_posix(),
        "exact_result_sha256": source["exact_sha256"],
        "provider_capture_artifact": [9, 9, 9],
        "artifact_types": artifact_types,
        "surface_ref": source["surface"].relative_to(ROOT).as_posix(),
        "surface_record_digest": source["surface_digest"],
        "owner_ref": source["owner"].relative_to(ROOT).as_posix(),
        "owner_decision_digest": source["owner_digest"],
        "R2": True,
    }


def materialize() -> dict[str, Any]:
    inventories = [
        _case_inventory(ticker, source) for ticker, source in CASE_SOURCES.items()
    ]
    body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t06_workbench_current_product_projection_"
            "entry_and_dependency_decision_v1_0"
        ),
        "recorded_at": "2026-08-05T19:10:00+08:00",
        "status": "T06_entry_authorized_current_product_projection_binding_blocked",
        "authority": {
            "source_T05_D_owner_decision": CASE_SOURCES["NVDA"]["owner_digest"],
            "S4_T06_entry_authorized": True,
            "implementation_authorized": False,
            "model_provider_network_source_calls_authorized": False,
            "current_product_projection_claim_authorized": False,
        },
        "current_three_case_assets": inventories,
        "workbench_existing_reusable_surfaces": {
            "backend_routes": [
                "Case and Task Center",
                "Execution and Research Run",
                "Evidence review",
                "Numeric and Workpaper",
                "Deliverable review and Trace",
            ],
            "frontend_components": [
                "TaskCenter",
                "CaseOverview",
                "ActivityTrace",
                "EvidenceWorkbench",
                "NumericWorkbench",
                "WorkpaperReview",
                "DeliverableReview",
            ],
            "reusable_boundary": (
                "Reuse typed route/component shapes and canonical read-model patterns; "
                "do not reuse fixture content as current product evidence, and do not "
                "assume the historical fixture workflow is regression-green."
            ),
        },
        "historical_workbench_regression_audit": {
            "issue": "RC-P36-127",
            "status": "open_nonblocking_for_T06_A_owned_by_T06_B_mode_isolation",
            "observed_selected_regression": {
                "total": 54,
                "passed": 44,
                "failed": 10,
                "common_failure": "exactly_one_pending_evidence_fixture_work_unit_required",
            },
            "root_cause_proof": {
                "default_create_app_work_unit_state": "succeeded",
                "default_create_app_evidence_compile_status": 409,
                "explicit_no_runtime_work_unit_state": "pending",
                "explicit_no_runtime_evidence_compile_status": 202,
                "cause": (
                    "create_app now auto-wires Fin01ResearchRuntime and background-dispatches "
                    "the legacy fixture WorkUnit before the historical Evidence compiler can "
                    "consume its required pending state."
                ),
            },
            "disposition": (
                "Do not repair this inside T06-A. T06-B must separate current read-only mode "
                "from legacy fixture execution mode and restore or replace the fixture contract "
                "without weakening current-product truth."
            ),
            "model_or_provider_fault": False,
            "T05_current_asset_failure": False,
        },
        "earliest_owned_blocker": {
            "issue": "RC-P36-126",
            "status": "open_T06_blocker",
            "layer": "S4_T06_Workbench_current_product_read_projection_binding",
            "evidence": [
                "CaseService is explicitly fixture-only and defaults to unavailable without FINSIGHT_P02_FIXTURE_ROOT.",
                "EvidenceService consumes the zero-call fixture contract through the fixture CaseService facade.",
                "The frontend default principal remains tenant=fixture_internal.",
                "No Workbench service binds the three accepted T05 Evidence Packs, exact results, product surfaces and Owner decisions into one current read model.",
                "There is no explicit current Graph or quality/Owner projection; approved Graph evidence is empty in all three current Evidence Packs.",
            ],
            "root_cause": (
                "Current live research assets and the historical Workbench evolved in separate "
                "stores and contracts. T05 proved immutable product artifacts, while Workbench "
                "still reads fixture/shadow canonical rows and has no digest-bound adapter."
            ),
            "model_or_provider_fault": False,
            "external_boundary": False,
        },
        "scope_disposition": {
            "T06_owned": [
                "digest-bound three-case CurrentProductProjectionManifest",
                "read-only projection compiler/service/API",
                "current Case/Run/Evidence/Numeric/Graph-empty/Gap/Workpaper/Report/Trace/quality views",
                "explicit current-versus-fixture labeling with no automatic fallback",
                "typed return/request-repair action contract and browser product replay",
                "current/fixture execution-mode isolation for RC-P36-127 in T06-B",
            ],
            "T07_owned": [
                "qualified Human Review execution",
                "exact review digest binding",
                "NVDA R3 decision and review burden",
            ],
            "T08_T10_S5_owned": [
                "RC-P36-119 WWC calibration",
                "RC-P36-125 Lead synthesis calibration",
                "cross-runtime exact-once lock and release hardening",
            ],
            "not_allowed": [
                "copy fixture rows and relabel them current",
                "promote raw provider captures into product content",
                "invent Graph edges when approved graph evidence is absent",
                "write T05 immutable artifacts into a second business source of truth",
                "call a model, Provider, source network or external tool in T06 entry",
            ],
        },
        "bounded_T06_sequence": [
            {
                "task": "T06-A",
                "scope": "three-case manifest plus read-only projection compiler/service/API",
                "status": "authorized_next_not_started",
            },
            {
                "task": "T06-B",
                "scope": (
                    "frontend current-mode integration, current/fixture runtime-mode isolation "
                    "for RC-P36-127, and cross-case/browser mutation"
                ),
                "status": "blocked_by_T06_A",
            },
            {
                "task": "T06-C",
                "scope": "typed return/request-repair envelope, replay and T07 handoff readiness",
                "status": "blocked_by_T06_B",
            },
        ],
        "acceptance_boundary": {
            "T05_three_case_R2": "pass_closed",
            "S4_T06_entry": "pass",
            "S4_T06_engineering": "not_started",
            "S4_T06_product_projection": "blocked_RC_P36_126",
            "S4_T07": "not_entered",
            "S4_product_acceptance": False,
            "S5": "not_entered",
            "release": "not_qualified",
            "production": "not_qualified",
        },
        "observed_counts": {
            "cases": 3,
            "evidence_rows": 45,
            "numeric_rows": 9,
            "typed_gaps": 9,
            "approved_graph_evidence": sum(
                row["approved_graph_evidence"] for row in inventories
            ),
            "business_artifacts": 27,
            "owner_acceptances": 3,
            "new_model_calls": 0,
            "new_provider_calls": 0,
            "new_network_calls": 0,
            "new_source_calls": 0,
            "new_external_tool_calls": 0,
            "new_runtime_writes": 0,
        },
        "recommended_next": (
            "FIN-0.1.2-S4-T06-A-THREE-CASE-CURRENT-PRODUCT-PROJECTION-"
            "MANIFEST-READ-ONLY-SERVICE-AND-API-ZERO-CALL-IMPLEMENTATION"
        ),
    }
    return validate_entry_decision(
        {**body, "decision_digest": canonical_digest(body)}
    )


def validate_entry_decision(value: Mapping[str, Any]) -> dict[str, Any]:
    body = {key: row for key, row in value.items() if key != "decision_digest"}
    _require(
        value.get("decision_digest") == canonical_digest(body),
        "s4_t06_entry_decision_digest_mismatch",
    )
    authority = value.get("authority") or {}
    blocker = value.get("earliest_owned_blocker") or {}
    regression = value.get("historical_workbench_regression_audit") or {}
    boundary = value.get("acceptance_boundary") or {}
    counts = value.get("observed_counts") or {}
    sequence = value.get("bounded_T06_sequence") or ()
    _require(
        value.get("status")
        == "T06_entry_authorized_current_product_projection_binding_blocked"
        and authority.get("S4_T06_entry_authorized") is True
        and authority.get("implementation_authorized") is False
        and authority.get("model_provider_network_source_calls_authorized") is False
        and blocker.get("issue") == "RC-P36-126"
        and blocker.get("model_or_provider_fault") is False,
        "s4_t06_entry_authority_or_blocker_invalid",
    )
    _require(
        regression.get("issue") == "RC-P36-127"
        and regression.get("model_or_provider_fault") is False
        and regression.get("T05_current_asset_failure") is False
        and (regression.get("observed_selected_regression") or {}).get("failed") == 10
        and (regression.get("root_cause_proof") or {}).get(
            "default_create_app_evidence_compile_status"
        )
        == 409
        and (regression.get("root_cause_proof") or {}).get(
            "explicit_no_runtime_evidence_compile_status"
        )
        == 202,
        "s4_t06_entry_historical_workbench_regression_disposition_invalid",
    )
    _require(
        len(value.get("current_three_case_assets") or ()) == 3
        and counts.get("cases") == 3
        and counts.get("evidence_rows") == 45
        and counts.get("numeric_rows") == 9
        and counts.get("typed_gaps") == 9
        and counts.get("approved_graph_evidence") == 0
        and counts.get("business_artifacts") == 27
        and counts.get("owner_acceptances") == 3,
        "s4_t06_entry_current_asset_inventory_invalid",
    )
    _require(
        [row.get("task") for row in sequence] == ["T06-A", "T06-B", "T06-C"]
        and sequence[0].get("status") == "authorized_next_not_started"
        and boundary.get("S4_T06_entry") == "pass"
        and boundary.get("S4_T06_engineering") == "not_started"
        and boundary.get("S4_T06_product_projection") == "blocked_RC_P36_126"
        and boundary.get("S4_T07") == "not_entered"
        and boundary.get("S4_product_acceptance") is False
        and boundary.get("release") == "not_qualified",
        "s4_t06_entry_sequence_or_boundary_invalid",
    )
    _require(
        all(
            counts.get(key) == 0
            for key in (
                "new_model_calls",
                "new_provider_calls",
                "new_network_calls",
                "new_source_calls",
                "new_external_tool_calls",
                "new_runtime_writes",
            )
        ),
        "s4_t06_entry_zero_call_boundary_invalid",
    )
    return dict(value)


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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    decision = materialize()
    _write_atomic(args.output.resolve(), decision)
    print(
        json.dumps(
            {
                "status": decision["status"],
                "output": args.output.resolve().as_posix(),
                "decision_digest": decision["decision_digest"],
                "blocker": decision["earliest_owned_blocker"]["issue"],
                "next": decision["recommended_next"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
