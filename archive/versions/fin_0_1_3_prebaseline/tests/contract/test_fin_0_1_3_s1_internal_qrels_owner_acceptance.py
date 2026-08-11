from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_qrels_owner_acceptance import (  # noqa: E402
    S1InternalQrelsOwnerAcceptanceError,
    materialize_internal_qrels_owner_acceptance,
    validate_internal_qrels_owner_acceptance,
)


def test_owner_acceptance_is_bound_to_exact_qrels_and_only_opens_ranking_entry() -> None:
    result = materialize_internal_qrels_owner_acceptance(repo_root=ROOT)
    assert result["status"] == (
        "owner_accepted_research_qrels_v1_3_ranking_entry_eligible"
    )
    assert result["owner_decision"]["accepted_qrel_count"] == 18
    assert result["owner_decision"]["review_state"] == "owner_reviewed"
    assert result["owner_decision"]["ranking_entry_eligible"] is True
    assert result["preserved_boundaries"]["ranking_quality_accepted"] is False
    assert result["preserved_boundaries"]["current_quarter_exact_sql"] == (
        "0_of_6_open"
    )
    assert result["preserved_boundaries"][
        "external_official_required_slot_coverage"
    ] == "4_of_12_open_release_blocker"
    assert all(value == 0 for value in result["observed_calls"].values())


def test_owner_acceptance_boundary_mutation_fails_closed() -> None:
    result = materialize_internal_qrels_owner_acceptance(repo_root=ROOT)
    mutated = deepcopy(result)
    mutated["preserved_boundaries"]["product_acceptance"] = True
    with pytest.raises(
        S1InternalQrelsOwnerAcceptanceError,
        match="internal_qrels_owner_decision_digest_invalid",
    ):
        validate_internal_qrels_owner_acceptance(mutated)


def test_owner_acceptance_cannot_be_rebound_to_an_unreviewed_row_count() -> None:
    result = materialize_internal_qrels_owner_acceptance(repo_root=ROOT)
    mutated = deepcopy(result)
    mutated["source_qrels"]["accepted_qrel_digests"] = mutated[
        "source_qrels"
    ]["accepted_qrel_digests"][:-1]
    mutated.pop("decision_digest")
    from sec_agent.canonical_runtime.models import canonical_digest

    mutated["decision_digest"] = canonical_digest(mutated)
    with pytest.raises(
        S1InternalQrelsOwnerAcceptanceError,
        match="internal_qrels_owner_decision_semantics_invalid",
    ):
        validate_internal_qrels_owner_acceptance(mutated)
