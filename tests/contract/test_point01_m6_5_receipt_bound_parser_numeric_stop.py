from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.receipt_bound_parser_numeric_stop import (
    ReceiptBoundParserNumericStopError,
    ReceiptBoundParserNumericStopPolicy,
    ReceiptBoundParserNumericStopService,
)
from sec_agent.canonical_runtime.receipt_bound_repair_ticket import ReceiptBoundRepairTicketService


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_5_receipt_bound_parser_numeric_stop_policy_v1_0.json"
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_5_receipt_bound_parser_numeric_stop.py"
M6_4_TEST_PATH = ROOT / "tests/contract/test_point01_m6_4_receipt_bound_terminal_repair.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_4_terminal_repair_helpers_for_m6_5", M6_4_TEST_PATH)
assert SPEC and SPEC.loader
M6_4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M6_4)
RUNNER_SPEC = importlib.util.spec_from_file_location("point01_m6_5_parser_stop_runner_helpers", RUNNER_PATH)
assert RUNNER_SPEC and RUNNER_SPEC.loader
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)


def _policy() -> ReceiptBoundParserNumericStopPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return ReceiptBoundParserNumericStopPolicy.model_validate(
        {field: raw[field] for field in ReceiptBoundParserNumericStopPolicy.model_fields}
    )


def _terminal_chain(tmp_path: Path, *, runner_compatible: bool = False):
    factory = M6_4._runner_compatible_typed_exhaustion if runner_compatible else M6_4._typed_exhaustion
    facade, command, request, bundle, session = factory(tmp_path)
    ticket = ReceiptBoundRepairTicketService(facade=facade, policy=M6_4._policy()).persist(
        command=command,
        request=request,
        candidate_bundle_version_ref=bundle.version.candidate_bundle_version_id,
    )
    return facade, command, request, bundle, ticket, session


def test_terminal_receipt_chain_persists_no_parser_no_numeric_stop(tmp_path: Path) -> None:
    facade, command, request, bundle, ticket, session = _terminal_chain(tmp_path)
    service = ReceiptBoundParserNumericStopService(facade=facade, policy=_policy())
    first = service.persist(
        command=command,
        request=request,
        candidate_bundle_version_ref=bundle.version.candidate_bundle_version_id,
        repair_ticket_version_ref=ticket.version.repair_ticket_version_id,
    )
    stop = first.version.stop
    assert first.status == "parser_numeric_stop_persisted"
    assert stop.status == "not_attempted_typed_gap"
    assert stop.stop_code == "candidate_bundle_has_no_verified_table_context"
    assert stop.parser_execution_count == stop.numeric_fact_count == stop.numeric_trace_count == 0
    assert first.external_call_count == first.tool_invocation_count == first.model_call_count == first.parser_execution_count == 0
    assert len(session.calls) == 1
    stored = facade.store.list_versions("canonical_parser_numeric_stop_versions")
    assert len(stored) == 1
    event = [event for event in facade.store.list_events() if event["event_type"] == "RECEIPT_BOUND_PARSER_NUMERIC_STOP_PERSISTED"]
    assert len(event) == 1
    assert event[0]["state_version_before"] == 0 and event[0]["state_version_after"] == 1
    replay = service.persist(
        command=command,
        request=request,
        candidate_bundle_version_ref=bundle.version.candidate_bundle_version_id,
        repair_ticket_version_ref=ticket.version.repair_ticket_version_id,
    )
    assert replay.reused_idempotent_result is True
    assert len(facade.store.list_versions("canonical_parser_numeric_stop_versions")) == 1
    assert len(session.calls) == 1


def test_missing_or_nonexact_terminal_chain_fails_before_parser_stop_write(tmp_path: Path) -> None:
    facade, command, request, bundle, ticket, _ = _terminal_chain(tmp_path)
    service = ReceiptBoundParserNumericStopService(facade=facade, policy=_policy())
    with pytest.raises(ReceiptBoundParserNumericStopError, match="repair_ticket_exact_version_not_found"):
        service.persist(
            command=command,
            request=request,
            candidate_bundle_version_ref=bundle.version.candidate_bundle_version_id,
            repair_ticket_version_ref=f"{ticket.version.repair_ticket_id}:v2",
        )
    with pytest.raises(ReceiptBoundParserNumericStopError, match="candidate_bundle_exact_version_not_found"):
        service.persist(
            command=command,
            request=request,
            candidate_bundle_version_ref="candidate_bundle_unknown:v1",
            repair_ticket_version_ref=ticket.version.repair_ticket_version_id,
        )
    assert not facade.store.list_versions("canonical_parser_numeric_stop_versions")


def test_policy_forbids_parser_numeric_and_new_source_execution() -> None:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert raw["approval_ref"] == "approve_m6_2_5_real_bounded_sec_metadata_pilot_only"
    assert raw["authority_boundary"]["parser_execution"] == "forbidden_without_verified_table_context"
    assert raw["authority_boundary"]["numeric_fact_or_trace_creation"] == "forbidden"
    assert raw["authority_boundary"]["new_tool_or_network_call"] == "forbidden"


def test_runner_fails_closed_when_the_isolated_pilot_store_does_not_exist(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--candidate-bundle-ref", "candidate_bundle_missing:v1", "--repair-ticket-ref", "repair_ticket_missing:v1", "--store-root", str(tmp_path / "missing-store"), "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "fail_closed"
    assert result["reason"] == "pilot_store_not_found"
    assert result["external_call_count"] == result["store_write_count"] == 0


def test_runner_persists_no_parser_stop_without_a_second_network_call(tmp_path: Path) -> None:
    facade, command, request, bundle, ticket, session = _terminal_chain(tmp_path, runner_compatible=True)
    result = RUNNER.build_result(
        store_root=tmp_path,
        candidate_bundle_version_ref=bundle.version.candidate_bundle_version_id,
        repair_ticket_version_ref=ticket.version.repair_ticket_version_id,
    )
    assert result["status"] == "pass"
    assert result["external_call_count"] == 0
    assert result["parser_numeric_stop"]["parser_execution_count"] == 0
    assert result["parser_numeric_stop"]["numeric_fact_count"] == 0
    assert len(session.calls) == 1
