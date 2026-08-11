from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
)
from apps.workbench.backend.application.case_service import (  # noqa: E402
    CasePrincipal,
    CaseService,
    CreateCaseDraft,
)
from apps.workbench.backend.application.evidence_service import (  # noqa: E402
    EvidenceService,
)
from apps.workbench.backend.application.planning_service import (  # noqa: E402
    CompileDecisionSurfaceDraft,
    PlanningCheckpointDecisionDraft,
    PlanningService,
)
from apps.workbench.backend.application.research_runtime import (  # noqa: E402
    prepare_s4_source_grounded_exact_input,
)
from sec_agent.canonical_runtime import (  # noqa: E402
    FileCanonicalObjectStore,
    RuntimeFacade,
)
from sec_agent.canonical_runtime.feature_flags import (  # noqa: E402
    FeatureFlagRegistry,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.canonical_runtime.store import (  # noqa: E402
    SQLiteCanonicalStore,
)
from sec_agent.s4_case_runtime import (  # noqa: E402
    S4SourceGroundedInputPack,
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
SOURCE_PACK_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_source_grounded_input_pack_v1_0.json"
)
PLANNING_PROFILE_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_canonical_planning_profile_v1_0.json"
)
DECISION_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_canonical_case_surface_and_fresh_exact_"
    "admission_preparation_zero_call_proof_v1_0.json"
)
PROSPECTIVE_ADMISSION_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_fresh_exact_admission_r1.json"
)
FROZEN_AT = "2026-07-29T13:00:00+08:00"
TENANT_ID = "tenant-fin01-s3-t09-eval"
PROJECT_ID = "project-fin01-s3-t09-eval"
ACTOR_ID = "analyst-fin01-s3-t09-eval"
CASE_IDEMPOTENCY_KEY = "fin01-s4-t06-mu-canonical-case-v1"
EXECUTION_IDENTITY = "fin01-s4-t06-mu-fresh-exact-live-r1"
PLANNING_COMPILER_POLICY_REF = "fin01.s4.mu_three_cell:v1"
PLANNING_PACK_SELECTION_REF = "fin01.s4.mu_hbm_source_grounded:v1"
SOURCE_POLICY_REF = "fin01.s4.public_local_official_case_pack:v1"
QUERY = (
    "Assess Micron HBM demand durability, value and profit capture, cycle "
    "exposure, and bottleneck counterevidence using issuer-bound official "
    "evidence."
)
PERMISSIONS = frozenset(
    {
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "evidence:read",
    }
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_planning_profile() -> dict[str, Any]:
    binding = load_s4_case_runtime_binding(ROOT, "MU")
    cells = []
    for row in binding.program_cell_contracts:
        cell_key = str(row["program_cell_id"])
        cells.append(
            {
                "cell_key": cell_key,
                "decision_question": row["decision_question"],
                "owner_role": row["owner_role"],
                "materiality": "high",
                "dependency_cell_keys": (
                    []
                    if cell_key == "demand_authenticity_and_sustainability"
                    else ["demand_authenticity_and_sustainability"]
                ),
                "stop_rule": row["stop_rule"],
                "what_would_change": "; ".join(
                    row["what_would_change_targets"]
                ),
                "evidence_slots": [
                    {
                        "evidence_role": role,
                        "entity_scope": ["MU"],
                        "period_scope": "through_2026-07-26",
                        "metric_scope": [role],
                        "source_policy_ref": SOURCE_POLICY_REF,
                        "forbidden_substitutions": [
                            "cross_issuer_fact",
                            "graph_edge_as_evidence",
                            "model_output_as_source",
                        ],
                        "acceptance_role": row["owner_role"],
                        "required": True,
                    }
                    for role in row["required_evidence_roles"]
                ],
            }
        )
    return {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_canonical_planning_profile_v1_0"
        ),
        "profile_id": "FIN-IA-0.1-S4-T06-MU-CANONICAL-PLANNING-R1",
        "status": "source_grounded_three_cell_planning_profile_ready",
        "planning_profile": {
            "compiler_policy_ref": PLANNING_COMPILER_POLICY_REF,
            "pack_selection_ref": PLANNING_PACK_SELECTION_REF,
            "exact_cell_count": 3,
            "cells": cells,
        },
    }


