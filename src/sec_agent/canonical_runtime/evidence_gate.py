from __future__ import annotations

from typing import Literal

from pydantic import Field

from .candidate_bundle import CandidateBundle, CandidateMetadata
from .evidence_request import EvidenceRequest
from .models import StrictModel, canonical_digest
from .parser_numeric import NormalizedNumericFact, NumericProgramTrace, ParserCandidate


class EvidenceGateError(ValueError):
    """Raised when a non-authoritative M6.6 fixture decision is used as formal evidence."""


FixtureDecision = Literal["fixture_accepted_for_gate_simulation", "context_only", "rejected", "typed_gap", "commercial_gap"]


class EvidenceGatePolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    minimum_source_authority_rank_by_evidence_role: dict[str, int]


class SemanticClassificationSuggestion(StrictModel):
    suggestion: str = Field(min_length=1)
    rationale_ref: str = Field(min_length=1)
    source: str = "fixture_rule_only"
    override_authority: bool = False


class EvidencePromotionDecision(StrictModel):
    decision_id: str = Field(min_length=1)
    decision_digest: str = Field(min_length=1)
    decision: FixtureDecision
    decision_scope: Literal["deterministic_fixture_only"] = "deterministic_fixture_only"
    runtime_promotion_authorized: Literal[False] = False
    writer_citable: Literal[False] = False
    domain_judgment_eligible: Literal[False] = False
    persistence_authorized: Literal[False] = False
    lead_human_status: Literal["approval_required_not_executed"] = "approval_required_not_executed"
    evidence_request_id: str = Field(min_length=1)
    evidence_request_digest: str = Field(min_length=1)
    candidate_bundle_id: str = Field(min_length=1)
    candidate_bundle_digest: str = Field(min_length=1)
    parser_candidate_id: str | None = None
    parser_candidate_digest: str | None = None
    normalized_fact_id: str | None = None
    normalized_fact_digest: str | None = None
    numeric_trace_id: str | None = None
    numeric_trace_digest: str | None = None
    hard_failure_codes: tuple[str, ...] = ()
    typed_gap_codes: tuple[str, ...] = ()
    conflict_candidate_ids: tuple[str, ...] = ()
    classification_suggestion: SemanticClassificationSuggestion | None = None
    fixture_only: Literal[True] = True


class EvidenceGateResult(StrictModel):
    status: str
    decision: EvidencePromotionDecision
    model_call_count: int = 0
    external_call_count: int = 0
    tool_invocation_count: int = 0
    store_write_count: int = 0


