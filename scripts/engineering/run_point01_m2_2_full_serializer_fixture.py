from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.cell_composition import CellCompositionEngine  # noqa: E402
from sec_agent.canonical_runtime.facade import RuntimeFacade  # noqa: E402
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry  # noqa: E402
from sec_agent.canonical_runtime.full_serializer import (  # noqa: E402
    DecisionSurfaceArtifactSerializer,
    DecisionSurfaceBundleAssembler,
    DecisionSurfaceReadbackVerifier,
    DecisionSurfaceSerializationError,
    FullSerializationRequest,
    FullSerializerPolicy,
    FullSerializerScope,
)
from sec_agent.canonical_runtime.legacy_objective_adapter import (  # noqa: E402
    LegacyMigrationPlan,
    LegacySemanticMapping,
    adapt_legacy_objective_semantically,
)
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest  # noqa: E402
from sec_agent.canonical_runtime.pack_registry import (  # noqa: E402
    PlanningPackRegistry,
    PlanningPackRegistryPolicy,
    PlanningPackVersion,
)
from sec_agent.canonical_runtime.pack_selection import PackSelectionEngine, PackSelectionIntent, PackSelectionPolicy  # noqa: E402
from sec_agent.canonical_runtime.planning_service import (  # noqa: E402
    CompilerInputContract,
    CompilerInputValidationPolicy,
    PackSelectionDecision,
)
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore  # noqa: E402
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore  # noqa: E402


AS_OF = datetime(2026, 7, 12, tzinfo=timezone.utc)
CASE_ID = "case-ai-semiconductor"
POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_2_full_serializer_policy_v1_0.json"
VALIDATION_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json"
REGISTRY_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json"
SELECTION_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_4_pack_selection_policy_v1_0.json"
FLAGS_PATH = ROOT / "configs/runtime/point01_feature_flags_v1_0.json"
PLAN_PATH = ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_2_full_serializer_fixture_result_v1_0.json"


def _load_runner(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M2_5 = _load_runner("point01_m2_5_for_m2_2", ROOT / "scripts/engineering/run_point01_m2_5_cell_composition_fixture.py")
M2_6 = _load_runner("point01_m2_6_for_m2_2", ROOT / "scripts/engineering/run_point01_m2_6_evidence_slot_policy_fixture.py")
M2_7 = _load_runner("point01_m2_7_for_m2_2", ROOT / "scripts/engineering/run_point01_m2_7_legacy_semantic_mapping_fixture.py")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy(path: Path, cls):
    raw = json.loads(path.read_text(encoding="utf-8"))
    return cls.model_validate({key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}})


