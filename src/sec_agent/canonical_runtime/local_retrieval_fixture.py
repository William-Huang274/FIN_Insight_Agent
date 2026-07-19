"""M6.3R.2 sanitized, immutable local-retrieval fixture harness.

The module evaluates supplied metadata fixtures only.  It intentionally has
no adapter, index, graph, SQL, source, receipt-store, network, model, parser,
promotion or canonical-store dependency.  Expected outcomes live in the
separate oracle module: this evaluator cannot read them while producing an
actual result.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from pydantic import Field, ValidationError, model_validator

from .local_retrieval_skeleton import (
    CandidateBundleProjection,
    DeterministicRerankDecision,
    EvidenceGateCandidateProjection,
    ExactValueSqlBindingPolicy,
    LocalRecallCandidate,
    LocalRetrievalQuery,
    SHA256_PATTERN,
)
from .models import StrictModel, canonical_digest


class LocalRetrievalFixtureError(ValueError):
    """Raised for an invalid fixture contract, never for a source runtime."""


def _require_owned_identity(*, identifier: str, digest: str, prefix: str, payload: dict[str, Any]) -> None:
    expected_digest = canonical_digest(payload)
    if digest != expected_digest:
        raise ValueError("owned_fixture_contract_digest_mismatch")
    if identifier != f"{prefix}_{expected_digest[:20]}":
        raise ValueError("owned_fixture_contract_id_mismatch")


class SqlFixturePolicyPin(StrictModel):
    """The only policy artifact that an R.2 SQL fixture can be admitted against."""

    policy_path: str = Field(min_length=1)
    policy_ref: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    policy_canonical_digest: str = Field(pattern=SHA256_PATTERN)
    policy_raw_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_read_status: Literal["registry_not_read"] = "registry_not_read"
    execution_admission: Literal["not_admitted"] = "not_admitted"


class LocalRetrievalFixtureAdmissionPolicy(StrictModel):
    """Create-owned R.2 admission policy for sanitized, non-executing fixtures."""

    policy_ref: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    policy_digest: str = Field(pattern=SHA256_PATTERN)
    sql_fixture_policy_pin: SqlFixturePolicyPin
    max_candidates_per_source_artifact: Literal[2] = 2
    max_candidates_per_identical_content_digest: Literal[1] = 1
    max_neighbor_expansions_total: Literal[32] = 32
    diversity_selection_policy: Literal["first_pass_per_source_family_then_ranked_fill"] = "first_pass_per_source_family_then_ranked_fill"
    fixture_provenance: Literal["sanitized_immutable_fixture_only"] = "sanitized_immutable_fixture_only"
    execution_admission: Literal["not_admitted"] = "not_admitted"
    persistence_authorized: Literal[False] = False
    promotion_authorized: Literal[False] = False
    writer_citable: Literal[False] = False
    domain_judgment_eligible: Literal[False] = False

    @model_validator(mode="after")
    def require_recomputed_digest(self) -> "LocalRetrievalFixtureAdmissionPolicy":
        payload = self.model_dump(mode="json", exclude={"policy_digest"})
        if self.policy_digest != canonical_digest(payload):
            raise ValueError("local_retrieval_fixture_admission_policy_digest_mismatch")
        return self

    @classmethod
    def create(cls, *, policy_ref: str, policy_version: str, sql_fixture_policy_pin: SqlFixturePolicyPin) -> "LocalRetrievalFixtureAdmissionPolicy":
        payload = {
            "policy_ref": policy_ref,
            "policy_version": policy_version,
            "sql_fixture_policy_pin": sql_fixture_policy_pin.model_dump(mode="json"),
            "max_candidates_per_source_artifact": 2,
            "max_candidates_per_identical_content_digest": 1,
            "max_neighbor_expansions_total": 32,
            "diversity_selection_policy": "first_pass_per_source_family_then_ranked_fill",
            "fixture_provenance": "sanitized_immutable_fixture_only",
            "execution_admission": "not_admitted",
            "persistence_authorized": False,
            "promotion_authorized": False,
            "writer_citable": False,
            "domain_judgment_eligible": False,
        }
        return cls(policy_digest=canonical_digest(payload), **payload)


class FixtureNeighborReference(StrictModel):
    """Declared, non-dereferencing neighbor relation with explicit requiredness."""

    seed_candidate_id: str = Field(min_length=1)
    neighbor_candidate_id: str = Field(min_length=1)
    relation: Literal[
        "previous_section",
        "next_section",
        "parent_section",
        "table",
        "previous_page",
        "next_page",
        "previous_row",
        "next_row",
    ]
    expected_coordinate_ref: str = Field(min_length=1)
    required: bool = True


class LocalRetrievalFixtureEntry(StrictModel):
    """One fully supplied fixture request/query/candidate slice.

    Expected outcomes intentionally do not appear here.  This is evaluator
    input, not a self-asserting oracle.
    """

    fixture_id: str = Field(min_length=1)
    fixture_kind: Literal[
        "bm25_narrative",
        "object_bm25_document_table",
        "relationship_graph",
        "exact_value_sql_row",
        "typed_exhaustion",
    ]
    fixture_provenance: Literal["sanitized_immutable_fixture_only"] = "sanitized_immutable_fixture_only"
    request_id: str = Field(min_length=1)
    request_digest: str = Field(pattern=SHA256_PATTERN)
    topk_policy_audit_digest: str = Field(pattern=SHA256_PATTERN)
    topk_registry_digest: str = Field(pattern=SHA256_PATTERN)
    adapter_snapshot_id: str = Field(min_length=1)
    adapter_snapshot_digest: str = Field(pattern=SHA256_PATTERN)
    query: LocalRetrievalQuery
    candidates: tuple[LocalRecallCandidate, ...] = ()
    required_candidate_kinds: tuple[str, ...] = ()
    neighbor_references: tuple[FixtureNeighborReference, ...] = ()
    sql_policy_pin: SqlFixturePolicyPin | None = None
    execution_admission: Literal["not_admitted"] = "not_admitted"
    persistence_authorized: Literal[False] = False
    promotion_authorized: Literal[False] = False
    writer_citable: Literal[False] = False
    domain_judgment_eligible: Literal[False] = False

    @model_validator(mode="after")
    def require_exact_query_binding(self) -> "LocalRetrievalFixtureEntry":
        if (
            self.request_id,
            self.request_digest,
            self.topk_policy_audit_digest,
            self.topk_registry_digest,
            self.adapter_snapshot_id,
            self.adapter_snapshot_digest,
        ) != (
            self.query.request_id,
            self.query.request_digest,
            self.query.topk_audit.audit_digest,
            self.query.topk_audit.request.policy_registry_digest,
            self.query.adapter_snapshot.snapshot_id,
            self.query.adapter_snapshot.snapshot_digest,
        ):
            raise ValueError("fixture_entry_request_topk_or_snapshot_unbound")
        if self.fixture_kind == "exact_value_sql_row":
            if self.query.adapter_snapshot.adapter_kind != "exact_value_sql" or self.sql_policy_pin is None:
                raise ValueError("exact_value_sql_fixture_requires_exact_query_and_policy_pin")
        elif self.sql_policy_pin is not None:
            raise ValueError("sql_policy_pin_only_allowed_for_exact_value_sql_fixture")
        if any(candidate.candidate_provenance != "fixture_supplied_not_retrieved" for candidate in self.candidates):
            raise ValueError("fixture_candidate_provenance_must_be_explicit")
        if not set(self.required_candidate_kinds).issubset(set(self.query.eligible_candidate_kinds)):
            raise ValueError("fixture_required_candidate_kind_not_eligible_for_query")
        return self


class LocalRetrievalFixtureCorpus(StrictModel):
    """Create-owned immutable corpus package; it contains no source bytes."""

    corpus_id: str = Field(min_length=1)
    corpus_digest: str = Field(pattern=SHA256_PATTERN)
    admission_policy: LocalRetrievalFixtureAdmissionPolicy
    entries: tuple[LocalRetrievalFixtureEntry, ...] = Field(min_length=1)
    corpus_provenance: Literal["sanitized_immutable_fixture_only"] = "sanitized_immutable_fixture_only"
    execution_admission: Literal["not_admitted"] = "not_admitted"
    persistence_authorized: Literal[False] = False

    @model_validator(mode="after")
    def require_recomputed_digest_and_unique_fixture_ids(self) -> "LocalRetrievalFixtureCorpus":
        if len({entry.fixture_id for entry in self.entries}) != len(self.entries):
            raise ValueError("fixture_corpus_duplicate_fixture_id")
        payload = self.model_dump(mode="json", exclude={"corpus_id", "corpus_digest"})
        _require_owned_identity(identifier=self.corpus_id, digest=self.corpus_digest, prefix="local_retrieval_fixture_corpus", payload=payload)
        return self

    @classmethod
    def create(cls, *, admission_policy: LocalRetrievalFixtureAdmissionPolicy, entries: tuple[LocalRetrievalFixtureEntry, ...]) -> "LocalRetrievalFixtureCorpus":
        payload = {
            "admission_policy": admission_policy.model_dump(mode="json"),
            "entries": [entry.model_dump(mode="json") for entry in entries],
            "corpus_provenance": "sanitized_immutable_fixture_only",
            "execution_admission": "not_admitted",
            "persistence_authorized": False,
        }
        digest = canonical_digest(payload)
        return cls(corpus_id=f"local_retrieval_fixture_corpus_{digest[:20]}", corpus_digest=digest, **payload)


class FixtureCandidateOutcome(StrictModel):
    candidate_id: str = Field(min_length=1)
    status: Literal["accepted", "metadata_rejected", "duplicate_rejected", "capacity_rejected"]
    reason: str = Field(min_length=1)


class FixtureDiversityDecision(StrictModel):
    """Records actual first-pass/fill-pass selection over the eligible pool."""

    eligible_source_families: tuple[str, ...] = ()
    diversity_applicable: bool
    selection_policy: Literal["first_pass_per_source_family_then_ranked_fill", "not_applicable"]
    first_pass_candidate_ids: tuple[str, ...] = ()
    selected_candidate_ids: tuple[str, ...] = ()


class FixtureNeighborOutcome(StrictModel):
    reference: FixtureNeighborReference
    status: Literal["validated", "typed_exhaustion"]
    reason: str = Field(min_length=1)
    seed_coordinate_field: str = Field(min_length=1)
    seed_coordinate_ref: str | None = None
    neighbor_coordinate_ref: str | None = None
    lineage_match: bool


class LocalRetrievalFixtureEvaluation(StrictModel):
    """Create-owned result, still explicitly non-authoritative and nonpersistent."""

    evaluation_id: str = Field(min_length=1)
    evaluation_digest: str = Field(pattern=SHA256_PATTERN)
    fixture_id: str = Field(min_length=1)
    fixture_digest: str = Field(pattern=SHA256_PATTERN)
    status: Literal["accepted_fixture_projection", "typed_exhaustion", "not_fixture_admitted"]
    reasons: tuple[str, ...] = Field(min_length=1)
    candidate_outcomes: tuple[FixtureCandidateOutcome, ...] = ()
    diversity_decision: FixtureDiversityDecision | None = None
    rerank_decisions: tuple[DeterministicRerankDecision, ...] = ()
    rerank_top_candidate_ids: tuple[str, ...] = ()
    rerank_to_gate_set_preserved: bool = False
    neighbor_outcomes: tuple[FixtureNeighborOutcome, ...] = ()
    candidate_bundle_projection: CandidateBundleProjection | None = None
    evidence_gate_candidate_projection: EvidenceGateCandidateProjection | None = None
    adapter_execution_count: Literal[0] = 0
    network_request_count: Literal[0] = 0
    external_tool_call_count: Literal[0] = 0
    tool_invocation_count: Literal[0] = 0
    model_call_count: Literal[0] = 0
    provider_call_count: Literal[0] = 0
    canonical_store_write_count: Literal[0] = 0
    evidence_promotion_count: Literal[0] = 0
    parser_numeric_execution_count: Literal[0] = 0
    sourcehunter_attempt_count: Literal[0] = 0
    execution_admission: Literal["not_admitted"] = "not_admitted"
    persistence_authorized: Literal[False] = False
    promotion_authorized: Literal[False] = False
    writer_citable: Literal[False] = False
    domain_judgment_eligible: Literal[False] = False

    @model_validator(mode="after")
    def require_consistent_terminal_state_and_recomputed_digest(self) -> "LocalRetrievalFixtureEvaluation":
        if self.status == "accepted_fixture_projection":
            if self.candidate_bundle_projection is None or self.evidence_gate_candidate_projection is None or self.diversity_decision is None:
                raise ValueError("accepted_fixture_evaluation_requires_nonpromoted_projections_and_selection")
            gate_ids = self.evidence_gate_candidate_projection.candidate_ids
            expected_gate_set = set(self.rerank_top_candidate_ids[: self.evidence_gate_candidate_projection.evidence_gate_candidate_top_k])
            if set(gate_ids) != expected_gate_set:
                raise ValueError("fixture_gate_candidates_not_selected_from_rerank_top_n")
            if not self.rerank_to_gate_set_preserved:
                raise ValueError("fixture_rerank_to_gate_set_not_preserved")
            if set(self.diversity_decision.selected_candidate_ids) != {candidate.candidate_id for candidate in self.candidate_bundle_projection.candidates}:
                raise ValueError("fixture_diversity_selected_set_not_bound_to_bundle")
        elif self.candidate_bundle_projection is not None or self.evidence_gate_candidate_projection is not None:
            raise ValueError("terminal_fixture_evaluation_must_not_carry_projection")
        payload = self.model_dump(mode="json", exclude={"evaluation_id", "evaluation_digest"})
        _require_owned_identity(identifier=self.evaluation_id, digest=self.evaluation_digest, prefix="local_retrieval_fixture_evaluation", payload=payload)
        return self

    @classmethod
    def create(cls, **payload: Any) -> "LocalRetrievalFixtureEvaluation":
        complete_payload = {
            "candidate_outcomes": (),
            "diversity_decision": None,
            "rerank_decisions": (),
            "rerank_top_candidate_ids": (),
            "rerank_to_gate_set_preserved": False,
            "neighbor_outcomes": (),
            "candidate_bundle_projection": None,
            "evidence_gate_candidate_projection": None,
            "adapter_execution_count": 0,
            "network_request_count": 0,
            "external_tool_call_count": 0,
            "tool_invocation_count": 0,
            "model_call_count": 0,
            "provider_call_count": 0,
            "canonical_store_write_count": 0,
            "evidence_promotion_count": 0,
            "parser_numeric_execution_count": 0,
            "sourcehunter_attempt_count": 0,
            "execution_admission": "not_admitted",
            "persistence_authorized": False,
            "promotion_authorized": False,
            "writer_citable": False,
            "domain_judgment_eligible": False,
        }
        complete_payload.update(payload)
        draft = cls.model_construct(evaluation_id="", evaluation_digest="", **complete_payload)
        digest = canonical_digest(draft.model_dump(mode="json", exclude={"evaluation_id", "evaluation_digest"}))
        return cls(evaluation_id=f"local_retrieval_fixture_evaluation_{digest[:20]}", evaluation_digest=digest, **complete_payload)


class FixtureFailureClassifier:
    """Fixed classifier taxonomy.  It never reads fixture oracle data."""

    @staticmethod
    def no_metadata_candidate() -> str:
        return "retrieval_exhausted_no_metadata_match"

    @staticmethod
    def required_candidate_kind_missing(*, missing_kinds: tuple[str, ...]) -> str:
        if "table_context" in missing_kinds:
            return "table_context_missing"
        if "neighbor_section" in missing_kinds:
            return "boundary_context_missing"
        return "required_candidate_kind_missing"

    @staticmethod
    def required_neighbor_missing(*, relation: str) -> str:
        return "table_context_missing" if relation == "table" else "boundary_context_missing"


_RELATION_SEED_FIELD: dict[str, str] = {
    "previous_section": "previous_ref",
    "next_section": "next_ref",
    "parent_section": "parent_section_ref",
    "table": "section_or_table_ref",
    "previous_page": "previous_page_ref",
    "next_page": "next_page_ref",
    "previous_row": "previous_row_ref",
    "next_row": "next_row_ref",
}


class LocalRetrievalFixtureHarness:
    """Pure deterministic fixture evaluator; it never invokes an adapter or oracle."""

    def __init__(
        self,
        *,
        admission_policy: LocalRetrievalFixtureAdmissionPolicy,
        pinned_sql_policy: ExactValueSqlBindingPolicy,
        pinned_sql_policy_raw_sha256: str,
    ) -> None:
        self._admission_policy = admission_policy
        self._pinned_sql_policy = pinned_sql_policy
        self._pinned_sql_policy_raw_sha256 = pinned_sql_policy_raw_sha256

    def _sql_fixture_is_admitted(self, entry: LocalRetrievalFixtureEntry) -> bool:
        if entry.fixture_kind != "exact_value_sql_row":
            return True
        pin = entry.sql_policy_pin
        required = self._admission_policy.sql_fixture_policy_pin
        if pin is None or pin != required:
            return False
        if (
            self._pinned_sql_policy.policy_ref,
            self._pinned_sql_policy.policy_version,
            self._pinned_sql_policy.policy_digest,
            self._pinned_sql_policy_raw_sha256,
        ) != (
            required.policy_ref,
            required.policy_version,
            required.policy_canonical_digest,
            required.policy_raw_sha256,
        ):
            return False
        scope = entry.query.exact_value_execution_scope
        return scope is not None and scope.binding_policy.model_dump(mode="json") == self._pinned_sql_policy.model_dump(mode="json")

    @staticmethod
    def _candidate_is_metadata_eligible(*, candidate: LocalRecallCandidate, query: LocalRetrievalQuery) -> tuple[bool, str]:
        if candidate.content_digest is None:
            return False, "content_digest_missing"
        try:
            CandidateBundleProjection.create(query=query, candidates=(candidate,))
        except (ValidationError, ValueError):
            return False, "metadata_scope_or_lineage_mismatch"
        return True, "metadata_filter_pass"

    @staticmethod
    def _rank(candidates: tuple[LocalRecallCandidate, ...]) -> tuple[LocalRecallCandidate, ...]:
        return tuple(sorted(candidates, key=lambda item: (-item.source_authority_rank, -item.recall_score, item.metadata_rank, item.candidate_id)))

    @staticmethod
    def _fixture_digest(entry: LocalRetrievalFixtureEntry) -> str:
        return canonical_digest(entry.model_dump(mode="json"))

    def _deduplicate(
        self,
        *,
        eligible: tuple[LocalRecallCandidate, ...],
        outcomes: list[FixtureCandidateOutcome],
    ) -> tuple[LocalRecallCandidate, ...]:
        retained: list[LocalRecallCandidate] = []
        source_counts: Counter[str] = Counter()
        content_counts: Counter[str] = Counter()
        for candidate in self._rank(eligible):
            assert candidate.content_digest is not None
            if source_counts[candidate.source_artifact_digest] >= self._admission_policy.max_candidates_per_source_artifact:
                outcomes.append(FixtureCandidateOutcome(candidate_id=candidate.candidate_id, status="duplicate_rejected", reason="source_artifact_duplicate_cap"))
                continue
            if content_counts[candidate.content_digest] >= self._admission_policy.max_candidates_per_identical_content_digest:
                outcomes.append(FixtureCandidateOutcome(candidate_id=candidate.candidate_id, status="duplicate_rejected", reason="identical_content_duplicate_cap"))
                continue
            source_counts[candidate.source_artifact_digest] += 1
            content_counts[candidate.content_digest] += 1
            retained.append(candidate)
        return tuple(retained)

    def _select_with_diversity(
        self,
        *,
        eligible_pool_after_duplicate_filter: tuple[LocalRecallCandidate, ...],
        candidate_capacity: int,
        outcomes: list[FixtureCandidateOutcome],
    ) -> tuple[tuple[LocalRecallCandidate, ...], FixtureDiversityDecision]:
        ranked = self._rank(eligible_pool_after_duplicate_filter)
        families = tuple(dict.fromkeys(candidate.source_family for candidate in ranked))
        diversity_applies = candidate_capacity >= 2 and len(families) >= 2
        first_pass: list[LocalRecallCandidate] = []
        if diversity_applies:
            seen_families: set[str] = set()
            for candidate in ranked:
                if candidate.source_family not in seen_families and len(first_pass) < candidate_capacity:
                    seen_families.add(candidate.source_family)
                    first_pass.append(candidate)
        selected: list[LocalRecallCandidate] = list(first_pass)
        selected_ids = {candidate.candidate_id for candidate in selected}
        for candidate in ranked:
            if len(selected) >= candidate_capacity:
                break
            if candidate.candidate_id not in selected_ids:
                selected.append(candidate)
                selected_ids.add(candidate.candidate_id)
        for candidate in ranked:
            if candidate.candidate_id not in selected_ids:
                outcomes.append(FixtureCandidateOutcome(candidate_id=candidate.candidate_id, status="capacity_rejected", reason="candidate_bundle_capacity_rejected"))
        decision = FixtureDiversityDecision(
            eligible_source_families=families,
            diversity_applicable=diversity_applies,
            selection_policy="first_pass_per_source_family_then_ranked_fill" if diversity_applies else "not_applicable",
            first_pass_candidate_ids=tuple(candidate.candidate_id for candidate in first_pass),
            selected_candidate_ids=tuple(candidate.candidate_id for candidate in selected),
        )
        return tuple(selected), decision

    def _neighbor_outcomes(
        self,
        *,
        entry: LocalRetrievalFixtureEntry,
        selected: tuple[LocalRecallCandidate, ...],
    ) -> tuple[FixtureNeighborOutcome, ...]:
        selected_by_id = {candidate.candidate_id: candidate for candidate in selected}
        outcomes: list[FixtureNeighborOutcome] = []
        if len(entry.neighbor_references) > self._admission_policy.max_neighbor_expansions_total:
            raise LocalRetrievalFixtureError("fixture_neighbor_expansion_budget_exceeded")
        for reference in entry.neighbor_references:
            seed_field = _RELATION_SEED_FIELD[reference.relation]
            seed = selected_by_id.get(reference.seed_candidate_id)
            neighbor = selected_by_id.get(reference.neighbor_candidate_id)
            if seed is None:
                outcomes.append(
                    FixtureNeighborOutcome(
                        reference=reference,
                        status="typed_exhaustion",
                        reason="fixture_neighbor_seed_not_selected",
                        seed_coordinate_field=seed_field,
                        lineage_match=False,
                    )
                )
                continue
            seed_coordinate = getattr(seed, seed_field)
            if neighbor is None:
                outcomes.append(
                    FixtureNeighborOutcome(
                        reference=reference,
                        status="typed_exhaustion",
                        reason="fixture_neighbor_not_selected",
                        seed_coordinate_field=seed_field,
                        seed_coordinate_ref=seed_coordinate,
                        lineage_match=False,
                    )
                )
                continue
            lineage_match = (
                seed.document_id,
                seed.document_version,
                seed.source_artifact_ref,
                seed.source_artifact_digest,
                seed.parser_artifact_ref,
                seed.parser_artifact_digest,
                seed.adapter_snapshot_id,
                seed.adapter_snapshot_digest,
            ) == (
                neighbor.document_id,
                neighbor.document_version,
                neighbor.source_artifact_ref,
                neighbor.source_artifact_digest,
                neighbor.parser_artifact_ref,
                neighbor.parser_artifact_digest,
                neighbor.adapter_snapshot_id,
                neighbor.adapter_snapshot_digest,
            )
            neighbor_coordinate = neighbor.section_or_table_ref
            if not lineage_match:
                reason = "fixture_neighbor_lineage_mismatch"
            elif seed_coordinate != reference.expected_coordinate_ref or neighbor_coordinate != reference.expected_coordinate_ref:
                reason = "fixture_neighbor_relation_coordinate_mismatch"
            else:
                reason = "fixture_neighbor_relation_lineage_bound"
            outcomes.append(
                FixtureNeighborOutcome(
                    reference=reference,
                    status="validated" if reason == "fixture_neighbor_relation_lineage_bound" else "typed_exhaustion",
                    reason=reason,
                    seed_coordinate_field=seed_field,
                    seed_coordinate_ref=seed_coordinate,
                    neighbor_coordinate_ref=neighbor_coordinate,
                    lineage_match=lineage_match,
                )
            )
        return tuple(outcomes)

    def evaluate(self, *, entry: LocalRetrievalFixtureEntry) -> LocalRetrievalFixtureEvaluation:
        fixture_digest = self._fixture_digest(entry)
        base = {"fixture_id": entry.fixture_id, "fixture_digest": fixture_digest}
        if not self._sql_fixture_is_admitted(entry):
            return LocalRetrievalFixtureEvaluation.create(**base, status="not_fixture_admitted", reasons=("exact_value_sql_policy_not_fixture_admitted",))
        outcomes: list[FixtureCandidateOutcome] = []
        eligible: list[LocalRecallCandidate] = []
        for candidate in entry.candidates:
            is_eligible, reason = self._candidate_is_metadata_eligible(candidate=candidate, query=entry.query)
            outcomes.append(FixtureCandidateOutcome(candidate_id=candidate.candidate_id, status="accepted" if is_eligible else "metadata_rejected", reason=reason))
            if is_eligible:
                eligible.append(candidate)
        duplicate_filtered = self._deduplicate(eligible=tuple(eligible), outcomes=outcomes)
        if not duplicate_filtered:
            return LocalRetrievalFixtureEvaluation.create(
                **base,
                status="typed_exhaustion",
                reasons=(FixtureFailureClassifier.no_metadata_candidate(),),
                candidate_outcomes=tuple(outcomes),
            )
        selected, diversity_decision = self._select_with_diversity(
            eligible_pool_after_duplicate_filter=duplicate_filtered,
            candidate_capacity=entry.query.resolved_topk_policy.candidate_bundle_top_k,
            outcomes=outcomes,
        )
        selected_kinds = {candidate.candidate_kind for candidate in selected}
        missing_kinds = tuple(kind for kind in entry.required_candidate_kinds if kind not in selected_kinds)
        if missing_kinds:
            return LocalRetrievalFixtureEvaluation.create(
                **base,
                status="typed_exhaustion",
                reasons=(FixtureFailureClassifier.required_candidate_kind_missing(missing_kinds=missing_kinds), *tuple(f"required_candidate_kind_missing:{kind}" for kind in missing_kinds)),
                candidate_outcomes=tuple(outcomes),
                diversity_decision=diversity_decision,
            )
        neighbor_outcomes = self._neighbor_outcomes(entry=entry, selected=selected)
        required_neighbor_failures = tuple(outcome for outcome in neighbor_outcomes if outcome.reference.required and outcome.status == "typed_exhaustion")
        if required_neighbor_failures:
            first_failure = required_neighbor_failures[0]
            return LocalRetrievalFixtureEvaluation.create(
                **base,
                status="typed_exhaustion",
                reasons=(FixtureFailureClassifier.required_neighbor_missing(relation=first_failure.reference.relation), first_failure.reason),
                candidate_outcomes=tuple(outcomes),
                diversity_decision=diversity_decision,
                neighbor_outcomes=neighbor_outcomes,
            )
        reranked = self._rank(selected)[: entry.query.resolved_topk_policy.rerank_top_k]
        rerank_decisions = tuple(
            DeterministicRerankDecision(
                candidate_id=candidate.candidate_id,
                reranker_profile_id="local_lexical_metadata_reranker",
                reranker_profile_version="v1",
                filter_pass=True,
                rerank_score=float(candidate.source_authority_rank) + candidate.recall_score,
                score_components=("metadata_filter_pass", "fixture_recall_score", "source_authority_rank", "stable_tie_break"),
                tie_break_key=f"{candidate.metadata_rank:08d}:{candidate.candidate_id}",
            )
            for candidate in reranked
        )
        rerank_top_ids = tuple(candidate.candidate_id for candidate in reranked)
        projection_candidates = tuple(sorted(selected, key=lambda item: (item.metadata_rank, item.candidate_id)))
        bundle_projection = CandidateBundleProjection.create(query=entry.query, candidates=projection_candidates)
        gate_rerank_set = set(rerank_top_ids[: entry.query.resolved_topk_policy.evidence_gate_candidate_top_k])
        gate_ids = tuple(candidate.candidate_id for candidate in projection_candidates if candidate.candidate_id in gate_rerank_set)
        gate_projection = EvidenceGateCandidateProjection.create(bundle_projection=bundle_projection, candidate_ids=gate_ids)
        reasons = ["fixture_projection_nonexecuting"]
        if not diversity_decision.diversity_applicable:
            reasons.append("diversity_not_applicable_after_eligible_pool_filter")
        if any(outcome.status == "typed_exhaustion" for outcome in neighbor_outcomes):
            reasons.append("optional_neighbor_context_missing")
        return LocalRetrievalFixtureEvaluation.create(
            **base,
            status="accepted_fixture_projection",
            reasons=tuple(reasons),
            candidate_outcomes=tuple(outcomes),
            diversity_decision=diversity_decision,
            rerank_decisions=rerank_decisions,
            rerank_top_candidate_ids=rerank_top_ids,
            rerank_to_gate_set_preserved=set(gate_ids) == gate_rerank_set,
            neighbor_outcomes=neighbor_outcomes,
            candidate_bundle_projection=bundle_projection,
            evidence_gate_candidate_projection=gate_projection,
        )


LOCAL_RETRIEVAL_FIXTURE_MODELS = (
    SqlFixturePolicyPin,
    LocalRetrievalFixtureAdmissionPolicy,
    FixtureNeighborReference,
    LocalRetrievalFixtureEntry,
    LocalRetrievalFixtureCorpus,
    FixtureCandidateOutcome,
    FixtureDiversityDecision,
    FixtureNeighborOutcome,
    LocalRetrievalFixtureEvaluation,
)


__all__ = [
    "FixtureCandidateOutcome",
    "FixtureDiversityDecision",
    "FixtureFailureClassifier",
    "FixtureNeighborOutcome",
    "FixtureNeighborReference",
    "LOCAL_RETRIEVAL_FIXTURE_MODELS",
    "LocalRetrievalFixtureAdmissionPolicy",
    "LocalRetrievalFixtureCorpus",
    "LocalRetrievalFixtureEntry",
    "LocalRetrievalFixtureError",
    "LocalRetrievalFixtureEvaluation",
    "LocalRetrievalFixtureHarness",
    "SqlFixturePolicyPin",
]
