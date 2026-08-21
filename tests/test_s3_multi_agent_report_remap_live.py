from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from sec_agent.providers import ChatCompletionToolStepResult
from sec_agent.research.multi_agent_report_authority import (
    MULTI_AGENT_PROTECTED_REPORT_DRAFT_LEGACY_SCHEMA_VERSION,
    MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
    MULTI_AGENT_PROTECTED_REPORT_REFERENCE_PATCH_SCHEMA_VERSION,
    MultiAgentReportAuthorityError,
    _clause_at_path,
    apply_protected_report_reference_patch,
    compile_protected_report_reference_patch_receipt,
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
execute_reference_patch_attempts = RUNNER.execute_reference_patch_attempts
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
FAILED_REPLACEMENT = (
    ROOT
    / "data/workbench_private/model_runs/fin_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_replacement_20260821/terminal_failure.json"
)
REFERENCE_PATCH_PROOF = (
    ROOT
    / "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_report_"
    "reference_patch_zero_call_result_v1_0.json"
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


def _actual_reference_patch_fixture():
    failed = _load(FAILED_REPLACEMENT)
    base = json.loads(
        failed["contract_attempts"][1]["tool_calls"][0]["function"][
            "arguments"
        ]
    )
    catalog = _load(CATALOG)
    source = _load(SOURCE)["report"]
    receipt = compile_protected_report_reference_patch_receipt(
        base, authority_catalog=catalog
    )
    rows = {
        path: {
            name: list(_clause_at_path(base, path)[name])
            for name in (
                "source_claim_refs",
                "evidence_refs",
                "authority_refs",
                "gap_refs",
            )
        }
        for path in receipt["target_paths"]
    }
    rows["executive_thesis[0]"]["authority_refs"] = [
        ref
        for ref in rows["executive_thesis[0]"]["authority_refs"]
        if ref
        not in {
            "REL::B60164179DFFDF5A",
            "REL::E07667E373A33286",
            "REL::E3A67501DFA73ACF",
            "REL::E773B8CD872C906A",
        }
    ]
    rows["sections[5].clauses[0]"]["source_claim_refs"].remove(
        "WPCLAIM::62610751A8539DC0DB2E"
    )
    rows["sections[5].clauses[0]"]["evidence_refs"].remove(
        "EV::734A9C177164E08E"
    )
    rows["remaining_gaps[1]"]["gap_refs"] = [
        "GAP::00730082A5C08C4C"
    ]
    rows["remaining_gaps[3]"] = {
        "source_claim_refs": ["WPCLAIM::C9ABFB9176456AB25DDC"],
        "evidence_refs": ["EV::7F4D7E6762C21D83"],
        "authority_refs": [],
        "gap_refs": ["GAP::34844D3F9935C0F5"],
    }
    rows["what_would_change[2]"]["source_claim_refs"] = [
        "WPCLAIM::C9ABFB9176456AB25DDC"
    ]
    rows["what_would_change[2]"]["evidence_refs"] = [
        "EV::7F4D7E6762C21D83"
    ]
    patch = {
        "schema_version": MULTI_AGENT_PROTECTED_REPORT_REFERENCE_PATCH_SCHEMA_VERSION,
        "base_payload_digest": receipt["base_payload_digest"],
        "patches": [
            {"field_path": path, **rows[path]}
            for path in receipt["target_paths"]
        ],
    }
    return failed, base, catalog, source, receipt, patch


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


def _truncated_result(number):
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
                    "arguments": '{"schema_version":"incomplete',
                },
            },
        ),
        finish_reason="length",
        usage={"completion_tokens": 7000},
        request_capture_ref=f"request-{number}.json",
        response_capture_ref=f"response-{number}.json",
        request_digest=f"request-digest-{number}",
        response_digest=f"response-digest-{number}",
        private_reasoning_fields_redacted=0,
    )


