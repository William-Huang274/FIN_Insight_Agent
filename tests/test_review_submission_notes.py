"""Review annotation compatibility does not grant research acceptance."""
import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sec_agent.agent_runtime.case_review_agent import (
    InvalidToolCallFeedback, SubmittedCaseReview, build_case_reviewer,
)
from sec_agent.agent_runtime.review_submission_notes import preserve_assessment_notes
from sec_agent.agent_runtime.review_recovery import public_review, public_confirmation
from test_case_review_agent import call, review_fixture
from test_review_argument_recovery import RecoveryChat
from test_review_inspection_recovery import reads
from test_research_convergence import artifact_fixture


def proposal():
    review = review_fixture(artifact_fixture())
    review["completion"] = "complete"
    review["assessments"][0]["verdict_note"] = '原样说明\n"resolved" is author text only.'
    return {"review": review}


def test_preserve_exact_provenance_idempotence_and_original_response():
    raw = proposal()
    before = deepcopy(raw)
    normalized, records = preserve_assessment_notes(raw)
    assert raw == before
    row = normalized["review"]["assessments"][0]
    assert row["assessment"] == raw["review"]["assessments"][0]["assessment"]
    assert row["supplemental_notes"] == [{
        "original_field": "verdict_note", "original_path": "/review/assessments/0/verdict_note",
        "text": raw["review"]["assessments"][0]["verdict_note"],
    }]
    assert records[0]["basis"]["paper_id"] == row["paper_id"]
    assert preserve_assessment_notes(normalized) == (normalized, [])
    duplicated = deepcopy(normalized)
    duplicated["review"]["assessments"][0]["verdict_note"] = row["supplemental_notes"][0]["text"]
    assert preserve_assessment_notes(duplicated)[0] == normalized
    message = AIMessage(content="", tool_calls=[call("submit_case_review", raw, "s")])
    result = InvalidToolCallFeedback().after_model({"messages": [message]}, None)["messages"][0]
    assert message.tool_calls[0]["args"] == before
    assert result.response_metadata["tool_argument_recovery"][0]["original_arguments"] == before
    assert InvalidToolCallFeedback().after_model({"messages": [result]}, None) is None
    assert public_review(SubmittedCaseReview.model_validate(normalized["review"]).model_dump())[
        "assessments"][0]["supplemental_notes"] == row["supplemental_notes"]


@pytest.mark.parametrize("problem", ["object", "too_long", "unknown_status", "conflict", "bad_notes"])
def test_unsafe_values_are_preserved_and_rejected(problem):
    raw = proposal()
    row = raw["review"]["assessments"][0]
    if problem == "object":
        row["verdict_note"] = {"status": "resolved"}
    elif problem == "too_long":
        row["verdict_note"] = "x" * 5001
    elif problem == "unknown_status":
        row["resolved"] = True
    elif problem == "conflict":
        row["supplemental_notes"] = [{"original_field": "verdict_note",
            "original_path": "/review/assessments/0/verdict_note", "text": "Different author text"}]
    else:
        row["supplemental_notes"] = "not a list"
    before = deepcopy(raw)
    normalized, _ = preserve_assessment_notes(raw)
    assert raw == before
    with pytest.raises(ValueError):
        SubmittedCaseReview.model_validate(normalized["review"])
    if problem != "unknown_status":
        assert normalized == before
    else:
        assert normalized["review"]["assessments"][0]["resolved"] is True


@pytest.mark.parametrize("problem", ["none", "unread", "unconfirmed", "bad_source", "unfinished", "unknown"])
def test_native_submission_preserves_notes_without_bypassing_validation(problem):
    async def run():
        artifacts = artifact_fixture()
        raw = proposal()
        confirmation = None
        if problem == "unconfirmed":
            from sec_agent.agent_runtime.workpaper_changes import paper_versions
            confirmation = {"paper_version_digests": paper_versions(artifacts),
                "findings_to_confirm": {"P01": [{"finding_id": "must-confirm", "paper_id": "P01"}]}}
        if problem == "unfinished":
            raw["review"]["unresolved_data_requests"] = ["Required check not performed."]
        if problem == "unknown":
            raw["review"]["assessments"][0]["override_status"] = "resolved"
        if problem == "bad_source":
            raw["review"]["findings"] = [{"finding_id": "F", "paper_id": "P01", "severity": "advisory",
                "diagnosis": "Synthetic diagnosis only.", "requested_change": "Synthetic change request only.",
                "problematic_quote": artifacts.read_paper("P01")["thesis"],
                "source_checks": [{"source_id": "missing-source", "quote": "unavailable"}]}]
        before = deepcopy(raw)
        agent = build_case_reviewer(role="verifier", artifacts=artifacts, tools=[],
            model=RecoveryChat(marker="notes", replies=[[call("submit_case_review", raw, "s")]]),
            confirmation=confirmation, max_model_calls=1)
        state = await agent.ainvoke({"messages": [HumanMessage(content="Synthetic test only."),
            *(reads(artifacts) if problem != "unread" else [])]})
        assert raw == before
        receipt = next(m for m in state["messages"] if isinstance(m, ToolMessage) and m.tool_call_id == "s")
        assert (receipt.status == "success") == (problem == "none"), receipt.content
        assert bool(state.get("review")) == (problem == "none")
        if problem in ("unfinished", "unknown"):
            detail = json.loads(receipt.content)
            assert detail["preserved_supplemental_notes"][0]["original_path"] == "/review/assessments/0/verdict_note"
            assert detail["executed"] is False
        if problem == "none":
            note = state["review"]["assessments"][0]["supplemental_notes"][0]
            assert note["text"] == raw["review"]["assessments"][0]["verdict_note"]
            assert public_review(state["review"])["assessments"][0]["supplemental_notes"] == [note]
            assert any(r["method"] == "assessment_note_preservation_v1"
                for r in receipt.artifact["runtime_parsing"])
            handoff = public_confirmation({"review": {"verifier": {
                "status": "review_submitted", "review": state["review"],
                "runtime_parsing": state["runtime_parsing"]}}})["review"]["verifier"]
            assert handoff["review"]["assessments"][0]["supplemental_notes"] == [note]
            assert handoff["annotation_preservation"][0]["field_path"] == note["original_path"]
            assert "original_input" not in handoff["annotation_preservation"][0]
    asyncio.run(run())
