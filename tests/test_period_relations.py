from copy import deepcopy
import json

import pytest

from sec_agent.agent_runtime.period_relations import (
    Period, compare_periods, text_period_checks, text_period_analysis,
    workpaper_period_checks, remedy_period_checks, project_period_receipt,
)
from sec_agent.agent_runtime.workpaper_drafts import save_draft
from test_workpaper_draft_lifecycle import state, save_action


@pytest.mark.parametrize("year", [1999, 2027, 2041])
@pytest.mark.parametrize("frequency", [1, 2, 4])
@pytest.mark.parametrize("basis", ["fiscal", "unspecified"])
def test_label_arithmetic_has_no_company_or_year_exceptions(year, frequency, basis):
    current = Period(year, 1, frequency, basis)
    previous = Period(year - 1, frequency, frequency, basis)
    assert compare_periods(current, previous, "previous_period")["status"] == "consistent"
    assert compare_periods(current, Period(year - 1, 1, frequency, basis),
                           "same_period_prior_year")["status"] == "consistent"
    assert compare_periods(current, current, "previous_period")["status"] == "inconsistent"


def test_incompatible_calendar_or_frequency_is_not_a_false_contradiction():
    a = Period(2030, 2, 4, "fiscal")
    assert compare_periods(a, Period(2030, 1, 4), "previous_period")["status"] == "not_comparable"
    assert compare_periods(a, Period(2030, 1, 2, "fiscal"),
                           "previous_period")["status"] == "not_comparable"


@pytest.mark.parametrize("text,reference,expected", [
    ("2030Q4 是 2031Q2 的上一季度。", None, "2031Q1"),
    ("Q4 2030 is the previous quarter of Q2 2031.", None, "2031Q1"),
    ("本期为2031Q1。2030Q3为上一季度。", None, "2030Q4"),
    ("Current period: FY2031Q1. FY2030Q3 is the prior quarter.", None, "FY2030Q4"),
    ("本期为2031H1。2030H1为上一半年度。", None, "2030H2"),
    ("2027Q1 为上年同期。", "报告期间为2029Q1。", "2028Q1"),
    ("2030Q2、2030Q3两个对照列，分别为上年同期与上一季度。",
     "本节所有金额均为**2031Q2** 单季。", "2031Q1"),
])
def test_prose_findings_expose_binding_and_assumptions(text, reference, expected):
    checks = text_period_checks(text, path="/narrative_markdown", reference_text=reference)
    assert len(checks) == 1
    check = checks[0]
    assert check["label_check"] == {"status": "inconsistent", "expected_label": expected}
    assert check["quote"] == text[check["span"]["start"]:check["span"]["end"]]
    assert not check["blocking"] and not check["financial_semantics_verified"]
    assert check["assumptions"]


@pytest.mark.parametrize("text", [
    "本期为2031Q2。2031Q1为上一季度。",
    "本期为2031Q2。2030Q2、2031Q1为上年同期与上一季度。",
    "2030Q3不是2031Q2的上一季度。",
    "2030Q3并非上一季度。",
    "Q3 2030 is not the previous quarter of Q2 2031.",
    "2031Q2收入上升，上一季度收入下降。",
    "本期为2031Q2。2030Q3历史比较数据。",
])
def test_consistent_negated_and_non_relational_prose_does_not_raise(text):
    assert text_period_checks(text, path="/thesis") == []


def test_ambiguous_reference_and_list_do_not_choose_period():
    analysis = text_period_analysis("2030Q3为上一季度。", path="/thesis",
                               reference_text="本期为2031Q2。\n当前季度为2031Q4。")
    assert not analysis["checks"]
    checks = analysis["diagnostics"]
    assert checks[0]["reference_label"] is None
    assert checks[0]["label_check"]["status"] == "binding_unresolved"
    analysis = text_period_analysis("本期为2031Q2。2030Q2、2030Q3为上一季度。", path="/thesis")
    assert not analysis["checks"]
    checks = analysis["diagnostics"]
    assert checks[0]["comparison_label"] is None
    assert checks[0]["binding_basis"] == "ambiguous_ordered_list"


def test_no_date_taken_from_publication_or_asof_or_unrelated_later_paragraph():
    text = "发布日2031Q2。\n2030Q3为上一季度。\n本期为2031Q4。"
    analysis = text_period_analysis(text, path="/thesis")
    assert not analysis["checks"]
    check = analysis["diagnostics"][0]
    assert check["reference_label"] is None
    assert check["label_check"]["expected_label"] is None


