from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.repair_ticket import RepairAttemptPlanner, RepairTicketError, RepairTicketRouter


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_4_repair_ticket_fixture.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_4_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_internal_ticket_is_replayable_and_attempt_is_planned_only() -> None:
    request, internal_bundle, *_ = RUNNER.inputs()
    router = RepairTicketRouter(policy=RUNNER.policy())
    first = router.route(request=request, bundle=internal_bundle)
    second = router.route(request=request, bundle=internal_bundle)
    attempt = RepairAttemptPlanner().plan_not_executed(ticket=first.ticket, attempt_no=1, route_id=first.ticket.permitted_route_scope[0])
    assert first.ticket.repair_ticket_digest == second.ticket.repair_ticket_digest
    assert first.ticket.permitted_route_scope == request.preferred_routes + request.fallback_routes
    assert attempt.attempt.outcome == "not_executed"
    assert first.external_call_count == attempt.external_call_count == 0


def test_terminal_and_budget_or_route_bypasses_fail_closed() -> None:
    request, internal_bundle, external_bundle, commercial_request, commercial_bundle = RUNNER.inputs()
    router = RepairTicketRouter(policy=RUNNER.policy())
    planner = RepairAttemptPlanner()
    internal = router.route(request=request, bundle=internal_bundle).ticket
    external = router.route(request=request, bundle=external_bundle).ticket
    commercial = router.route(request=commercial_request, bundle=commercial_bundle).ticket
    assert external.terminal and commercial.terminal
    with pytest.raises(RepairTicketError, match="terminal_repair_ticket_cannot_create_attempt"):
        planner.plan_not_executed(ticket=external, attempt_no=1, route_id="issuer_disclosure_metadata_route")
    with pytest.raises(RepairTicketError, match="repair_attempt_budget_exhausted"):
        planner.plan_not_executed(ticket=internal, attempt_no=2, route_id=internal.permitted_route_scope[0])
    with pytest.raises(RepairTicketError, match="repair_attempt_route_not_permitted"):
        planner.plan_not_executed(ticket=internal, attempt_no=1, route_id="free-search")
    with pytest.raises(RepairTicketError, match="candidate_bundle_request_lineage_mismatch"):
        router.route(request=request, bundle=internal_bundle.model_copy(update={"request_digest": "wrong"}))


def test_review_is_user_scoped_and_does_not_claim_independent_human_signoff() -> None:
    review = json.loads((ROOT / "configs/engineering_handoff/point01_m6_4_cross_owner_design_review_v1_0.json").read_text(encoding="utf-8"))
    assert review["status"] == "user_confirmed_structured_cross_owner_review_accepted_for_m6_4"
    assert review["independent_human_or_multi_person_signoff"] is False
    assert review["user_confirmation"]["decision"] == "approve_m6_4_deterministic_repair_ticket_attempt_contract_only"


def test_m6_4_fixture_runner_is_execution_free(tmp_path: Path) -> None:
    output = tmp_path / "m6_4_fixture.json"
    completed = subprocess.run([sys.executable, str(RUNNER_PATH), "--output", str(output)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["external_source_is_terminal_stop"] is True
    assert result["checks"]["commercial_gap_is_terminal_stop"] is True
    assert result["authority_boundary"]["sourcehunter_network_provider_tool"] is False
