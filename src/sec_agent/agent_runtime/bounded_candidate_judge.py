"""Strict contracts for one bounded local-retrieval candidate judge.

This module deliberately owns no retrieval, provider transport, retry loop, or
Evidence authority.  It validates an answer-free projection of two local
candidate sets and a candidate-only JSON decision returned by one model call.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


INPUT_SCHEMA_VERSION = "fin_ia_dell_bounded_candidate_judge_input_v1_0"
OUTPUT_SCHEMA_VERSION = "fin_ia_dell_bounded_candidate_judge_output_v1_0"

BANNED_QREL_INPUT_KEYS = frozenset(
    {
        "gold_node_ids",
        "hard_negative_node_ids",
        "partial_node_ids",
        "derivable_node_ids",
        "acceptable_alternate_node_ids",
        "direct_alternate_node_ids",
        "must_match",
    }
)


class BoundedCandidateJudgeError(ValueError):
    """Fail-closed input or output contract boundary."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )


class RequirementSpec(_StrictModel):
    requirement_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    description: str = Field(min_length=1, max_length=240)


class LocalCandidate(_StrictModel):
    node_id: str = Field(min_length=1, max_length=160)
    retrieval_rank: int = Field(ge=1, le=6)
    node_kind: Literal["chunk", "mixed_prose_span", "table"]
    issuer_id: str = Field(min_length=1, max_length=32)
    fiscal_period: str = Field(min_length=1, max_length=32)
    route_id: str = Field(min_length=1, max_length=160)
    source_role: str = Field(min_length=1, max_length=160)
    publication_date: str = Field(min_length=1, max_length=32)
    period_end: str | None = Field(default=None, max_length=32)
    section_path: tuple[str, ...] = Field(default=(), max_length=16)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    stable_url: str = Field(min_length=1, max_length=2_048)
    content: str = Field(min_length=1, max_length=12_000)
    candidate_is_not_evidence: Literal[True]
    citation_eligible: Literal[False]
    numeric_authority: Literal[False]

    @model_validator(mode="after")
    def validate_page_range(self) -> "LocalCandidate":
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_start > self.page_end
        ):
            raise ValueError("candidate_page_range_inverted")
        return self


