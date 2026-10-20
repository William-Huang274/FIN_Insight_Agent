"""Scope contracts only; no financial acceptance or model calls."""
from copy import deepcopy

import pytest

from sec_agent.agent_runtime.case_review_agent import CaseReview, review_assessment_scope
from sec_agent.agent_runtime.research_session import responsible_author_feedback
from test_research_convergence import artifact_fixture
from test_case_review_agent import review_fixture


def bundle(artifacts, assessed):
    review = review_fixture(artifacts)
    review["assessments"] = [
        {"paper_id": pid, "assessment": "Synthetic assessment for scope routing only."}
        for pid in assessed
    ]
    return {role: {"status": "review_submitted", "review": deepcopy(review)}
            for role in ("counter", "verifier")}


def test_local_scope_preserves_reviews_and_full_scope_stays_strict():
    artifacts = artifact_fixture()
    result = bundle(artifacts, ["P02"])
    before = deepcopy(result)
    context = {"findings_to_confirm": {"P02": [{"finding_id": "F1"}]}}
    assert responsible_author_feedback(result, artifacts, confirmation=context) == {}
    assert result == before
    with pytest.raises(ValueError, match="research_review_paper_scope_mismatch"):
        responsible_author_feedback(result, artifacts)
    assert responsible_author_feedback(bundle(artifacts, ["P01", "P02"]), artifacts) == {}


@pytest.mark.parametrize("assessed,assigned,error", [
    (["P01"], ["P02"], "research_review_paper_scope_mismatch"),
    (["P02", "P02"], ["P02"], "research_review_paper_scope_mismatch"),
    (["P02", "P99"], ["P02"], "research_confirmation_paper_scope_invalid"),
    (["P02"], ["P99"], "research_confirmation_paper_scope_invalid"),
    (["P02"], [], "research_confirmation_paper_scope_invalid"),
])
def test_confirmation_cannot_shrink_assignment_or_accept_invalid_scope(assessed, assigned, error):
    artifacts = artifact_fixture()
    with pytest.raises(ValueError, match=error):
        responsible_author_feedback(bundle(artifacts, assessed), artifacts,
            confirmation={"findings_to_confirm": {pid: [] for pid in assigned}})


def test_relevant_extra_assessment_allowed_but_extra_finding_requires_assessment():
    artifacts = artifact_fixture()
    context = {"findings_to_confirm": {"P02": []}}
    assert responsible_author_feedback(bundle(artifacts, ["P01", "P02"]), artifacts,
                                      confirmation=context) == {}
    review = CaseReview.model_validate(bundle(artifacts, ["P02"])["counter"]["review"])
    # Scope union uses findings too; the submission validator still owns exact
    # source/quote checks. Do not invent a semantic judgment in this fixture.
    from types import SimpleNamespace
    review.findings = [SimpleNamespace(paper_id="P01")]
    assert review_assessment_scope(review, artifacts, confirmation=context) == {"P01", "P02"}


def test_incomplete_peer_is_not_silently_accepted():
    artifacts = artifact_fixture()
    result = bundle(artifacts, ["P02"])
    result["counter"]["status"] = "review_incomplete"
    with pytest.raises(ValueError, match="research_review_incomplete_no_silent_convergence"):
        responsible_author_feedback(result, artifacts,
            confirmation={"findings_to_confirm": {"P02": []}})