def _principal() -> CasePrincipal:
    return CasePrincipal(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        actor_id=ACTOR_ID,
        permissions=PERMISSIONS,
    )


def _case_service(
    canonical_root: Path, planning_profile: Mapping[str, Any]
) -> CaseService:
    flags = FeatureFlagRegistry.from_path(
        ROOT / "configs" / "runtime" / "point01_feature_flags_v1_0.json"
    )
    facade = RuntimeFacade(
        SQLiteCanonicalStore(canonical_root / "canonical.sqlite"),
        FileCanonicalObjectStore(canonical_root / "objects"),
        flags,
        mode="shadow",
        grants={"point01.shadow.write"},
        planning_fixture_profile=planning_profile,
    )
    return CaseService(facade)


def _execution_identity_presence(
    service: CaseService, prepared: Mapping[str, Any]
) -> dict[str, bool]:
    store = service._facade.store
    return {
        "work_unit_absent": store.get_latest(
            "canonical_work_units", str(prepared["work_unit_id"])
        )
        is None,
        "attempt_absent": store.get_latest(
            "canonical_attempts", str(prepared["attempt_id"])
        )
        is None,
        "research_run_absent": store.get_latest(
            "canonical_research_run_versions",
            str(prepared["research_run_id"]),
        )
        is None,
    }


def _materialize_once(
    canonical_root: Path,
    planning_profile: Mapping[str, Any],
    source_pack: S4SourceGroundedInputPack,
) -> dict[str, Any]:
    binding = load_s4_case_runtime_binding(ROOT, "MU")
    service = _case_service(canonical_root, planning_profile)
    principal = _principal()
    workspace = service.create_case(
        CreateCaseDraft(
            query=QUERY,
            as_of=datetime.fromisoformat(
                source_pack.as_of.replace("Z", "+00:00")
            ),
            language="zh-CN",
            source_policy_ref=SOURCE_POLICY_REF,
            idempotency_key=CASE_IDEMPOTENCY_KEY,
        ),
        principal,
        trace_id="fin01-s4-t06-mu-case-materialization",
    )
    planning = PlanningService.from_case_service(service)
    surface = planning.compile_decision_surface(
        workspace["case_id"],
        CompileDecisionSurfaceDraft(
            expected_case_version=workspace["case_version"],
            expected_summary_version=workspace["summary_version"],
            compiler_policy_ref=PLANNING_COMPILER_POLICY_REF,
            pack_selection_ref=PLANNING_PACK_SELECTION_REF,
            actor_ref=ACTOR_ID,
            idempotency_key="fin01-s4-t06-mu-planning-compile-v1",
        ),
        principal,
        trace_id="fin01-s4-t06-mu-planning-compile",
    )
    accepted = planning.review_planning_checkpoint(
        workspace["case_id"],
        PlanningCheckpointDecisionDraft(
            decision="accept",
            expected_case_version=workspace["case_version"],
            expected_decision_surface_contract_version=surface[
                "contract_version"
            ],
            expected_checkpoint_version=surface["checkpoint_version"],
            actor_ref=ACTOR_ID,
            idempotency_key="fin01-s4-t06-mu-planning-accept-v1",
        ),
        principal,
        trace_id="fin01-s4-t06-mu-planning-accept",
    )
    if (
        len(accepted["cells"]) != 3
        or accepted["review_status"] != "accepted"
    ):
        raise RuntimeError("s4_mu_canonical_surface_not_accepted_three_cell")
    prepared = prepare_s4_source_grounded_exact_input(
        service,
        EvidenceService.from_case_service(service, repo_root=ROOT),
        binding,
        source_pack,
        workspace["case_id"],
        principal,
        decision_surface_contract_ref=accepted["contract_version_id"],
        execution_identity=EXECUTION_IDENTITY,
    )
    prepared_payload = prepared.model_dump(mode="json")
    object_ref = service._facade.object_store.put_json(
        prepared_payload,
        namespace="fin01/s4/exact-input-heads",
        artifact_type="mu_source_grounded_prepared_input",
    )
    freshness = _execution_identity_presence(service, prepared_payload)
    if not all(freshness.values()):
        raise RuntimeError("s4_mu_fresh_identity_reused")
    return {
        "case": workspace,
        "decision_surface": accepted,
        "prepared": prepared_payload,
        "input_object_ref": object_ref,
        "freshness_and_nonreuse": freshness,
    }


