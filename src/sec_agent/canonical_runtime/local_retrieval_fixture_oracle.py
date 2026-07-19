"""Independent M6.3R.2 fixture oracle contracts.

The oracle is package-external to the evaluator input corpus.  The fixture
harness never imports this module, so altering an oracle expectation cannot
alter an actual fixture evaluation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .local_retrieval_fixture import LocalRetrievalFixtureCorpus, LocalRetrievalFixtureEvaluation
from .local_retrieval_skeleton import SHA256_PATTERN
from .models import StrictModel, canonical_digest


class FixtureOracleRecord(StrictModel):
    """Post-evaluation expectation for exactly one immutable corpus entry."""

    fixture_id: str = Field(min_length=1)
    expected_status: Literal["accepted_fixture_projection", "typed_exhaustion", "not_fixture_admitted"]
    required_reason_codes: tuple[str, ...] = Field(min_length=1)


class LocalRetrievalFixtureOracle(StrictModel):
    """Create-owned, corpus-bound audit oracle; it has no execution authority."""

    oracle_id: str = Field(min_length=1)
    oracle_digest: str = Field(pattern=SHA256_PATTERN)
    corpus_id: str = Field(min_length=1)
    corpus_digest: str = Field(pattern=SHA256_PATTERN)
    records: tuple[FixtureOracleRecord, ...] = Field(min_length=1)
    oracle_provenance: Literal["independent_post_evaluation_fixture_oracle"] = "independent_post_evaluation_fixture_oracle"
    execution_admission: Literal["not_admitted"] = "not_admitted"
    persistence_authorized: Literal[False] = False

    @model_validator(mode="after")
    def require_exact_identity_and_unique_records(self) -> "LocalRetrievalFixtureOracle":
        if len({record.fixture_id for record in self.records}) != len(self.records):
            raise ValueError("fixture_oracle_duplicate_fixture_id")
        payload = self.model_dump(mode="json", exclude={"oracle_id", "oracle_digest"})
        digest = canonical_digest(payload)
        if self.oracle_digest != digest:
            raise ValueError("fixture_oracle_digest_mismatch")
        if self.oracle_id != f"local_retrieval_fixture_oracle_{digest[:20]}":
            raise ValueError("fixture_oracle_id_mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        corpus: LocalRetrievalFixtureCorpus,
        records: tuple[FixtureOracleRecord, ...],
    ) -> "LocalRetrievalFixtureOracle":
        payload = {
            "corpus_id": corpus.corpus_id,
            "corpus_digest": corpus.corpus_digest,
            "records": [record.model_dump(mode="json") for record in records],
            "oracle_provenance": "independent_post_evaluation_fixture_oracle",
            "execution_admission": "not_admitted",
            "persistence_authorized": False,
        }
        digest = canonical_digest(payload)
        return cls(oracle_id=f"local_retrieval_fixture_oracle_{digest[:20]}", oracle_digest=digest, **payload)

    def verify(
        self,
        *,
        corpus: LocalRetrievalFixtureCorpus,
        evaluations: tuple[LocalRetrievalFixtureEvaluation, ...],
    ) -> dict[str, bool]:
        """Compare completed actuals against external expectations only."""

        corpus_bound = (self.corpus_id, self.corpus_digest) == (corpus.corpus_id, corpus.corpus_digest)
        oracle_by_id = {record.fixture_id: record for record in self.records}
        evaluations_by_id = {evaluation.fixture_id: evaluation for evaluation in evaluations}
        fixture_ids = {entry.fixture_id for entry in corpus.entries}
        record_set_exact = set(oracle_by_id) == fixture_ids
        evaluation_set_exact = set(evaluations_by_id) == fixture_ids
        status_match = record_set_exact and evaluation_set_exact and all(
            evaluations_by_id[fixture_id].status == record.expected_status
            for fixture_id, record in oracle_by_id.items()
        )
        reason_match = record_set_exact and evaluation_set_exact and all(
            set(record.required_reason_codes).issubset(set(evaluations_by_id[fixture_id].reasons))
            for fixture_id, record in oracle_by_id.items()
        )
        return {
            "oracle_binds_exact_corpus": corpus_bound,
            "oracle_record_set_matches_corpus": record_set_exact,
            "oracle_evaluation_set_matches_corpus": evaluation_set_exact,
            "oracle_expected_statuses_match_actual": status_match,
            "oracle_required_reason_codes_match_actual": reason_match,
        }


LOCAL_RETRIEVAL_FIXTURE_ORACLE_MODELS = (FixtureOracleRecord, LocalRetrievalFixtureOracle)


__all__ = [
    "FixtureOracleRecord",
    "LOCAL_RETRIEVAL_FIXTURE_ORACLE_MODELS",
    "LocalRetrievalFixtureOracle",
]