class FixtureEvidenceGate:
    """M6.6 hard-rule simulator. It emits only non-authoritative fixture decisions."""

    def __init__(self, *, policy: EvidenceGatePolicy):
        self.policy = policy

    @staticmethod
    def _candidate(bundle: CandidateBundle, candidate_id: str | None) -> CandidateMetadata | None:
        return next((item for item in bundle.candidates if item.candidate_id == candidate_id), None)

    def _decision(
        self,
        *,
        request: EvidenceRequest,
        bundle: CandidateBundle,
        decision: FixtureDecision,
        parser_candidate: ParserCandidate | None = None,
        fact: NormalizedNumericFact | None = None,
        trace: NumericProgramTrace | None = None,
        hard_failure_codes: tuple[str, ...] = (),
        typed_gap_codes: tuple[str, ...] = (),
        conflict_candidate_ids: tuple[str, ...] = (),
        suggestion: SemanticClassificationSuggestion | None = None,
    ) -> EvidenceGateResult:
        payload = {
            "decision": decision, "decision_scope": "deterministic_fixture_only", "runtime_promotion_authorized": False, "writer_citable": False, "domain_judgment_eligible": False, "persistence_authorized": False, "lead_human_status": "approval_required_not_executed",
            "evidence_request_id": request.request_id, "evidence_request_digest": request.request_digest, "candidate_bundle_id": bundle.bundle_id, "candidate_bundle_digest": bundle.bundle_digest,
            "parser_candidate_id": parser_candidate.parser_candidate_id if parser_candidate else None, "parser_candidate_digest": parser_candidate.parser_candidate_digest if parser_candidate else None,
            "normalized_fact_id": fact.normalized_fact_id if fact else None, "normalized_fact_digest": fact.normalized_fact_digest if fact else None,
            "numeric_trace_id": trace.numeric_trace_id if trace else None, "numeric_trace_digest": trace.trace_digest if trace else None,
            "hard_failure_codes": tuple(sorted(set(hard_failure_codes))), "typed_gap_codes": tuple(sorted(set(typed_gap_codes))), "conflict_candidate_ids": tuple(sorted(set(conflict_candidate_ids))),
            "classification_suggestion": suggestion.model_dump(mode="json") if suggestion else None, "fixture_only": True,
        }
        digest = canonical_digest(payload)
        return EvidenceGateResult(status="pass", decision=EvidencePromotionDecision(decision_id=f"evidence_gate_decision_{digest[:20]}", decision_digest=digest, **payload))

    def evaluate(
        self,
        *,
        request: EvidenceRequest,
        bundle: CandidateBundle,
        parser_candidate: ParserCandidate | None = None,
        fact: NormalizedNumericFact | None = None,
        trace: NumericProgramTrace | None = None,
        suggestion: SemanticClassificationSuggestion | None = None,
    ) -> EvidenceGateResult:
        if suggestion and suggestion.override_authority:
            raise EvidenceGateError("semantic_suggestion_must_not_claim_override_authority")
        if request.execution_admission != "not_admitted" or bundle.execution_admission != "not_admitted" or bundle.persistence_admission != "not_admitted":
            raise EvidenceGateError("fixture_gate_inputs_must_be_not_admitted")
        if bundle.request_id != request.request_id or bundle.request_digest != request.request_digest:
            return self._decision(request=request, bundle=bundle, decision="rejected", hard_failure_codes=("candidate_bundle_request_digest_mismatch",), suggestion=suggestion)
        if request.accepted_evidence_role == "gap_evidence" or bundle.status == "not_attempted_typed_stop":
            return self._decision(request=request, bundle=bundle, decision="commercial_gap", typed_gap_codes=bundle.typed_gap_codes or ("commercial_gap_stop_rule",), suggestion=suggestion)
        if bundle.status == "retrieval_exhausted":
            return self._decision(request=request, bundle=bundle, decision="typed_gap", typed_gap_codes=bundle.typed_gap_codes or ("retrieval_exhausted",), suggestion=suggestion)
        if bundle.status != "metadata_fixture_compiled":
            return self._decision(request=request, bundle=bundle, decision="rejected", hard_failure_codes=("candidate_bundle_not_fixture_compiled",), suggestion=suggestion)
        conflicts = tuple(sorted({item.candidate_id for item in bundle.candidates if item.candidate_kind == "table_context" and sum(other.candidate_kind == "table_context" and other.document_id != item.document_id for other in bundle.candidates) > 0}))
        if conflicts:
            return self._decision(request=request, bundle=bundle, decision="typed_gap", conflict_candidate_ids=conflicts, typed_gap_codes=("candidate_conflict_unresolved",), suggestion=suggestion)
        if request.accepted_evidence_role == "context":
            if any(value is not None for value in (parser_candidate, fact, trace)):
                return self._decision(request=request, bundle=bundle, decision="rejected", hard_failure_codes=("relationship_context_cannot_be_promoted_as_fact",), suggestion=suggestion)
            return self._decision(request=request, bundle=bundle, decision="context_only", suggestion=suggestion)
        failures: list[str] = []
        if not all((parser_candidate, fact, trace)):
            failures.append("numeric_program_trace_required")
        else:
            assert parser_candidate and fact and trace
            candidate = self._candidate(bundle, parser_candidate.candidate_id)
            if not parser_candidate.fixture_only or parser_candidate.parse_status != "parsed_unpromoted" or fact.promotion_status != "unpromoted" or trace.promotion_status != "unpromoted": failures.append("fixture_only_unpromoted_required")
            if parser_candidate.candidate_bundle_id != bundle.bundle_id or parser_candidate.candidate_bundle_digest != bundle.bundle_digest: failures.append("parser_candidate_bundle_digest_mismatch")
            if fact.parser_candidate_id != parser_candidate.parser_candidate_id or fact.parser_candidate_digest != parser_candidate.parser_candidate_digest: failures.append("normalized_fact_parser_digest_mismatch")
            if trace.normalized_fact_id != fact.normalized_fact_id or trace.normalized_fact_digest != fact.normalized_fact_digest: failures.append("numeric_trace_fact_digest_mismatch")
            if candidate is None: failures.append("parser_candidate_not_in_bundle")
            else:
                minimum = self.policy.minimum_source_authority_rank_by_evidence_role.get(request.accepted_evidence_role, 999)
                if candidate.entity_ref not in request.target_entities: failures.append("entity_mismatch")
                if fact.period not in request.target_periods or fact.period != candidate.period_ref: failures.append("period_mismatch")
                if request.unit and fact.unit != request.unit: failures.append("unit_mismatch")
                if fact.scale_multiplier <= 0: failures.append("scale_mismatch")
                if candidate.source_authority_rank < minimum: failures.append("source_authority_below_minimum")
                if not fact.source_coordinate.startswith(candidate.section_or_table_ref): failures.append("source_coordinate_mismatch")
                if "relationship_graph_only" in request.forbidden_substitutions and candidate.source_role == "relationship_graph": failures.append("forbidden_substitution_relationship_graph_only")
        return self._decision(request=request, bundle=bundle, decision="rejected" if failures else "fixture_accepted_for_gate_simulation", parser_candidate=parser_candidate, fact=fact, trace=trace, hard_failure_codes=tuple(failures), suggestion=suggestion)


def reject_formal_evidence_consumer(*, decision: EvidencePromotionDecision, consumer: str) -> None:
    """Explicit consumer firewall for M6.7/Writer until a separately admitted real promotion exists."""
    if consumer not in {"writer", "domain_judgment", "context_injection"}:
        raise EvidenceGateError("fixture_decision_consumer_not_allowed")
    raise EvidenceGateError(f"fixture_evidence_promotion_decision_not_consumable:{consumer}")