def _logical_counts(database_path: Path, case_id: str) -> dict[str, int]:
    connection = sqlite3.connect(database_path)
    try:
        counts = {}
        for table in (
            "canonical_research_cases",
            "canonical_case_control_versions",
            "canonical_decision_surface_contract_versions",
            "canonical_decision_surface_cell_versions",
            "canonical_evidence_slot_versions",
            "canonical_planning_checkpoint_versions",
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
        ):
            counts[table] = sum(
                1
                for (payload_json,) in connection.execute(
                    f"select payload_json from {table}"
                )
                if json.loads(payload_json).get("case_id") == case_id
            )
        return counts
    finally:
        connection.close()


def _database_logical_digest(database_path: Path) -> str:
    connection = sqlite3.connect(database_path)
    try:
        payload: dict[str, list[list[Any]]] = {}
        table_names = [
            str(row[0])
            for row in connection.execute(
                "select name from sqlite_master "
                "where type='table' and name not like 'sqlite_%' "
                "order by name"
            )
        ]
        for table in table_names:
            columns = [
                str(row[1])
                for row in connection.execute(f"pragma table_info({table})")
            ]
            order = "row_id" if "row_id" in columns else columns[0]
            payload[table] = [
                [
                    value.hex() if isinstance(value, bytes) else value
                    for value in row
                ]
                for row in connection.execute(
                    f"select * from {table} order by {order}"
                )
            ]
        return canonical_digest(payload)
    finally:
        connection.close()


def _prospective_admission(
    materialized: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    prepared = materialized["prepared"]
    binding = load_s4_case_runtime_binding(ROOT, "MU")
    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id="fin01-s4-t06-mu-fresh-exact-admission-r1",
        output_contract_ref="fin01.s3.bounded_agent_three_cell_output:v4",
        execution_enabled=True,
        execution_mode="exact_live_s4_mu_source_grounded_three_cell_r1",
        research_profile_ref=binding.research_profile_ref,
        company="MU",
        program_cell_ids=binding.program_cell_ids,
        case_id=prepared["case_id"],
        case_version=prepared["case_version"],
        as_of=prepared["input_pack"]["as_of"],
        input_digest=prepared["input_digest"],
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/beta",
        transport_ref=(
            "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v7"
        ),
        research_lead_transport_ref=(
            "fin01.s3.bounded_agent.research_lead_owner_grade:v5"
        ),
        memo_writer_transport_ref=(
            "fin01.s3.bounded_agent.memo_writer_owner_grade:v3"
        ),
        scoped_identity_contract_ref=(
            "fin01.s3.cell_scoped_research_identity:v1"
        ),
        claim_fact_link_policy_ref="fin01.s3.claim_fact_link_policy:v1",
        provider_output_capture_policy_ref=(
            "fin01.s3.provider_output_capture.assistant_final_text_only:v1"
        ),
        max_semantic_model_calls=12,
        max_provider_calls=12,
        max_network_calls=12,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=4200,
        lead_max_output_tokens=1800,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
        timeout_seconds=120,
        max_transport_attempts_per_call=1,
        retry_budget=0,
        source_network_calls_allowed=False,
        external_tool_calls_allowed=False,
        live_business_case_head_writes_allowed=False,
    )
    admission.assert_profile_admissible()
    payload = admission.digest_payload()
    digest = canonical_digest(payload)
    roundtrip = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    if canonical_digest(roundtrip.digest_payload()) != digest:
        raise RuntimeError("s4_mu_admission_digest_not_roundtrip_stable")
    return payload, digest


