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

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.canonical_runtime.pack_registry import (  # noqa: E402
    PlanningPackRegistry,
    PlanningPackRegistryPolicy,
    PlanningPackVersion,
)
from sec_agent.canonical_runtime.pack_selection import (  # noqa: E402
    PackSelectionEngine,
    PackSelectionIntent,
    PackSelectionPolicy,
)


REGISTRY_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json"
SELECTION_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_4_pack_selection_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_4_pack_selection_fixture_result_v1_0.json"
AS_OF = datetime(2026, 7, 12, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _registry_policy() -> PlanningPackRegistryPolicy:
    raw = json.loads(REGISTRY_POLICY_PATH.read_text(encoding="utf-8"))
    return PlanningPackRegistryPolicy.model_validate(
        {key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}}
    )


def _selection_policy() -> PackSelectionPolicy:
    raw = json.loads(SELECTION_POLICY_PATH.read_text(encoding="utf-8"))
    return PackSelectionPolicy.model_validate(
        {key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}}
    )


def _pack(pack_id: str, version: int, scope_kind: str, *, sector: str | None = None, report_type: str | None = None) -> PlanningPackVersion:
    payload = {"pack_id": pack_id, "version": version, "scope_kind": scope_kind, "sector": sector, "report_type": report_type}
    return PlanningPackVersion(
        pack_id=pack_id,
        pack_version=version,
        pack_version_id=f"{pack_id}:v{version}",
        scope_kind=scope_kind,
        sector=sector,
        report_type=report_type,
        promotion_status="reviewed_runtime_candidate",
        effective_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
        fresh_until=datetime(2026, 12, 31, tzinfo=timezone.utc),
        source_authority_policy_refs=(f"{scope_kind}_authority_policy",),
        payload_digest=canonical_digest(payload),
        published_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def _engine() -> PackSelectionEngine:
    registry = PlanningPackRegistry(_registry_policy())
    registry.publish(_pack("universal-core", 1, "universal"))
    for sector in ("ai_semis", "saas", "healthcare", "banks"):
        registry.publish(_pack(f"sector-{sector}", 1, "sector", sector=sector))
    for report_type in ("initiation", "event_update", "valuation_price_in"):
        registry.publish(_pack(f"report-{report_type}", 1, "report_type", report_type=report_type))
    return PackSelectionEngine(registry, _selection_policy())


def build_result() -> dict[str, Any]:
    engine = _engine()
    sector_queries = {
        "ai_semis": "Semiconductor accelerator",
        "saas": "Subscription software",
        "healthcare": "Clinical therapeutic",
        "banks": "Bank deposit",
    }
    report_suffixes = {
        "initiation": "initiation",
        "event_update": "earnings update",
        "valuation_price_in": "valuation price-in",
    }
    decisions = {}
    for sector, base_query in sector_queries.items():
        for report_type, suffix in report_suffixes.items():
            intent = PackSelectionIntent(query=f"{base_query} {suffix}", sector=sector, report_type=report_type, as_of=AS_OF)
            decisions[f"{sector}:{report_type}"] = engine.select(intent)
    conflict = engine.select(PackSelectionIntent(query="bank software initiation", sector="saas", report_type="initiation", as_of=AS_OF))
    rejected = engine.select(PackSelectionIntent(query="unclassified initiation", report_type="initiation", as_of=AS_OF))
    checks = {
        "multi_sector_report_type_grid": len(decisions) == 12 and all(decision.status == "selected" for decision in decisions.values()),
        "selection_reasons_present": all(decision.reasons and decision.resolution for decision in decisions.values()),
        "conflict_recorded": conflict.status == "conflict" and bool(conflict.conflicts),
        "rejection_recorded": rejected.status == "rejected" and bool(rejected.rejections),
        "model_free": all(decision.model_call_count == 0 for decision in decisions.values()) and conflict.model_call_count == 0,
    }
    return {
        "result_version": "finsight_point01_m2_4_pack_selection_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M2_4_pack_selection_engine",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "decisions": {key: value.model_dump(mode="json") for key, value in decisions.items()},
        "conflict": conflict.model_dump(mode="json"),
        "rejection": rejected.model_dump(mode="json"),
        "authority_boundary": {"legacy_task_run": "authoritative", "canonical_lane": "shadow_only", "model_call_count": 0, "external_call_count": 0},
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json": _sha256(REGISTRY_POLICY_PATH),
            "configs/engineering_handoff/point01_m2_4_pack_selection_policy_v1_0.json": _sha256(SELECTION_POLICY_PATH),
            "scripts/engineering/run_point01_m2_4_pack_selection_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/pack_registry.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/pack_registry.py"),
            "src/sec_agent/canonical_runtime/pack_selection.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/pack_selection.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
        },
        "boundary": "This fixture selects versioned shadow packs with reasons/rejections/conflicts only. It does not compile cells, call a model, retrieve evidence, write legacy state or change authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M2.4 pack-selection fixture.")
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
