from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.evidence_request import EvidenceRequestCompiler
from sec_agent.canonical_runtime.tool_planner import BoundedToolPlanner, PlannerPermissionContext, PlannerPolicy, ToolRegistryEntry, ToolRegistrySnapshot


REGISTRY_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_tool_registry_policy_v1_0.json"
REVIEW_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_cross_owner_design_review_v1_0.json"
M6_1_RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_1_evidence_request_fixture.py"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_2_tool_planner_fixture_result_v1_0.json"

SPEC = importlib.util.spec_from_file_location("point01_m6_1_fixture_for_m6_2", M6_1_RUNNER_PATH)
assert SPEC and SPEC.loader
M6_1_RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M6_1_RUNNER)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registry_and_policy() -> tuple[ToolRegistrySnapshot, PlannerPolicy]:
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entries = tuple(ToolRegistryEntry.model_validate(item) for item in raw["tools"])
    snapshot = ToolRegistrySnapshot.create(
        registry_id=raw["registry_id"],
        registry_version=int(raw["registry_snapshot_version"]),
        entries=entries,
    )
    return snapshot, PlannerPolicy.model_validate(raw["planner_policy"])


def permissions(snapshot: ToolRegistrySnapshot, *, allowed_tool_ids: tuple[str, ...] | None = None) -> PlannerPermissionContext:
    return PlannerPermissionContext(
        permission_snapshot_ref="permission-m6-2-fixture",
        allowed_tool_ids=allowed_tool_ids if allowed_tool_ids is not None else tuple(entry.tool_id for entry in snapshot.entries),
        required_permission_scope="runtime_read_only",
    )


def _request(
    *,
    sector: str,
    evidence_role: str = "issuer_metric",
    source_policy_ref: str = "issuer_first",
    acceptance_role: str = "primary",
    forbidden_substitutions: tuple[str, ...] = ("relationship_graph_only",),
    metric_scope: tuple[str, ...] = ("revenue_growth",),
):
    contract, cell, slot = M6_1_RUNNER.planning_models(
        sector=sector,
        evidence_role=evidence_role,
        source_policy_ref=source_policy_ref,
        acceptance_role=acceptance_role,
        forbidden_substitutions=forbidden_substitutions,
        metric_scope=metric_scope,
    )
    return EvidenceRequestCompiler(M6_1_RUNNER._policy()).compile(contract=contract, cell=cell, slot=slot).request


def build_result() -> dict[str, Any]:
    snapshot, policy = registry_and_policy()
    planner = BoundedToolPlanner(registry=snapshot, policy=policy)
    allowed = permissions(snapshot)
    issuer_request = _request(sector="ai_semis")
    issuer = planner.plan(request=issuer_request, permissions=allowed)
    issuer_replay = planner.plan(request=issuer_request, permissions=allowed)
    relationship_request = _request(
        sector="relationship",
        evidence_role="relationship_signal",
        source_policy_ref="relationship_graph_only",
        acceptance_role="bounded_context_only",
        forbidden_substitutions=("issuer_metric_substitute",),
        metric_scope=(),
    )
    relationship = planner.plan(request=relationship_request, permissions=allowed)
    commercial_request = _request(
        sector="commercial",
        evidence_role="commercial_tracker_metric",
        source_policy_ref="commercial_gap",
        acceptance_role="primary_or_bounded_context",
        forbidden_substitutions=("public_proxy_as_exact",),
        metric_scope=(),
    )
    commercial = planner.plan(request=commercial_request, permissions=allowed)
    permission_denied = planner.plan(request=issuer_request, permissions=permissions(snapshot, allowed_tool_ids=()))

    checks = {
        "issuer_primary_and_bounded_fallback": [step.selected_tool_id for step in issuer.plan.steps] == ["issuer_disclosure_metadata_tool", "official_company_commentary_metadata_tool"],
        "issuer_authority_before_cost": issuer.plan.steps[0].selection_rationale.startswith("authority_rank=5;cost_rank=2"),
        "replay_digest_match": issuer.plan.plan_digest == issuer_replay.plan.plan_digest,
        "relationship_context_route": [step.selected_tool_id for step in relationship.plan.steps] == ["relationship_graph_metadata_tool"],
        "commercial_gap_stops": commercial.plan.status == "stopped" and commercial.plan.stop_reason == "commercial_gap_stop_rule",
        "permission_stop": permission_denied.plan.status == "stopped" and permission_denied.plan.stop_reason == "permission_scope_stop_rule",
        "fallback_and_budget_bounded": len(issuer.plan.steps) <= 1 + policy.max_fallback_depth and issuer.plan.planned_tool_call_count <= issuer_request.budget.tool_call_limit,
        "no_execution": all(step.invocation_status == "not_executed" for step in issuer.plan.steps) and issuer.tool_invocation_count == 0 and issuer.external_call_count == 0 and issuer.store_write_count == 0,
    }
    return {
        "result_version": "finsight_point01_m6_2_tool_planner_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M6_2_deterministic_tool_registry_and_nonexecuting_planner",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "registry": {"snapshot_id": snapshot.snapshot_id, "snapshot_digest": snapshot.snapshot_digest, "tool_count": len(snapshot.entries)},
        "plans": {
            "issuer": issuer.plan.model_dump(mode="json"),
            "relationship": relationship.plan.model_dump(mode="json"),
            "commercial": commercial.plan.model_dump(mode="json"),
            "permission_denied": permission_denied.plan.model_dump(mode="json"),
        },
        "authority_boundary": {
            "tool_registry_persistence": "not_admitted",
            "tool_selection_persistence": "not_admitted",
            "tool_invocation_count": 0,
            "provider_execution": False,
            "external_tool_execution": False,
            "model_call_count": 0,
            "external_call_count": 0,
            "store_write_count": 0,
            "candidate_retrieval": "M6_3_not_implemented",
            "evidence_promotion": "M6_6_not_implemented",
            "writer_full_chain": "not_admitted"
        },
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m6_2_tool_registry_policy_v1_0.json": _sha256(REGISTRY_PATH),
            "configs/engineering_handoff/point01_m6_2_cross_owner_design_review_v1_0.json": _sha256(REVIEW_PATH),
            "scripts/engineering/run_point01_m6_2_tool_planner_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/tool_planner.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/tool_planner.py"),
            "src/sec_agent/canonical_runtime/evidence_request.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/evidence_request.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")
        },
        "boundary": "M6.2 creates only a deterministic ToolRegistrySnapshot and nonexecuting ToolSelectionPlan. It does not persist registry/plans, perform M5.4 admission, reserve/consume budget, invoke a tool/provider/network, retrieve candidates, promote evidence, write a report, mutate a business Case or change legacy authority."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M6.2 deterministic Tool Registry/planner fixture.")
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
