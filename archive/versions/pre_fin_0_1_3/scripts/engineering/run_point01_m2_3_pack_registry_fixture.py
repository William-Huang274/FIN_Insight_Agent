from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.pack_registry import (  # noqa: E402
    PackResolutionRequest,
    PlanningPackRegistry,
    PlanningPackRegistryError,
    PlanningPackRegistryPolicy,
    PlanningPackVersion,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_3_pack_registry_fixture_result_v1_0.json"
AS_OF = datetime(2026, 7, 12, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy() -> PlanningPackRegistryPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return PlanningPackRegistryPolicy.model_validate(
        {key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}}
    )


def _pack(
    pack_id: str,
    version: int,
    scope_kind: str,
    *,
    sector: str | None = None,
    report_type: str | None = None,
    case_id: str | None = None,
    supersedes: str | None = None,
    fresh_until: datetime | None = None,
    promotion_status: str = "reviewed_runtime_candidate",
) -> PlanningPackVersion:
    payload = {
        "pack_id": pack_id,
        "version": version,
        "scope_kind": scope_kind,
        "sector": sector,
        "report_type": report_type,
        "case_id": case_id,
    }
    return PlanningPackVersion(
        pack_id=pack_id,
        pack_version=version,
        pack_version_id=f"{pack_id}:v{version}",
        scope_kind=scope_kind,
        sector=sector,
        report_type=report_type,
        case_id=case_id,
        promotion_status=promotion_status,
        effective_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
        fresh_until=fresh_until or datetime(2026, 12, 31, tzinfo=timezone.utc),
        source_authority_policy_refs=(f"{scope_kind}_authority_policy",),
        payload_digest=canonical_digest(payload),
        published_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        supersedes_pack_version_id=supersedes,
    )


def build_result() -> dict[str, Any]:
    registry = PlanningPackRegistry(_policy())
    registry.publish(_pack("universal-core", 1, "universal"))
    for sector in ("ai_semis", "saas", "healthcare", "banks"):
        registry.publish(_pack(f"sector-{sector}", 1, "sector", sector=sector))
    registry.publish(_pack("report-initiation", 1, "report_type", report_type="initiation"))
    registry.publish(_pack("case-ai-semiconductor", 1, "case_delta", case_id="case-ai-semiconductor", promotion_status="provisional_case_delta"))

    sector_resolutions = {
        sector: registry.resolve(
            PackResolutionRequest(
                as_of=AS_OF,
                sector=sector,
                report_type="initiation",
                require_sector_pack=True,
                require_report_type_pack=True,
            )
        )
        for sector in ("ai_semis", "saas", "healthcare", "banks")
    }
    case_resolution = registry.resolve(
        PackResolutionRequest(
            as_of=AS_OF,
            sector="ai_semis",
            report_type="initiation",
            case_id="case-ai-semiconductor",
            require_sector_pack=True,
            require_report_type_pack=True,
            require_case_delta_pack=True,
        )
    )

    registry.publish(_pack("sector-ai_semis", 2, "sector", sector="ai_semis", supersedes="sector-ai_semis:v1"))
    superseded_exact_rejected = False
    try:
        registry.read_exact("sector-ai_semis:v1", as_of=AS_OF)
    except PlanningPackRegistryError as exc:
        superseded_exact_rejected = str(exc) == "superseded_pack_version"
    current_ai = registry.resolve(
        PackResolutionRequest(as_of=AS_OF, sector="ai_semis", require_sector_pack=True)
    )

    registry.publish(
        _pack(
            "sector-stale",
            1,
            "sector",
            sector="stale_fixture",
            fresh_until=datetime(2026, 7, 2, tzinfo=timezone.utc),
        )
    )
    stale_exact_rejected = False
    try:
        registry.read_exact("sector-stale:v1", as_of=AS_OF)
    except PlanningPackRegistryError as exc:
        stale_exact_rejected = str(exc) == "pack_not_fresh:stale"
    document_only_rejected = False
    try:
        registry.publish(_pack("document-only", 1, "universal", promotion_status="document_only"))
    except PlanningPackRegistryError as exc:
        document_only_rejected = str(exc) == "pack_promotion_status_not_allowed"

    snapshot = registry.snapshot()
    replay = PlanningPackRegistry.from_snapshot(snapshot)
    checks = {
        "four_sector_coverage": set(sector_resolutions) == {"ai_semis", "saas", "healthcare", "banks"},
        "all_sector_resolutions_have_universal_sector_report": all(
            resolution.universal_pack_refs and resolution.sector_pack_refs and resolution.report_type_pack_refs
            for resolution in sector_resolutions.values()
        ),
        "case_delta_resolution": bool(case_resolution.case_delta_pack_refs),
        "superseded_exact_rejected": superseded_exact_rejected,
        "current_ai_uses_v2": current_ai.sector_pack_refs == ("sector-ai_semis:v2",),
        "stale_exact_rejected": stale_exact_rejected,
        "document_only_rejected": document_only_rejected,
        "snapshot_replay_deterministic": replay.snapshot() == snapshot,
    }
    return {
        "result_version": "finsight_point01_m2_3_pack_registry_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M2_3_pack_registry_resolution_lifecycle",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "sector_resolutions": {sector: resolution.model_dump(mode="json") for sector, resolution in sector_resolutions.items()},
        "case_resolution": case_resolution.model_dump(mode="json"),
        "lifecycle_event_count": len(registry.lifecycle_events),
        "authority_boundary": {
            "legacy_task_run": "authoritative",
            "canonical_lane": "shadow_only",
            "model_call_count": 0,
            "external_call_count": 0,
        },
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json": _sha256(POLICY_PATH),
            "scripts/engineering/run_point01_m2_3_pack_registry_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/pack_registry.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/pack_registry.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
        },
        "boundary": "This fixture exercises an in-memory shadow planning registry and deterministic snapshot replay only. It does not write a production registry, legacy TaskRun, evidence runtime, model or cutover path.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M2.3 pack-registry fixture.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "checks": result["checks"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