def _patch_result(payload, number):
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fake",
        model="fake-model",
        content="",
        reasoning_content="",
        tool_calls=(
            {
                "id": f"patch-call-{number}",
                "type": "function",
                "function": {
                    "name": "submit_protected_report_reference_patch",
                    "arguments": json.dumps(payload, ensure_ascii=False),
                },
            },
        ),
        finish_reason="tool_calls",
        usage={"completion_tokens": 10},
        request_capture_ref=f"patch-request-{number}.json",
        response_capture_ref=f"patch-response-{number}.json",
        request_digest=f"patch-request-digest-{number}",
        response_digest=f"patch-response-digest-{number}",
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


def test_truncated_tool_arguments_keep_call_id_and_receive_contract_feedback(
    tmp_path: Path,
) -> None:
    source, evaluation, catalog, valid = _actual_fixture()
    calls = []

    def fake_executor(**kwargs):
        calls.append(kwargs)
        return _truncated_result(1) if len(calls) == 1 else _result(valid, 2)

    _, _, attempts = execute_contract_attempts(
        profile=object(),
        source_report=source,
        evaluation=evaluation,
        authority_catalog=catalog,
        capture_root=tmp_path,
        run_id="TEST-REPORT-REMAP-TRUNCATED",
        executor=fake_executor,
    )

    assert len(calls) == 2
    assert attempts[0]["failure_code"] == (
        "report_remap_live_tool_arguments_truncated_at_output_budget"
    )
    assert calls[1]["messages"][-1]["tool_call_id"] == "call-1"
    assert "complete contract from the beginning" in (
        calls[1]["messages"][-1]["content"]
    )
    assert attempts[1]["status"] == "contract_validated_and_rendered"


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


def test_reference_patch_reuses_complete_payload_and_feedback_is_actionable(
    tmp_path: Path,
) -> None:
    source, _, catalog, valid = _actual_fixture()
    base = deepcopy(valid)
    base["schema_version"] = (
        MULTI_AGENT_PROTECTED_REPORT_DRAFT_LEGACY_SCHEMA_VERSION
    )
    base["executive_thesis"][0]["model_text"] = "A" * 1200
    selected_claim = next(
        row
        for row in catalog["claims"]
        if row["claim_ref"]
        == base["executive_thesis"][0]["source_claim_refs"][0]
    )
    bad_authority = next(
        row["authority_ref"]
        for row in catalog["presentation_authority"]
        if row["authority_ref"] not in set(selected_claim["authority_refs"])
    )
    base["executive_thesis"][0]["authority_refs"] = [bad_authority]
    base["remaining_gaps"][0]["gap_refs"] = []
    patch_receipt = compile_protected_report_reference_patch_receipt(
        base, authority_catalog=catalog
    )
    valid_patch = {
        "schema_version": MULTI_AGENT_PROTECTED_REPORT_REFERENCE_PATCH_SCHEMA_VERSION,
        "base_payload_digest": patch_receipt["base_payload_digest"],
        "patches": [
            {
                "field_path": "executive_thesis[0]",
                "source_claim_refs": list(
                    valid["executive_thesis"][0]["source_claim_refs"]
                ),
                "evidence_refs": list(
                    valid["executive_thesis"][0]["evidence_refs"]
                ),
                "authority_refs": list(
                    valid["executive_thesis"][0]["authority_refs"]
                ),
                "gap_refs": list(valid["executive_thesis"][0]["gap_refs"]),
            },
            {
                "field_path": "remaining_gaps[0]",
                "source_claim_refs": list(
                    valid["remaining_gaps"][0]["source_claim_refs"]
                ),
                "evidence_refs": list(
                    valid["remaining_gaps"][0]["evidence_refs"]
                ),
                "authority_refs": list(
                    valid["remaining_gaps"][0]["authority_refs"]
                ),
                "gap_refs": list(valid["remaining_gaps"][0]["gap_refs"]),
            },
        ],
    }
    invalid_patch = deepcopy(valid_patch)
    invalid_patch["patches"][1]["gap_refs"] = []
    calls = []

    def fake_executor(**kwargs):
        calls.append(kwargs)
        return _patch_result(
            invalid_patch if len(calls) == 1 else valid_patch,
            len(calls),
        )

    draft, rendered, attempts, returned_receipt = execute_reference_patch_attempts(
        profile=object(),
        base_payload=base,
        source_report=source,
        authority_catalog=catalog,
        capture_root=tmp_path,
        run_id="TEST-REPORT-REFERENCE-PATCH",
        executor=fake_executor,
    )

    assert len(calls) == 2
    assert attempts[0]["status"] == "contract_rejected"
    assert attempts[0]["failure_details"]["contract_finding_receipt"][
        "hard_findings"
    ][0]["field_path"] == "remaining_gaps[0]"
    feedback = json.loads(calls[1]["messages"][-1]["content"])
    assert feedback["failure_details"]["contract_finding_receipt"][
        "hard_findings"
    ][0]["details"]["allowed_refs"]["gap_refs"]
    assert attempts[1]["status"] == "reference_patch_validated_and_rendered"
    assert draft["reference_patch_receipt"]["model_text_unchanged"] is True
    assert draft["surface_contract_receipt"][
        "recommended_narrative_density_pass"
    ] is False
    assert rendered["rendered_report_digest"]
    assert returned_receipt["patch_receipt_digest"] == patch_receipt[
        "patch_receipt_digest"
    ]