def _pack(pack_id: str, scope_kind: str, *, sector: str | None = None, report_type: str | None = None, case_id: str | None = None) -> PlanningPackVersion:
    payload = {"pack_id": pack_id, "scope_kind": scope_kind, "sector": sector, "report_type": report_type, "case_id": case_id}
    return PlanningPackVersion(
        pack_id=pack_id,
        pack_version=1,
        pack_version_id=f"{pack_id}:v1",
        scope_kind=scope_kind,
        sector=sector,
        report_type=report_type,
        case_id=case_id,
        promotion_status="provisional_case_delta" if scope_kind == "case_delta" else "reviewed_runtime_candidate",
        effective_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
        fresh_until=datetime(2026, 12, 31, tzinfo=timezone.utc),
        source_authority_policy_refs=(f"{scope_kind}_authority_policy",),
        payload_digest=canonical_digest(payload),
        published_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def _context(
    *,
    sector: str = "ai_semis",
    case_id: str = CASE_ID,
) -> tuple[FullSerializationRequest, DecisionSurfaceBundleAssembler, FullSerializerPolicy]:
    queries = {
        "ai_semis": "Semiconductor accelerator initiation",
        "saas": "Subscription software initiation",
        "healthcare": "Clinical therapeutic initiation",
        "banks": "Bank deposit initiation",
    }
    query = queries[sector]
    registry = PlanningPackRegistry(_policy(REGISTRY_POLICY_PATH, PlanningPackRegistryPolicy))
    registry.publish(_pack("universal-core", "universal"))
    registry.publish(_pack(f"sector-{sector}", "sector", sector=sector))
    registry.publish(_pack("report-initiation", "report_type", report_type="initiation"))
    registry.publish(_pack(case_id, "case_delta", case_id=case_id))
    engine = PackSelectionEngine(registry, _policy(SELECTION_POLICY_PATH, PackSelectionPolicy))
    selection = engine.select(
        PackSelectionIntent(
            query=query,
            sector=sector,
            report_type="initiation",
            case_id=case_id,
            as_of=AS_OF,
        )
    )
    assert selection.resolution is not None
    composition = CellCompositionEngine(M2_5._policy()).compose(
        case_id=case_id,
        selected_pack_refs=selection.resolution.universal_pack_refs + selection.resolution.sector_pack_refs,
        archetypes=M2_5.build_archetypes(sector),
    )
    compiler_input = CompilerInputContract(
        tenant_id="tenant-m2-2",
        project_id="project-m2-2",
        case_id=case_id,
        query=query,
        as_of=AS_OF,
        universe=("AAA",),
        language="en",
        compiler_policy_ref="point01-m2-1-compiler-policy-v1",
        pack_selection=PackSelectionDecision(
            universal_pack_refs=selection.resolution.universal_pack_refs,
            sector_pack_refs=selection.resolution.sector_pack_refs,
            report_type_pack_refs=selection.resolution.report_type_pack_refs,
            case_delta_pack_refs=selection.resolution.case_delta_pack_refs,
        ),
        required_cells=tuple(cell.seed for cell in composition.cells),
    )
    evidence_slots = tuple(
        M2_6.SlotCompilationInput(cell_key=cell.cell_key, slot_key=slot_key, slot=slot)
        for cell in composition.cells
        for slot_key, slot in DecisionSurfaceBundleAssembler._slot_bindings(cell)
    )
    evidence_policy = M2_6._compiler().compile(
        sector=sector,
        slots=evidence_slots,
        available_parser_source_policy_refs=("issuer_first",),
    )
    target_cells = tuple(cell.seed for cell in composition.cells)
    legacy_payload = M2_7._legacy_payload(sector)
    legacy_migration: LegacyMigrationPlan = adapt_legacy_objective_semantically(
        legacy_payload,
        target_cells=target_cells,
        mappings=(
            LegacySemanticMapping(
                legacy_required_item_id="legacy_unit_economics",
                action="split",
                target_cell_keys=("core_0", "core_1"),
                information_loss_tags=("legacy_question_split_into_mechanism_cells",),
            ),
            LegacySemanticMapping(
                legacy_required_item_id="legacy_revenue",
                action="merge",
                target_cell_keys=("core_2",),
                information_loss_tags=("legacy_metric_not_direct_cell_equivalence",),
            ),
            LegacySemanticMapping(
                legacy_required_item_id="legacy_cashflow",
                action="merge",
                target_cell_keys=("core_2",),
                information_loss_tags=("legacy_metric_merged_with_financial_quality",),
            ),
            LegacySemanticMapping(
                legacy_required_item_id="legacy_fact_search",
                action="downgrade",
                information_loss_tags=("legacy_fact_search_becomes_bounded_context",),
                downgrade_reason="legacy fact lookup is not an independent material DecisionCell",
            ),
        ),
        policy=M2_7._policy(),
    )
    serializer_policy = _policy(POLICY_PATH, FullSerializerPolicy)
    compiler_policy = _policy(VALIDATION_POLICY_PATH, CompilerInputValidationPolicy)
    scope = FullSerializerScope(
        tenant_id=compiler_input.tenant_id,
        project_id=compiler_input.project_id,
        case_id=case_id,
        actor_snapshot_ref="actor-m2-2",
        permission_snapshot_ref="permission-m2-2",
        policy_config_refs=(compiler_policy.policy_ref, serializer_policy.policy_ref),
        correlation_id=f"correlation-m2-2-{sector}",
        created_at=AS_OF,
        recorded_at=AS_OF,
    )
    request = FullSerializationRequest(
        contract_id=f"contract-m2-2-{case_id}",
        contract_version=1,
        compiler_input=compiler_input,
        pack_selection=selection,
        composition=composition,
        evidence_policy=evidence_policy,
        legacy_migration=legacy_migration,
        scope=scope,
    )
    return request, DecisionSurfaceBundleAssembler(compiler_policy=compiler_policy, serializer_policy=serializer_policy), serializer_policy


def _command(command_type: str, *, payload: dict[str, Any], expected: int = 0, key: str) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-{key}",
        command_type=command_type,
        tenant_id="tenant-m2-2",
        project_id="project-m2-2",
        case_id=CASE_ID,
        actor_snapshot_ref="actor-m2-2",
        permission_snapshot_ref="permission-m2-2",
        policy_config_refs=("point01-m2-2-full-serializer-policy-v1",),
        idempotency_key=key,
        expected_state_version=expected,
        correlation_id="correlation-m2-2",
        requested_at=AS_OF,
        payload=payload,
    )