def prepare(runtime_root: Path = RUNTIME_ROOT) -> dict[str, Any]:
    existing_decision = (
        json.loads(DECISION_PATH.read_text(encoding="utf-8"))
        if DECISION_PATH.is_file()
        else {}
    )
    planning_profile = _build_planning_profile()
    _write_json(PLANNING_PROFILE_PATH, planning_profile)
    source_pack = load_s4_source_grounded_input_pack(ROOT, "MU")
    if source_pack.case_ticker != "MU":
        raise RuntimeError("s4_mu_source_pack_identity_mismatch")

    canonical_root = runtime_root.resolve() / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    if not database_path.is_file():
        raise RuntimeError("s4_mu_target_canonical_runtime_missing")
    before_target_digest = _sha256(database_path)
    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t06-mu-input-materialization-"
    ) as temp_dir:
        clone_root = Path(temp_dir) / "canonical-runtime"
        shutil.copytree(canonical_root, clone_root)
        clone_first = _materialize_once(
            clone_root, planning_profile, source_pack
        )
        clone_first_digest = _database_logical_digest(
            clone_root / "canonical.sqlite"
        )
        clone_second = _materialize_once(
            clone_root, planning_profile, source_pack
        )
        clone_second_digest = _database_logical_digest(
            clone_root / "canonical.sqlite"
        )
        if (
            clone_first["prepared"] != clone_second["prepared"]
            or clone_first["decision_surface"]
            != clone_second["decision_surface"]
            or clone_first_digest != clone_second_digest
        ):
            raise RuntimeError("s4_mu_clone_materialization_not_idempotent")

    target_first = _materialize_once(
        canonical_root, planning_profile, source_pack
    )
    after_first_digest = _sha256(database_path)
    after_first_logical_digest = _database_logical_digest(database_path)
    target_second = _materialize_once(
        canonical_root, planning_profile, source_pack
    )
    after_second_digest = _sha256(database_path)
    after_second_logical_digest = _database_logical_digest(database_path)
    if (
        target_first["prepared"] != target_second["prepared"]
        or target_first["decision_surface"]
        != target_second["decision_surface"]
        or after_first_logical_digest != after_second_logical_digest
    ):
        raise RuntimeError("s4_mu_target_materialization_not_idempotent")

    prospective_payload, prospective_digest = _prospective_admission(
        target_first
    )
    if PROSPECTIVE_ADMISSION_PATH.exists():
        raise RuntimeError("s4_mu_prospective_admission_file_must_be_absent")
    case_id = target_first["case"]["case_id"]
    prepared = target_first["prepared"]
    existing_materialization = existing_decision.get(
        "canonical_materialization", {}
    )
    preserve_first_materialization_audit = (
        existing_materialization.get("case_id") == case_id
        and existing_materialization.get(
            "logical_digest_after_second_materialization"
        )
        == after_second_logical_digest
    )
    if preserve_first_materialization_audit:
        database_sha256_before = existing_materialization[
            "database_sha256_before"
        ]
        database_sha256_after_first_materialization = (
            existing_materialization[
                "database_sha256_after_first_materialization"
            ]
        )
        database_sha256_after = existing_materialization[
            "database_sha256_after"
        ]
    else:
        database_sha256_before = before_target_digest
        database_sha256_after_first_materialization = after_first_digest
        database_sha256_after = after_second_digest

    decision = {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_canonical_case_surface_and_fresh_exact_"
            "admission_preparation_zero_call_proof_v1_0"
        ),
        "decision_id": (
            "S4-T06-MU-CANONICAL-CASE-SURFACE-AND-FRESH-EXACT-"
            "ADMISSION-PREPARATION-ZERO-CALL-PROOF-R1"
        ),
        "decided_at": FROZEN_AT,
        "status": (
            "pass_MU_canonical_case_surface_exact_input_materialized_"
            "fresh_admission_frozen_unissued_zero_call"
        ),
        "authority": {
            "user_instruction": "继续",
            "authorized_scope": (
                "S4-T06 MU canonical Case, DecisionSurface, exact-input "
                "materialization and fresh admission preparation only"
            ),
            "model_or_provider_calls_authorized": False,
            "admission_issuance_authorized": False,
            "exact_live_authorized": False,
        },
        "selected_mainline": {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "model_tier": "pro_not_flash",
            "base_url": "https://api.deepseek.com/beta",
            "api_key_env": "DEEPSEEK_API_KEY",
        },
        "source_execution": {
            "source_pack_ref": SOURCE_PACK_PATH.relative_to(ROOT).as_posix(),
            "source_pack_sha256": _sha256(SOURCE_PACK_PATH),
            "source_pack_digest": source_pack.source_pack_digest,
            "source_snapshot_count": len(source_pack.source_snapshots),
            "route_receipt_count": len(
                source_pack.route_execution_receipts
            ),
            "evidence_row_count": len(source_pack.evidence_rows),
            "numeric_row_count": len(source_pack.numeric_rows),
            "derived_metric_count": len(source_pack.derived_metrics),
            "context_only_graph_edge_count": len(source_pack.graph_edges),
            "typed_gap_count": len(source_pack.typed_gaps),
        },
        "planning_profile": {
            "ref": PLANNING_PROFILE_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha256(PLANNING_PROFILE_PATH),
            "compiler_policy_ref": PLANNING_COMPILER_POLICY_REF,
            "pack_selection_ref": PLANNING_PACK_SELECTION_REF,
            "cell_count": 3,
            "evidence_slot_count": sum(
                len(row["evidence_slots"])
                for row in planning_profile["planning_profile"]["cells"]
            ),
        },
        "canonical_materialization": {
            "runtime_root": runtime_root.relative_to(ROOT).as_posix(),
            "database_ref": database_path.relative_to(ROOT).as_posix(),
            "database_sha256_before": database_sha256_before,
            "database_sha256_after": database_sha256_after,
            "database_sha256_after_first_materialization": (
                database_sha256_after_first_materialization
            ),
            "logical_digest_after_first_materialization": (
                after_first_logical_digest
            ),
            "logical_digest_after_second_materialization": (
                after_second_logical_digest
            ),
            "idempotent_second_materialization": True,
            "case_id": case_id,
            "case_version": prepared["case_version"],
            "decision_surface_contract_ref": prepared[
                "decision_surface_contract_ref"
            ],
            "planning_checkpoint_status": target_first[
                "decision_surface"
            ]["review_status"],
            "planning_cell_count": len(
                target_first["decision_surface"]["cells"]
            ),
            "input_head_digest": prepared["input_pack"][
                "input_head_digest"
            ],
            "input_object_ref": target_first["input_object_ref"],
            "logical_counts": _logical_counts(database_path, case_id),
        },
        "fresh_agent_proof": {
            "decision": "frozen_unissued_unconsumed",
            "execution_identity": prepared["execution_identity"],
            "work_unit_id": prepared["work_unit_id"],
            "attempt_id": prepared["attempt_id"],
            "research_run_id": prepared["research_run_id"],
            "input_digest": prepared["input_digest"],
            "preparation_digest": prepared["preparation_digest"],
            "freshness_and_nonreuse": target_first[
                "freshness_and_nonreuse"
            ],
            "double_prepare_parity": True,
            "prospective_admission": {
                "payload": prospective_payload,
                "digest": prospective_digest,
                "prospective_admission_file": (
                    PROSPECTIVE_ADMISSION_PATH.relative_to(ROOT).as_posix()
                ),
                "prospective_admission_file_absent": True,
                "issued": False,
                "consumed": False,
                "execution_started": False,
            },
        },
        "truth_and_scope_boundaries": {
            "HBM_specific_revenue_or_profit_inferred": False,
            "customer_concentration_or_identity_inferred": False,
            "forward_demand_or_capacity_realized_as_fact": False,
            "graph_promoted_to_direct_evidence": False,
            "strict_schema_transport_reactivated": False,
        },
        "hard_boundaries": {
            "new_source_network_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "paid_calls": 0,
            "admission_files_written": 0,
            "work_units_created": 0,
            "attempts_created": 0,
            "research_runs_created": 0,
            "business_artifacts_created": 0,
            "human_acceptance_completed": False,
        },
        "stage_acceptance": {
            "S4_T06": "in_progress_pre_admission_zero_call_proof_passed",
            "MU_R2": "not_started",
            "S4_pass": False,
            "S5": "blocked",
        },
        "next_action": "S4-T06-MU-FRESH-EXACT-ADMISSION-ISSUANCE",
    }
    _write_json(DECISION_PATH, decision)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=RUNTIME_ROOT,
    )
    args = parser.parse_args()
    result = prepare(args.runtime_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
