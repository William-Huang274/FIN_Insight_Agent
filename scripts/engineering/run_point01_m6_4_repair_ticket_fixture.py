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

from sec_agent.canonical_runtime.repair_ticket import RepairAttemptPlanner, RepairGapRoute, RepairTicketPolicy, RepairTicketRouter


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_4_repair_ticket_policy_v1_0.json"
REVIEW_PATH = ROOT / "configs/engineering_handoff/point01_m6_4_cross_owner_design_review_v1_0.json"
M6_3_RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_3_candidate_bundle_fixture.py"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_4_repair_ticket_fixture_result_v1_0.json"

SPEC = importlib.util.spec_from_file_location("point01_m6_3_fixture_for_m6_4", M6_3_RUNNER_PATH)
assert SPEC and SPEC.loader
M6_3_RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M6_3_RUNNER)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy() -> RepairTicketPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return RepairTicketPolicy(
        policy_ref=raw["policy_ref"],
        max_internal_repair_attempts=raw["max_internal_repair_attempts"],
        gap_routes={key: RepairGapRoute.model_validate(value) for key, value in raw["gap_routes"].items()},
    )


def inputs():
    compiler = M6_3_RUNNER.CandidateBundleCompiler(policy=M6_3_RUNNER.policy())
    request, plan = M6_3_RUNNER.issuer_request_and_plan()
    internal_bundle = compiler.compile(request=request, plan=plan, snapshot=M6_3_RUNNER.CandidateMetadataSnapshot.create(snapshot_id="empty-repair-fixture", candidates=())).bundle
    external_bundle = internal_bundle.model_copy(update={"typed_gap_codes": ("external_source_unavailable",), "bundle_digest": "external-bundle-digest", "bundle_id": "external-bundle"})
    registry, planner_policy = M6_3_RUNNER.M6_2_RUNNER.registry_and_policy()
    commercial_request = M6_3_RUNNER.M6_2_RUNNER._request(sector="commercial", evidence_role="commercial_tracker_metric", source_policy_ref="commercial_gap", acceptance_role="primary_or_bounded_context", forbidden_substitutions=("public_proxy_as_exact",), metric_scope=())
    commercial_plan = M6_3_RUNNER.BoundedToolPlanner(registry=registry, policy=planner_policy).plan(request=commercial_request, permissions=M6_3_RUNNER.M6_2_RUNNER.permissions(registry)).plan
    commercial_bundle = compiler.compile(request=commercial_request, plan=commercial_plan, snapshot=M6_3_RUNNER.CandidateMetadataSnapshot.create(snapshot_id="commercial-repair-empty", candidates=())).bundle
    return request, internal_bundle, external_bundle, commercial_request, commercial_bundle


def build_result() -> dict[str, Any]:
    router = RepairTicketRouter(policy=policy())
    attempts = RepairAttemptPlanner()
    request, internal_bundle, external_bundle, commercial_request, commercial_bundle = inputs()
    internal = router.route(request=request, bundle=internal_bundle)
    planned = attempts.plan_not_executed(ticket=internal.ticket, attempt_no=1, route_id=internal.ticket.permitted_route_scope[0])
    internal_replay = router.route(request=request, bundle=internal_bundle)
    external = router.route(request=request, bundle=external_bundle)
    commercial = router.route(request=commercial_request, bundle=commercial_bundle)
    checks = {
        "internal_gap_bound_to_origin_and_official_first_routes": internal.ticket.classification == "internal_metadata_gap" and internal.ticket.permitted_route_scope == request.preferred_routes + request.fallback_routes and internal.ticket.attempt_budget == 1,
        "planned_attempt_is_not_executed": planned.attempt.attempt_state == "planned_not_executed" and planned.attempt.outcome == "not_executed" and planned.attempt.next_owner == "M6_2_tool_registry_planner",
        "replay_digest_match": internal.ticket.repair_ticket_digest == internal_replay.ticket.repair_ticket_digest,
        "external_source_is_terminal_stop": external.ticket.classification == "external_source_exhausted" and external.ticket.terminal and external.ticket.attempt_budget == 0,
        "commercial_gap_is_terminal_stop": commercial.ticket.classification == "commercial_license_required" and commercial.ticket.terminal and commercial.ticket.permitted_route_scope == (),
        "execution_free": internal.external_call_count == planned.external_call_count == 0 and internal.tool_invocation_count == planned.tool_invocation_count == 0 and internal.store_write_count == planned.store_write_count == 0,
    }
    return {
        "result_version": "finsight_point01_m6_4_repair_ticket_fixture_result_v1_0", "generated_at": datetime.now(timezone.utc).isoformat(), "scope": "Point01_M6_4_deterministic_repair_ticket_attempt_contract", "status": "pass" if all(checks.values()) else "fail_closed", "checks": checks,
        "tickets": {"internal": internal.ticket.model_dump(mode="json"), "external": external.ticket.model_dump(mode="json"), "commercial": commercial.ticket.model_dump(mode="json")}, "planned_attempt": planned.attempt.model_dump(mode="json"),
        "authority_boundary": {"repair_ticket_persistence": "not_admitted", "repair_attempt_execution": False, "sourcehunter_network_provider_tool": False, "tool_selection_plan_write": "M6_2_owner_only", "evidence_promotion": "M6_6_not_implemented", "model_call_count": 0, "external_call_count": 0, "tool_invocation_count": 0, "store_write_count": 0, "writer_full_chain": "not_admitted"},
        "fixed_input_sha256": {"configs/engineering_handoff/point01_m6_4_repair_ticket_policy_v1_0.json": _sha256(POLICY_PATH), "configs/engineering_handoff/point01_m6_4_cross_owner_design_review_v1_0.json": _sha256(REVIEW_PATH), "scripts/engineering/run_point01_m6_4_repair_ticket_fixture.py": _sha256(Path(__file__).resolve()), "src/sec_agent/canonical_runtime/repair_ticket.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/repair_ticket.py"), "src/sec_agent/canonical_runtime/candidate_bundle.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/candidate_bundle.py"), "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")},
        "boundary": "M6.4 only creates deterministic RepairTicket and planned_not_executed RepairAttempt contracts from typed CandidateBundle gaps. It does not invoke SourceHunter, a tool/provider/network, M5 admission/budget, parser/numeric/promotion, persistence, Writer/full-chain, Case mutation or legacy authority change."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M6.4 deterministic repair-ticket fixture.")
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