def _facade(root: Path, *, failing_object_store: bool = False) -> RuntimeFacade:
    class FailingObjectStore:
        def put_json(self, payload: Any, *, namespace: str, artifact_type: str) -> dict[str, Any]:
            raise OSError("fixture_full_serializer_object_store_failure")

        def get_json(self, object_key: str, *, expected_digest: str | None = None) -> Any:
            raise AssertionError("not_called")

    return RuntimeFacade(
        SQLiteCanonicalStore(root / "canonical.sqlite"),
        FailingObjectStore() if failing_object_store else FileCanonicalObjectStore(root / "objects"),
        FeatureFlagRegistry.from_path(FLAGS_PATH),
        mode="shadow",
        grants={"point01.shadow.write"},
    )


def _create_case(facade: RuntimeFacade) -> None:
    facade.create_research_case(
        _command("CREATE_RESEARCH_CASE", payload={"query": "Semiconductor accelerator initiation", "accountable_owner_ref": "lead-m2-2"}, key="case")
    )


def _start_work(facade: RuntimeFacade, suffix: str) -> tuple[str, str]:
    work_unit_id = f"wu-m2-2-{suffix}"
    attempt_id = f"attempt-m2-2-{suffix}"
    facade.create_work_unit(_command("CREATE_WORK_UNIT", payload={"work_unit_id": work_unit_id, "input_version_refs": (f"serializer-input-{suffix}",)}, key=f"wu-{suffix}"))
    facade.start_attempt(_command("START_ATTEMPT", payload={"work_unit_id": work_unit_id, "attempt_id": attempt_id}, key=f"attempt-{suffix}"))
    return work_unit_id, attempt_id


def _error_code(action: Callable[[], Any]) -> str:
    try:
        action()
    except DecisionSurfaceSerializationError as exc:
        return str(exc)
    return "not_rejected"


