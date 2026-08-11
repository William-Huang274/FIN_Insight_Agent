"""Create or reopen an isolated synthetic M4 store and emit a read-only pilot preflight.

This runner is deliberately not a cutover command.  It creates only a synthetic,
non-production Case when absent, then records its immutable planning bindings,
backup snapshot hash and zero-consumer boundary.  It never requests, executes or
rolls back a planning authority change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_point01_m4_cutover_fixtures import _bundle, _command
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import ShadowComparisonRecord
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.planning_cutover import CutoverScope, LaneEligibilityPolicy, PlanningLaneCutoverService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


DEFAULT_WORK_ROOT = ROOT / "data/staging/point01_m4_synthetic_pilot_v2"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m4_synthetic_pilot_preflight_result_v1_0.json"
SCOPE = CutoverScope(
    tenant_id="tenant-point01-synthetic-pilot",
    project_id="project-point01-synthetic-pilot",
    case_id="case-point01-synthetic-pilot",
    lane_id="planning",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_or_open(work_root: Path) -> tuple[SQLiteCanonicalStore, PlanningLaneCutoverService]:
    work_root.mkdir(parents=True, exist_ok=True)
    store = SQLiteCanonicalStore(work_root / "canonical.sqlite")
    service = _service_for(store)
    if store.get_latest("canonical_research_cases", SCOPE.case_id):
        return store, service
    flags = FeatureFlagRegistry.from_path(ROOT / "configs/runtime/point01_feature_flags_v1_0.json")
    facade = RuntimeFacade(store, FileCanonicalObjectStore(work_root / "objects"), flags, mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(
        _command(
            "CREATE_RESEARCH_CASE",
            {
                "query": "Synthetic M4 pilot: assess durable demand quality.",
                "universe": ["SYNTHETIC"],
                "accountable_owner_ref": "synthetic-pilot-owner",
                "legacy_task_id": "synthetic-legacy-task",
                "legacy_run_id": "synthetic-legacy-run",
            },
        ).model_copy(
            update={
                "tenant_id": SCOPE.tenant_id,
                "project_id": SCOPE.project_id,
                "case_id": SCOPE.case_id,
                "actor_snapshot_ref": "synthetic-pilot-actor",
                "permission_snapshot_ref": "synthetic-pilot-permission",
                "correlation_id": "synthetic-pilot-correlation",
            }
        )
    )
    command_scope = {
        "tenant_id": SCOPE.tenant_id,
        "project_id": SCOPE.project_id,
        "case_id": SCOPE.case_id,
        "actor_snapshot_ref": "synthetic-pilot-actor",
        "permission_snapshot_ref": "synthetic-pilot-permission",
        "correlation_id": "synthetic-pilot-correlation",
    }
    facade.create_work_unit(
        _command("CREATE_WORK_UNIT", {"work_unit_id": "wu-synthetic-pilot", "input_version_refs": ["summary-synthetic-pilot-v1"]}).model_copy(update=command_scope)
    )
    facade.start_attempt(
        _command("START_ATTEMPT", {"work_unit_id": "wu-synthetic-pilot", "attempt_id": "attempt-synthetic-pilot"}).model_copy(update=command_scope)
    )
    bundle = _bundle()
    for row in (bundle["contract"], *bundle["cells"], *bundle["slots"]):
        row.update(
            {
                "tenant_id": SCOPE.tenant_id,
                "project_id": SCOPE.project_id,
                "case_id": SCOPE.case_id,
                "actor_snapshot_ref": "synthetic-pilot-actor",
                "permission_snapshot_ref": "synthetic-pilot-permission",
                "correlation_id": "synthetic-pilot-correlation",
            }
        )
    bundle["contract"].update({"contract_id": "contract-synthetic-pilot", "contract_version_id": "contract-synthetic-pilot:v1", "required_cell_ids": ["cell-synthetic-pilot"]})
    bundle["cells"][0].update({"contract_version_id": "contract-synthetic-pilot:v1", "cell_id": "cell-synthetic-pilot", "cell_version_id": "cell-synthetic-pilot:v1"})
    bundle["slots"][0].update({"cell_version_id": "cell-synthetic-pilot:v1", "evidence_slot_id": "slot-synthetic-pilot", "slot_version_id": "slot-synthetic-pilot:v1"})
    facade.commit_decision_surface_bundle(
        _command(
            "COMMIT_DECISION_SURFACE_BUNDLE",
            {"work_unit_id": "wu-synthetic-pilot", "attempt_id": "attempt-synthetic-pilot", "artifact_id": "artifact-synthetic-pilot", "bundle": bundle},
            expected=1,
        ).model_copy(update=command_scope)
    )
    now = datetime.now(timezone.utc)
    comparison = ShadowComparisonRecord(
        tenant_id=SCOPE.tenant_id,
        project_id=SCOPE.project_id,
        case_id=SCOPE.case_id,
        created_at=now,
        recorded_at=now,
        actor_snapshot_ref="synthetic-pilot-comparison",
        permission_snapshot_ref="synthetic-pilot-permission",
        correlation_id="synthetic-pilot-comparison",
        current_status="shadow_compared",
        comparison_id="comparison-synthetic-pilot",
        comparison_version=1,
        legacy_plan_ref="synthetic-legacy-task",
        canonical_contract_version_id="contract-synthetic-pilot:v1",
        rubric_version="m3-fixture-v1",
        summary_metrics={"semantic_coverage": 1.0},
        details_artifact_ref="artifact-synthetic-pilot:v1",
    )
    with store.transaction() as tx:
        tx.insert("canonical_shadow_comparisons", comparison.comparison_id, comparison.comparison_version, comparison.model_dump(mode="json"))
    return store, service


def _service_for(store: SQLiteCanonicalStore) -> PlanningLaneCutoverService:
    flags = FeatureFlagRegistry.from_path(ROOT / "configs/runtime/point01_feature_flags_v1_0.json")
    return PlanningLaneCutoverService(
        store,
        flags,
        LaneEligibilityPolicy(policy_ref="point01_m4_case_scoped_cutover_policy_v1_0"),
        grants={"point01.cutover.execute"},
    )


def _backup_snapshot(store: SQLiteCanonicalStore, work_root: Path) -> Path:
    destination = work_root / "backups" / "preflight_snapshot.sqlite"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(store.db_path) as source, sqlite3.connect(destination) as backup:
        source.backup(backup)
    return destination


def _restore_snapshot(snapshot: Path, work_root: Path) -> SQLiteCanonicalStore:
    """Restore the snapshot to a distinct database path and reopen it for audit."""
    destination = work_root / "restores" / "preflight_restored.sqlite"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(snapshot) as source, sqlite3.connect(destination) as restored:
        source.backup(restored)
    return SQLiteCanonicalStore(destination)


def build_result(work_root: Path) -> dict[str, Any]:
    store, service = _build_or_open(work_root)
    snapshot = _backup_snapshot(store, work_root)
    preflight = service.read_only_preflight(SCOPE, downstream_consumer_ids=())
    source_recovery = store.recovery_check()
    restored_store = _restore_snapshot(snapshot, work_root)
    restored_preflight = _service_for(restored_store).read_only_preflight(SCOPE, downstream_consumer_ids=())
    restored_recovery = restored_store.recovery_check()
    exact_bindings = {
        "contract_version_id": preflight.contract_version_id,
        "contract_digest": preflight.contract_digest,
        "artifact_version_id": preflight.artifact_version_id,
        "artifact_digest": preflight.artifact_digest,
        "comparison_id": preflight.comparison_id,
        "comparison_digest": preflight.comparison_digest,
    }
    restored_bindings = {
        "contract_version_id": restored_preflight.contract_version_id,
        "contract_digest": restored_preflight.contract_digest,
        "artifact_version_id": restored_preflight.artifact_version_id,
        "artifact_digest": restored_preflight.artifact_digest,
        "comparison_id": restored_preflight.comparison_id,
        "comparison_digest": restored_preflight.comparison_digest,
    }
    source_fingerprint = store.content_fingerprint()
    restored_fingerprint = restored_store.content_fingerprint()
    restore_passed = bool(
        source_recovery["status"] == "pass"
        and restored_recovery["status"] == "pass"
        and preflight.authority == restored_preflight.authority == "legacy"
        and exact_bindings == restored_bindings
        and source_fingerprint == restored_fingerprint
    )
    return {
        "result_version": "finsight_point01_m4_synthetic_pilot_preflight_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if restore_passed else "fail_closed",
        "pilot_kind": "isolated_nonproduction_synthetic_persistent_case",
        "scope": preflight.scope.model_dump(mode="json"),
        "store_identity": preflight.store_identity,
        "exact_bindings": exact_bindings,
        "backup_snapshot_sha256": _sha256(snapshot),
        "source_store_integrity_check": source_recovery,
        "backup_restore_drill": {
            "status": "pass" if restore_passed else "fail_closed",
            "source_store_identity": preflight.store_identity,
            "restored_store_identity": restored_preflight.store_identity,
            "source_authority": preflight.authority,
            "restored_authority": restored_preflight.authority,
            "source_exact_bindings": exact_bindings,
            "restored_exact_bindings": restored_bindings,
            "exact_bindings_match": exact_bindings == restored_bindings,
            "source_content_fingerprint": source_fingerprint,
            "restored_content_fingerprint": restored_fingerprint,
            "content_fingerprint_match": source_fingerprint == restored_fingerprint,
            "restored_store_integrity_check": restored_recovery,
        },
        "rollback_window": "not_opened_read_only_preflight_only",
        "kill_switch_state": "off",
        "downstream_consumer_ids": [],
        "downstream_consumer_count": 0,
        "authority_before_after": {"before": preflight.authority, "after": preflight.authority},
        "mutation_performed": False,
        "forbidden_actions": ["request_cutover", "execute_cutover", "rollback_cutover", "evidence_runtime", "writer_runtime", "provider_execution", "full_chain"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an isolated synthetic M4 store and run read-only preflight.")
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    work_root = args.work_root if args.work_root.is_absolute() else ROOT / args.work_root
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result(work_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "mutation_performed": result["mutation_performed"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