class CandidateJudgeCase(_StrictModel):
    query_id: str = Field(min_length=1, max_length=120)
    question_zh: str = Field(min_length=1, max_length=1_000)
    retrieval_query_en: str = Field(min_length=1, max_length=1_000)
    issuer_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    fiscal_periods: tuple[str, ...] = Field(min_length=1, max_length=4)
    source_roles: tuple[str, ...] = Field(min_length=1, max_length=4)
    route_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    requirements: tuple[RequirementSpec, ...] = Field(min_length=1, max_length=8)
    candidates: tuple[LocalCandidate, ...] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def validate_case_identity(self) -> "CandidateJudgeCase":
        requirement_ids = [row.requirement_id for row in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("candidate_judge_requirement_id_duplicate")
        candidate_ids = [row.node_id for row in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_judge_candidate_id_duplicate")
        if [row.retrieval_rank for row in self.candidates] != list(range(1, 7)):
            raise ValueError("candidate_judge_candidate_rank_sequence_invalid")
        for candidate in self.candidates:
            if (
                candidate.issuer_id not in self.issuer_ids
                or candidate.fiscal_period not in self.fiscal_periods
                or candidate.source_role not in self.source_roles
                or candidate.route_id not in self.route_ids
            ):
                raise ValueError("candidate_judge_candidate_scope_mismatch")
        return self


class CandidateJudgeInput(_StrictModel):
    schema_version: Literal[
        "fin_ia_dell_bounded_candidate_judge_input_v1_0"
    ]
    task: Literal["select_minimal_sufficient_local_candidates"]
    candidate_authority: Literal["candidate_only_not_evidence"]
    external_knowledge_allowed: Literal[False]
    cases: tuple[CandidateJudgeCase, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_query_identity(self) -> "CandidateJudgeInput":
        query_ids = [row.query_id for row in self.cases]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("candidate_judge_query_id_duplicate")
        all_candidate_ids = [
            candidate.node_id for case in self.cases for candidate in case.candidates
        ]
        if len(all_candidate_ids) != len(set(all_candidate_ids)):
            raise ValueError("candidate_judge_cross_query_candidate_overlap")
        return self


CandidateVerdict = Literal[
    "full_support",
    "partial_support",
    "wrong_period_or_outlook",
    "irrelevant",
    "ambiguous",
]


class CandidateAssessment(_StrictModel):
    node_id: str = Field(min_length=1, max_length=160)
    verdict: CandidateVerdict
    covered_requirement_ids: tuple[str, ...] = Field(default=(), max_length=8)


class RequirementCoverage(_StrictModel):
    requirement_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    supporting_node_ids: tuple[str, ...] = Field(min_length=1, max_length=2)


class QueryJudgment(_StrictModel):
    query_id: str = Field(min_length=1, max_length=120)
    decision: Literal["select", "abstain"]
    candidate_assessments: tuple[CandidateAssessment, ...] = Field(
        min_length=6, max_length=6
    )
    selected_node_ids: tuple[str, ...] = Field(default=(), max_length=2)
    requirement_coverage: tuple[RequirementCoverage, ...] = Field(
        default=(), max_length=8
    )
    confidence: Literal["low", "medium", "high"]
    rationale: str = Field(min_length=1, max_length=500)


class CandidateJudgeOutput(_StrictModel):
    schema_version: Literal[
        "fin_ia_dell_bounded_candidate_judge_output_v1_0"
    ]
    judgments: tuple[QueryJudgment, ...] = Field(min_length=2, max_length=2)


def _json_round_trip(value: Any, *, code: str) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise BoundedCandidateJudgeError(code) from exc


def find_banned_qrel_input_keys(value: Any) -> tuple[str, ...]:
    """Return banned evaluation-only keys without inspecting text substrings."""

    findings: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                normalized = str(key).casefold()
                if normalized in BANNED_QREL_INPUT_KEYS:
                    findings.add(normalized)
                visit(child)
        elif isinstance(item, Sequence) and not isinstance(
            item, (str, bytes, bytearray)
        ):
            for child in item:
                visit(child)

    visit(value)
    return tuple(sorted(findings))


def validate_candidate_judge_input(value: Any) -> CandidateJudgeInput:
    if find_banned_qrel_input_keys(value):
        raise BoundedCandidateJudgeError("candidate_judge_qrel_label_leakage")
    try:
        return CandidateJudgeInput.model_validate_json(
            _json_round_trip(value, code="candidate_judge_input_not_json")
        )
    except (ValidationError, ValueError) as exc:
        raise BoundedCandidateJudgeError("candidate_judge_input_invalid") from exc


def validate_candidate_judge_output(
    value: Any,
    *,
    model_input: CandidateJudgeInput,
) -> CandidateJudgeOutput:
    """Validate strict JSON plus query/candidate/requirement dynamic bindings."""

    try:
        parsed = CandidateJudgeOutput.model_validate_json(
            _json_round_trip(value, code="candidate_judge_output_not_json")
        )
    except (ValidationError, ValueError) as exc:
        raise BoundedCandidateJudgeError("candidate_judge_output_invalid") from exc

    case_by_query = {case.query_id: case for case in model_input.cases}
    judgments = {row.query_id: row for row in parsed.judgments}
    if len(judgments) != len(parsed.judgments) or set(judgments) != set(case_by_query):
        raise BoundedCandidateJudgeError("candidate_judge_output_query_set_invalid")

    for query_id, case in case_by_query.items():
        judgment = judgments[query_id]
        candidate_ids = {row.node_id for row in case.candidates}
        requirement_ids = {row.requirement_id for row in case.requirements}
        assessments = {row.node_id: row for row in judgment.candidate_assessments}
        if (
            len(assessments) != len(judgment.candidate_assessments)
            or set(assessments) != candidate_ids
        ):
            raise BoundedCandidateJudgeError(
                "candidate_judge_assessment_candidate_set_invalid"
            )
        for assessment in assessments.values():
            covered = set(assessment.covered_requirement_ids)
            if (
                len(covered) != len(assessment.covered_requirement_ids)
                or not covered.issubset(requirement_ids)
            ):
                raise BoundedCandidateJudgeError(
                    "candidate_judge_assessment_requirement_set_invalid"
                )
            if assessment.verdict == "full_support" and covered != requirement_ids:
                raise BoundedCandidateJudgeError(
                    "candidate_judge_full_support_coverage_invalid"
                )
            if assessment.verdict == "partial_support" and (
                not covered or covered == requirement_ids
            ):
                raise BoundedCandidateJudgeError(
                    "candidate_judge_partial_support_coverage_invalid"
                )
            if assessment.verdict not in {"full_support", "partial_support"} and covered:
                raise BoundedCandidateJudgeError(
                    "candidate_judge_non_support_coverage_invalid"
                )

        selected = tuple(judgment.selected_node_ids)
        if len(selected) != len(set(selected)) or not set(selected).issubset(
            candidate_ids
        ):
            raise BoundedCandidateJudgeError(
                "candidate_judge_selected_candidate_set_invalid"
            )
        coverage_by_requirement = {
            row.requirement_id: row for row in judgment.requirement_coverage
        }
        if len(coverage_by_requirement) != len(judgment.requirement_coverage):
            raise BoundedCandidateJudgeError(
                "candidate_judge_requirement_coverage_duplicate"
            )

        if judgment.decision == "abstain":
            if selected or judgment.requirement_coverage:
                raise BoundedCandidateJudgeError(
                    "candidate_judge_abstain_payload_invalid"
                )
            if any(
                row.verdict == "full_support" for row in assessments.values()
            ):
                raise BoundedCandidateJudgeError(
                    "candidate_judge_abstain_full_support_conflict"
                )
            continue

        if not selected or set(coverage_by_requirement) != requirement_ids:
            raise BoundedCandidateJudgeError(
                "candidate_judge_selected_requirement_coverage_incomplete"
            )
        selected_set = set(selected)
        for node_id in selected:
            if assessments[node_id].verdict not in {
                "full_support",
                "partial_support",
            }:
                raise BoundedCandidateJudgeError(
                    "candidate_judge_selected_candidate_verdict_invalid"
                )
        for requirement_id, coverage in coverage_by_requirement.items():
            support_ids = tuple(coverage.supporting_node_ids)
            if (
                len(support_ids) != len(set(support_ids))
                or not set(support_ids).issubset(selected_set)
                or any(
                    requirement_id
                    not in assessments[node_id].covered_requirement_ids
                    for node_id in support_ids
                )
            ):
                raise BoundedCandidateJudgeError(
                    "candidate_judge_supporting_candidate_binding_invalid"
                )

    return parsed


def build_candidate_judge_messages(
    model_input: CandidateJudgeInput,
) -> tuple[dict[str, str], dict[str, str]]:
    """Compile one single-turn JSON request with no evaluation labels."""

    system = (
        "You are a bounded local-retrieval candidate judge. Return one JSON object "
        "only, using schema_version fin_ia_dell_bounded_candidate_judge_output_v1_0. "
        "Use only the supplied candidate text and metadata; do not use external "
        "knowledge and do not answer the research questions. Assess every candidate. "
        "Prefer the smallest, least-confounded set that directly supports every "
        "required field. Distinguish actual results from outlook, the requested period "
        "from nearby periods, and full support from partial support. A mixed passage "
        "may be selected only when its exact actual-results span is unambiguous; prefer "
        "a cleaner direct passage when available. If the candidates cannot support all "
        "requirements, abstain. Candidate selection is advisory and never Evidence. "
        "Each judgment must contain exactly six candidate_assessments. For select, "
        "selected_node_ids must contain one or two supplied IDs and requirement_coverage "
        "must cover every supplied requirement. For abstain, both arrays must be empty. "
        "Valid verdicts are full_support, partial_support, wrong_period_or_outlook, "
        "irrelevant, and ambiguous. Valid confidence values are low, medium, and high."
    )
    user_payload = model_input.model_dump(mode="json")
    if find_banned_qrel_input_keys(user_payload):
        raise BoundedCandidateJudgeError("candidate_judge_qrel_label_leakage")
    user = json.dumps(
        user_payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    )


__all__ = [
    "BANNED_QREL_INPUT_KEYS",
    "BoundedCandidateJudgeError",
    "CandidateJudgeInput",
    "CandidateJudgeOutput",
    "INPUT_SCHEMA_VERSION",
    "OUTPUT_SCHEMA_VERSION",
    "build_candidate_judge_messages",
    "find_banned_qrel_input_keys",
    "validate_candidate_judge_input",
    "validate_candidate_judge_output",
]