def build_result(work_root: Path) -> dict[str, Any]:
    request, assembler, serializer_policy = _context()
    assembly_v1 = assembler.assemble(request)
    facade = _facade(work_root)
    _create_case(facade)
    work_unit_1, attempt_1 = _start_work(facade, "v1")
    serializer = DecisionSurfaceArtifactSerializer(serializer_policy)
    committed_v1 = serializer.commit(
        facade,
        _command("COMMIT_DECISION_SURFACE_BUNDLE", payload={"work_unit_id": work_unit_1, "attempt_id": attempt_1}, expected=1, key="commit-v1"),
        assembly_v1,
        artifact_id="artifact-m2-2-v1",
    )
    verifier = DecisionSurfaceReadbackVerifier()
    readback_v1 = verifier.verify(facade, assembly_v1, artifact_version_id=committed_v1.artifact_refs[0])

    assembly_v2 = assembler.assemble(request.model_copy(update={"contract_version": 2}))
    work_unit_2, attempt_2 = _start_work(facade, "v2")
    committed_v2 = serializer.commit(
        facade,
        _command("COMMIT_DECISION_SURFACE_BUNDLE", payload={"work_unit_id": work_unit_2, "attempt_id": attempt_2}, expected=1, key="commit-v2"),
        assembly_v2,
        artifact_id="artifact-m2-2-v2",
    )
    readback_v2 = verifier.verify(facade, assembly_v2, artifact_version_id=committed_v2.artifact_refs[0])
    readback_v1_after_v2 = verifier.verify(facade, assembly_v1, artifact_version_id=committed_v1.artifact_refs[0])

    selection_mismatch = _error_code(
        lambda: assembler.assemble(
            request.model_copy(
                update={
                    "pack_selection": request.pack_selection.model_copy(
                        update={"resolution": request.pack_selection.resolution.model_copy(update={"case_delta_pack_refs": ()})}
                    )
                }
            )
        )
    )
    typed_gap_dropped = _error_code(
        lambda: assembler.assemble(request.model_copy(update={"evidence_policy": request.evidence_policy.model_copy(update={"gaps": ()})}))
    )
    legacy_direct_equivalence = _error_code(
        lambda: assembler.assemble(request.model_copy(update={"legacy_migration": request.legacy_migration.model_copy(update={"one_to_one_equivalence_count": 1})}))
    )

    failing_root = work_root / "failing"
    failing_facade = _facade(failing_root, failing_object_store=True)
    _create_case(failing_facade)
    failing_work_unit, failing_attempt = _start_work(failing_facade, "atomic")
    atomic_failure = "not_rejected"
    try:
        serializer.commit(
            failing_facade,
            _command("COMMIT_DECISION_SURFACE_BUNDLE", payload={"work_unit_id": failing_work_unit, "attempt_id": failing_attempt}, expected=1, key="commit-atomic-failure"),
            assembly_v1,
            artifact_id="artifact-m2-2-failing",
        )
    except OSError as exc:
        atomic_failure = str(exc)
    checks = {
        "full_envelope_preserves_case_delta_and_all_lineage": bool(assembly_v1.envelope.pack_resolution_snapshot.case_delta_pack_refs)
        and assembly_v1.envelope.composition.composition_digest == request.composition.composition_digest
        and assembly_v1.envelope.legacy_migration_plan.legacy_input_digest == request.legacy_migration.legacy_input_digest,
        "atomic_commit_and_readback": readback_v1.status == "pass" and readback_v2.status == "pass",
        "multi_version_snapshot_replay": readback_v1_after_v2.status == "pass" and assembly_v1.contract_version_id.endswith(":v1") and assembly_v2.contract_version_id.endswith(":v2"),
        "selection_mismatch_rejected": selection_mismatch == "pack_resolution_mismatch",
        "typed_gap_drop_rejected": typed_gap_dropped == "typed_gap_lineage_dropped_or_unexpected",
        "legacy_direct_equivalence_rejected": legacy_direct_equivalence == "legacy_direct_equivalence_forbidden",
        "object_store_failure_leaves_no_canonical_artifact": atomic_failure == "fixture_full_serializer_object_store_failure"
        and failing_facade.store.get_latest("canonical_artifact_versions", "artifact-m2-2-failing") is None
        and failing_facade.store.get_latest("canonical_work_units", failing_work_unit)["state"] == "running",
        "model_free": assembly_v1.model_call_count == 0 and assembly_v2.external_call_count == 0,
    }
    return {
        "result_version": "finsight_point01_m2_2_full_serializer_fixture_result_v1_0",
        "scope": "Point01_M2_2_full_serializer_atomic_readback_replay",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "assemblies": {"v1": assembly_v1.model_dump(mode="json"), "v2": assembly_v2.model_dump(mode="json")},
        "readback_reports": {"v1": readback_v1.model_dump(mode="json"), "v2": readback_v2.model_dump(mode="json"), "v1_after_v2": readback_v1_after_v2.model_dump(mode="json")},
        "negative_errors": {"selection_mismatch": selection_mismatch, "typed_gap_dropped": typed_gap_dropped, "legacy_direct_equivalence": legacy_direct_equivalence, "atomic_failure": atomic_failure},
        "authority_boundary": {"legacy_task_run": "authoritative", "canonical_lane": "shadow_only", "model_call_count": 0, "external_call_count": 0, "runtime_cutover": False},
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m2_2_full_serializer_policy_v1_0.json": _sha256(POLICY_PATH),
            "scripts/engineering/run_point01_m2_2_full_serializer_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/full_serializer.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/full_serializer.py"),
            "src/sec_agent/canonical_runtime/facade.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/facade.py"),
            "src/sec_agent/canonical_runtime/planning_service.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/planning_service.py"),
            "src/sec_agent/canonical_runtime/store.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/store.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(PLAN_PATH),
        },
        "boundary": "M2.2 serializes and commits a deterministic shadow artifact only. It does not invoke a model, retrieve evidence, write legacy TaskRun, run full-chain or change planning authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M2.2 full serializer fixture.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-root", type=Path, default=ROOT / ".tmp_point01_m2_2_full_serializer")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    work_root = args.work_root if args.work_root.is_absolute() else ROOT / args.work_root
    result = build_result(work_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "checks": result["checks"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