@pytest.mark.parametrize("year", [2004, 2031, 2048])
@pytest.mark.parametrize("second", ["第 三 季度", "第三季度", "Q3"])
def test_mixed_complements_and_negative_parenthetical_scope(year, second):
    literal = f"{year - 1}年{second}"
    text = (f"本期为{year}Q2。{year - 1}Q2、{year - 1}Q3两个对照列，分别为上年同期与"
            f"{literal}的实际数（非{year}Q2数，亦非{year}Q2的上一季度），仅展示同比与趋势。")
    assert not text_period_checks(text, path="/narrative_markdown")
    # The same first slot must still be checked when it is really wrong.
    wrong = text.replace(f"{year - 1}Q2、", f"{year - 2}Q2、")
    checks = text_period_checks(wrong, path="/narrative_markdown")
    assert len(checks) == 1
    assert checks[0]["comparison_label"] == f"{year - 2}Q2"


@pytest.mark.parametrize("text,expected", [
    ("本期为2031Q2。2030Q3、2030Q1分别为2030年第三季度与上年同期。", "2030Q2"),
    ("Current period: 2031Q2. 2030Q3 and 2030Q1 are Q3 2030 and the year-earlier period respectively.", "2030Q2"),
    ("本期为2031Q2。2030Q3并非上一季度；2030Q4为上一季度。", "2031Q1"),
    ("本期为2031Q2。（2030Q3为上一季度）", "2031Q1"),
])
def test_literal_slot_keeps_order_and_negative_scope_does_not_hide_other_assertions(text, expected):
    checks = text_period_checks(text, path="/thesis")
    assert len(checks) == 1
    assert checks[0]["label_check"]["expected_label"] == expected


@pytest.mark.parametrize("text", [
    "本期为FY2031Q2。2030Q3为上一季度。",
    "本期为2031Q2。2030H1为上一季度。",
    "本期为2031Q2。2030Q2、2030Q3分别为上年同期与其他历史数据。",
    "本期为2031Q2。2030Q2、2030Q3分别为未知期间与上一季度及2030Q3。",
    "本期为2031Q2。2030Q3不是上一季度。",
])
def test_parse_uncertainty_is_not_an_author_task(text):
    result = text_period_analysis(text, path="/thesis")
    assert not result["checks"]
    assert result["diagnostics"]
    assert all(not d["author_action_required"] and "instruction" not in d
               for d in result["diagnostics"])


def test_historical_period_receipt_projection_preserves_other_feedback_and_original():
    receipt = {"saved": True, "accepted": False, "submitted": False,
        "period_relation_checks": [{"instruction": "old false warning"}],
        "semantic_check_status": "period_relations_require_author_check_not_schema_errors",
        "draft_issues": [{"code": "real_schema_issue"}], "draft_digest": "abc"}
    original = deepcopy(receipt)
    projected = project_period_receipt(receipt)
    assert receipt == original
    assert "period_relation_checks" not in projected
    assert projected["draft_issues"] == original["draft_issues"]
    assert projected["saved"] and not projected["submitted"] and not projected["accepted"]


def test_current_view_refreshes_checks_and_recent_receipt_keeps_exact_readback():
    from langchain_core.messages import AIMessage, ToolMessage
    from sec_agent.agent_runtime.research_context_view import (
        compact_current_context, compact_accepted_operations, public_operation,
    )
    stale = {"saved": True, "submitted": False, "accepted": False, "draft_digest": "same",
             "period_relation_checks": [{"code": "period_relation_requires_check", "instruction": "old warning"}]}
    context = {"task_context": {}, "submission_to_repair": {
        "candidate": {"narrative_markdown": "本期为2031Q2。2030Q2为上年同期。"},
        "last_edit_feedback": stale, "period_relation_checks": stale["period_relation_checks"]}}
    original = deepcopy(context)
    projected = compact_current_context(context)
    assert not projected["submission_to_repair"]["period_relation_checks"]
    assert "period_relation_checks" not in projected["submission_to_repair"]["last_edit_feedback"]
    journal = [
        AIMessage(content="", tool_calls=[{"id": "save", "name": "SaveWorkpaperEditsAction", "args": {}}]),
        ToolMessage(content=json.dumps({"result": stale}), name="SaveWorkpaperEditsAction", tool_call_id="save"),
    ]
    recent = deepcopy(journal)
    compact_accepted_operations(recent, {"current_context": projected})
    visible = json.loads(recent[-1].content)["result"]
    assert "period_relation_checks" not in visible and visible["saved"]
    assert visible["draft_digest"] == "same" and not visible["accepted"]
    assert public_operation(journal, "save")["receipt"]["result"] == stale
    assert context == original


