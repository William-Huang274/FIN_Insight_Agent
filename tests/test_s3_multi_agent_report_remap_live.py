from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from sec_agent.providers import ChatCompletionToolStepResult
from sec_agent.research.multi_agent_report_authority import (
    MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/research/run_s3_multi_agent_report_remap_live.py"
SPEC = importlib.util.spec_from_file_location("report_remap_live_runner", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
ReportRemapLiveError = RUNNER.ReportRemapLiveError
_result_execution = RUNNER._result_execution
execute_contract_attempts = RUNNER.execute_contract_attempts
SOURCE = (
    ROOT
    / "data/workbench_private/model_runs/fin_0_1_3_s3_dell_multi_agent_"
    "preview_writer_terminal_submission_successor_20260821/full_result.json"
)
CATALOG = (
    ROOT
    / "configs/research/fin_ia_0_1_3_s3_dell_multi_agent_"
    "report_authority_catalog_v1_1.json"
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _clause(
    *,
    agent_ids,
    claim_ref="",
    evidence_ref="",
    authority_ref="",
    gap_ref="",
    text="The reviewed evidence supports a bounded conclusion with material uncertainty.",
):
    return {
        "model_text": text,
        "source_workpaper_agent_ids": list(agent_ids),
        "source_claim_refs": [claim_ref] if claim_ref else [],
        "evidence_refs": [evidence_ref] if evidence_ref else [],
        "authority_refs": [authority_ref] if authority_ref else [],
        "gap_refs": [gap_ref] if gap_ref else [],
    }


def _actual_fixture():
    full = _load(SOURCE)
    source = full["report"]
    evaluation = full["evaluations"][-1]
    catalog = _load(CATALOG)
    claims_by_agent = {}
    for claim in catalog["claims"]:
        claims_by_agent.setdefault(claim["agent_id"], claim)
    gaps_by_agent = {
        row["agent_id"]: list(row["gap_refs"])
        for row in catalog["workpaper_gap_bindings"]
    }

    def claim_clause(agent_ids, *, text=None):
        claim = claims_by_agent[agent_ids[0]]
        return _clause(
            agent_ids=agent_ids,
            claim_ref=claim["claim_ref"],
            evidence_ref=claim["evidence_refs"][0],
            text=text
            or "The reviewed evidence supports a bounded conclusion with material uncertainty.",
        )

    sections = []
    source_agent_orders = [
        list(row["source_workpaper_agent_ids"]) for row in source["sections"]
    ]
    for index, agent_ids in enumerate(source_agent_orders):
        sections.append(
            {
                "heading": f"Bounded research perspective {chr(65 + index)}",
                "clauses": [claim_clause(agent_ids)],
            }
        )
    gap_rows = []
    agents_with_gaps = [
        agent for agent in source_agent_orders if gaps_by_agent.get(agent[0])
    ]
    for index in range(len(source["remaining_gaps"])):
        agent_ids = agents_with_gaps[index % len(agents_with_gaps)]
        gap_rows.append(
            _clause(
                agent_ids=agent_ids,
                gap_ref=gaps_by_agent[agent_ids[0]][0],
                text="Direct public disclosure remains unavailable after bounded retrieval.",
            )
        )
    wwc_rows = [
        claim_clause(
            source_agent_orders[index % len(source_agent_orders)],
            text="A verified change in the operating mechanism would alter this conclusion.",
        )
        for index in range(len(source["what_would_change"]))
    ]
    payload = {
        "schema_version": MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
        "report_topic": "Demand quality, value capture and operating conversion",
        "executive_thesis": [claim_clause(source_agent_orders[0])],
        "sections": sections,
        "remaining_gaps": gap_rows,
        "what_would_change": wwc_rows,
        "confidence": claim_clause(
            source_agent_orders[0],
            text="Confidence is bounded because causal attribution and decomposition remain incomplete.",
        ),
    }
    return source, evaluation, catalog, payload


def _result(payload, number):
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fake",
        model="fake-model",
        content="",
        reasoning_content="",
        tool_calls=(
            {
                "id": f"call-{number}",
                "type": "function",
                "function": {
                    "name": "submit_protected_report_draft",
                    "arguments": json.dumps(payload, ensure_ascii=False),
                },
            },
        ),
        finish_reason="tool_calls",
        usage={"completion_tokens": 10},
        request_capture_ref=f"request-{number}.json",
        response_capture_ref=f"response-{number}.json",
        request_digest=f"request-digest-{number}",
        response_digest=f"response-digest-{number}",
        private_reasoning_fields_redacted=0,
    )


def test_one_logical_writer_node_allows_one_feedback_bound_contract_correction(
    tmp_path: Path,
) -> None:
    source, evaluation, catalog, valid = _actual_fixture()
    invalid = deepcopy(valid)
    invalid["executive_thesis"][0]["model_text"] = (
        "Revenue increased by 10 percent, which is a forbidden free surface."
    )
    calls = []

    def fake_executor(**kwargs):
        calls.append(kwargs)
        return _result(invalid if len(calls) == 1 else valid, len(calls))

    draft, rendered, attempts = execute_contract_attempts(
        profile=object(),
        source_report=source,
        evaluation=evaluation,
        authority_catalog=catalog,
        capture_root=tmp_path,
        run_id="TEST-REPORT-REMAP",
        executor=fake_executor,
    )

    execution = _result_execution(attempts=attempts, success=True)
    assert len(calls) == 2
    assert attempts[0]["status"] == "contract_rejected"
    assert attempts[1]["status"] == "contract_validated_and_rendered"
    assert calls[1]["messages"][-1]["role"] == "tool"
    assert "remaining_contract_attempts" in calls[1]["messages"][-1]["content"]
    assert execution["logical_model_node_count"] == 1
    assert execution["contract_attempt_count"] == 2
    assert execution["analysis_call_count"] == 0
    assert execution["scope_compliant"] is True
    assert draft["remap_receipt"]["section_count_preserved"] is True
    assert rendered["rendering_authority"][
        "case_identity_period_numeric_and_citations_harness_rendered"
    ] is True


def test_second_contract_rejection_is_terminal_and_preserves_both_attempts(
    tmp_path: Path,
) -> None:
    source, evaluation, catalog, invalid = _actual_fixture()
    invalid["executive_thesis"][0]["model_text"] = "Revenue was 10."
    calls = []

    def fake_executor(**kwargs):
        calls.append(kwargs)
        return _result(invalid, len(calls))

    with pytest.raises(ReportRemapLiveError) as caught:
        execute_contract_attempts(
            profile=object(),
            source_report=source,
            evaluation=evaluation,
            authority_catalog=catalog,
            capture_root=tmp_path,
            run_id="TEST-REPORT-REMAP-FAIL",
            executor=fake_executor,
        )
    assert len(calls) == 2
    assert len(caught.value.attempts) == 2
    assert all(row["status"] == "contract_rejected" for row in caught.value.attempts)


def test_transport_failure_is_not_silently_retried(tmp_path: Path) -> None:
    source, evaluation, catalog, _ = _actual_fixture()
    calls = []

    def fake_executor(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("offline")

    with pytest.raises(
        ReportRemapLiveError,
        match="report_remap_live_provider_transport_failure",
    ) as caught:
        execute_contract_attempts(
            profile=object(),
            source_report=source,
            evaluation=evaluation,
            authority_catalog=catalog,
            capture_root=tmp_path,
            run_id="TEST-REPORT-REMAP-TRANSPORT",
            executor=fake_executor,
        )
    assert len(calls) == 1
    assert len(caught.value.attempts) == 1
    assert caught.value.attempts[0]["status"] == "terminal_transport_failure"