def test_real_replacement_capture_has_one_bounded_five_path_patch_surface() -> None:
    failed, base, catalog, source, receipt, valid_patch = (
        _actual_reference_patch_fixture()
    )
    proof = _load(REFERENCE_PATCH_PROOF)

    assert len(failed["contract_attempts"]) == 2
    assert failed["contract_attempts"][1]["finish_reason"] == "tool_calls"
    assert receipt["target_paths"] == proof["actual_replay"]["target_paths"]
    assert len(receipt["hard_findings"]) == 5
    assert len(receipt["quality_findings_preserved_for_later_assessment"]) == 5

    trusted = apply_protected_report_reference_patch(
        valid_patch,
        base_payload=base,
        patch_receipt=receipt,
        authority_catalog=catalog,
        source_report=source,
    )
    assert trusted["draft_digest"] == proof["synthetic_valid_patch_replay"][
        "draft_digest"
    ]
    assert trusted["reference_patch_receipt"]["model_text_unchanged"] is True
    assert trusted["reference_patch_receipt"][
        "source_workpaper_agent_ids_unchanged"
    ] is True
    assert trusted["reference_patch_receipt"]["unlisted_paths_modified"] is False

    prose_patch = deepcopy(valid_patch)
    prose_patch["patches"][0]["model_text"] = "forbidden rewrite"
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_reference_patch_fields_invalid",
    ):
        apply_protected_report_reference_patch(
            prose_patch,
            base_payload=base,
            patch_receipt=receipt,
            authority_catalog=catalog,
            source_report=source,
        )

    wrong_path = deepcopy(valid_patch)
    wrong_path["patches"][0]["field_path"] = "confidence"
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_reference_patch_paths_invalid",
    ):
        apply_protected_report_reference_patch(
            wrong_path,
            base_payload=base,
            patch_receipt=receipt,
            authority_catalog=catalog,
            source_report=source,
        )

    unknown_ref = deepcopy(valid_patch)
    unknown_ref["patches"][0]["authority_refs"] = ["REL::UNKNOWN"]
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_reference_patch_ref_invalid",
    ):
        apply_protected_report_reference_patch(
            unknown_ref,
            base_payload=base,
            patch_receipt=receipt,
            authority_catalog=catalog,
            source_report=source,
        )

    cross_agent = deepcopy(valid_patch)
    cross_agent["patches"][1]["source_claim_refs"] = [
        "WPCLAIM::62610751A8539DC0DB2E"
    ]
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_reference_patch_ref_invalid",
    ):
        apply_protected_report_reference_patch(
            cross_agent,
            base_payload=base,
            patch_receipt=receipt,
            authority_catalog=catalog,
            source_report=source,
        )

    missing_gap = deepcopy(valid_patch)
    missing_gap["patches"][2]["gap_refs"] = []
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_reference_patch_still_invalid",
    ):
        apply_protected_report_reference_patch(
            missing_gap,
            base_payload=base,
            patch_receipt=receipt,
            authority_catalog=catalog,
            source_report=source,
        )