def test_citation_and_historical_notes_are_not_new_author_assertions():
    misleading = "本期为2031Q2。2030Q3为上一季度。"
    assert workpaper_period_checks({"task_note": {"changes": misleading},
        "claims": [{"claim_id": "C1", "citation_quotes": {"SOURCE": misleading},
                    "authority_note": misleading}]}) == []


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("saved", [False, True, None])
def test_native_receipt_projection_only_retires_acknowledged_checks(nested, saved):
    from langchain_core.messages import AIMessage, ToolMessage
    from sec_agent.agent_runtime.research_context_view import (
        compact_accepted_operations, public_operation,
    )
    receipt = {"saved": saved, "accepted": False, "draft_digest": "unchanged",
               "period_relation_checks": [{"instruction": "historical warning"}],
               "draft_issues": [{"code": "still_actionable"}],
               "source": {"period_relation_checks": ["source data, not feedback"]}}
    result = {"draft_result": receipt, "feedback": ["preserve"]} if nested else receipt
    journal = [
        AIMessage(content="", tool_calls=[{"id": "s", "name": "SaveWorkpaperEditsAction", "args": {}}]),
        ToolMessage(content=json.dumps({"result": result}), name="SaveWorkpaperEditsAction", tool_call_id="s"),
    ]
    frozen = deepcopy(journal)
    # No authoritative current check view: do not hide historical feedback.
    recent = deepcopy(journal)
    compact_accepted_operations(recent, {"current_context": {"submission_to_repair": {}}})
    assert recent == journal
    current_checks = [{"instruction": "real current contradiction"}]
    view = {"current_context": {"submission_to_repair": {"period_relation_checks": current_checks}}}
    compact_accepted_operations(recent, view)
    visible = json.loads(recent[-1].content)["result"]
    if nested:
        assert visible["feedback"] == ["preserve"]
        visible = visible["draft_result"]
    if saved is True:
        assert "period_relation_checks" not in visible
        assert visible["period_check_view"]["current_checks_at"].endswith("/period_relation_checks")
    else:
        assert visible == receipt
    assert visible["draft_issues"] == receipt["draft_issues"]
    assert visible["source"] == receipt["source"]
    assert visible["draft_digest"] == "unchanged" and visible["accepted"] is False
    assert view["current_context"]["submission_to_repair"]["period_relation_checks"] == current_checks
    assert recent[0] == journal[0]
    assert public_operation(journal, "s")["receipt"]["result"] == result
    assert journal == frozen


def test_old_feedback_projection_always_has_a_current_destination():
    from sec_agent.agent_runtime.research_context_view import compact_current_context
    context = {"task_context": {}, "submission_to_repair": {
        "candidate": {"narrative_markdown": "本期为2031Q2。2030Q2为上年同期。"},
        "last_edit_feedback": {"draft_result": {"saved": True,
            "period_relation_checks": [{"instruction": "old warning"}]}}}}
    projected = compact_current_context(context)["submission_to_repair"]
    assert projected["period_relation_checks"] == []
    assert "period_relation_checks" not in projected["last_edit_feedback"]["draft_result"]


def test_save_keeps_proposal_and_current_check_survives_claim_of_correction():
    s = state()
    narrative = "本期为2031Q2。2030Q3为上一季度。"
    action = save_action(s, [{"op": "set_field", "path": "/narrative_markdown", "value": narrative}])
    original = deepcopy(s)
    draft, receipt = save_draft(s, action)
    assert s == original and draft["arguments"]["narrative_markdown"] == narrative
    assert receipt["saved"] and not receipt["accepted"] and not receipt["submitted"]
    assert receipt["period_relation_checks"] and receipt["draft_issues"] == []
    candidate = deepcopy(draft["arguments"])
    candidate["task_note"] = {"finding_responses": [{"finding_id": "period", "disposition": "corrected"}]}
    assert workpaper_period_checks(candidate) == receipt["period_relation_checks"]
    s["workpaper_draft"] = draft
    fixed, next_receipt = save_draft(s, save_action(s, [
        {"op": "set_field", "path": "/narrative_markdown",
         "value": "本期为2031Q2。2030Q3为历史对照季度。"}], operation="fixed"))
    assert not workpaper_period_checks(fixed["arguments"])
    assert "period_relation_checks" not in next_receipt
    assert draft["receipts"][action.operation_id]["receipt"] == receipt


def test_lead_remedy_is_checked_against_its_paper_without_changing_it():
    findings = [{"paper_id": "A", "finding_id": "x", "requested_change": "补一句2030Q3为上一季度。"}]
    original = deepcopy(findings)
    checks = remedy_period_checks(findings, lambda pid: {"narrative_markdown": "本期为2031Q2。"})
    assert findings == original
    assert checks[0]["paper_id"] == "A" and checks[0]["finding_id"] == "x"
    assert checks[0]["label_check"]["expected_label"] == "2031Q1"


def test_author_handoff_preserves_original_feedback_and_checks_lead_provenance():
    from sec_agent.agent_runtime.author_revision import author_feedback
    class Artifacts:
        def read_paper(self, pid):
            return {"narrative_markdown": "本期为2031Q2。"}
    feedback = [{"paper_id": "A", "finding_id": "x", "requested_change": "检查期间说明。",
                 "lead_requested_change": "补一句2030Q3为上一季度。"}]
    original = deepcopy(feedback)
    result = author_feedback(feedback, Artifacts())
    assert feedback == original and result[0]["lead_requested_change"] == original[0]["lead_requested_change"]
    assert result[0]["runtime_period_checks"][0]["path"] == "/lead_requested_change"
    assert result[0]["runtime_period_checks"][0]["label_check"]["expected_label"] == "2031Q1"


def test_native_save_next_request_and_final_receipt_all_preserve_advisory():
    from sec_agent.agent_runtime.specialist_graph import (
        SpecialistAgenticDependencies, build_specialist_agentic_state_graph,
    )
    from test_workpaper_partial_edits import paper
    from test_specialist_graph import _input, _ToolPorts, _evidence_action, _finance_action
    from test_specialist_tool_batch import _batch
    ports = _ToolPorts()
    requests = []
    def model(request):
        requests.append(request)
        if len(requests) == 1:
            return _batch(request, [_evidence_action()({}), _finance_action()({})])
        if len(requests) == 2:
            value = paper()
            value["claims"][0]["evidence_ids"] = ["E:unobserved"]
            return _batch(request, [value])
        repair = request["submission_to_repair"]
        if len(requests) == 3:
            return _batch(request, [{"action": "save_workpaper_edits", "operation_id": "period",
                "reason_summary": "Save exact author wording.", "base_submission_digest": repair["base_submission_digest"],
                "edits": [
                    {"op": "set_field", "path": "/narrative_markdown",
                     "value": "本期为2031Q2。2030Q3为上一季度。"},
                    {"op": "update_claim", "claim_id": repair["candidate"]["claims"][0]["claim_id"],
                     "changes": {"evidence_ids": ["E:DELL:Q1"]}}]}])
        assert len(requests) == 4
        assert repair["period_relation_checks"][0]["label_check"]["expected_label"] == "2031Q1"
        return _batch(request, [{"action": "finalize_workpaper_revision",
            "reason_summary": "Fixture submits despite advisory; runtime must not certify semantics.",
            "draft_digest": repair["base_submission_digest"]}])
    deps = SpecialistAgenticDependencies(model_turn=model, evidence_tool=ports.evidence,
        finance_tool=ports.finance, allow_workpaper_field_edits=True)
    result = build_specialist_agentic_state_graph(dependencies=deps).compile().invoke(
        _input(), {"recursion_limit": 60})
    assert result["phase"] == "specialist_submission_accepted"
    receipt = json.loads(result["tool_results"][0]["content"])
    assert receipt["accepted"] and receipt["period_relation_checks"]
    assert receipt["semantic_check_status"] == "not_verified_by_submission_acceptance"
    assert result["final_submission"]["narrative_markdown"] == "本期为2031Q2。2030Q3为上一季度。"


def test_review_check_survives_navigation_without_new_assignments_or_verdict():
    from test_confirmation_change_handoff import setup
    from sec_agent.agent_runtime.workpaper_changes import confirmation_context
    from sec_agent.agent_runtime.review_context import confirmation_navigation, handoff_page
    artifacts, _, after, revisions, feedback = setup()
    after["narrative_markdown"] = "本期为2031Q2。2030Q3为上一季度。"
    original = deepcopy((revisions, feedback))
    context = confirmation_context(artifacts, revisions, feedback)
    nav = confirmation_navigation(context)
    assert nav["runtime_period_checks"] == context["runtime_period_checks"]
    assert nav["findings_to_confirm"] == feedback
    # Use the same per-paper selection as the paged readback, without unrelated
    # diff text exceeding the first page.
    page = handoff_page(artifacts, {"runtime_period_checks": nav["runtime_period_checks"]},
                        section="revision_confirmation", paper_id="P01")
    assert json.loads(page["text"])["runtime_period_checks"] == nav["runtime_period_checks"]["P01"]
    assert (revisions, feedback) == original
