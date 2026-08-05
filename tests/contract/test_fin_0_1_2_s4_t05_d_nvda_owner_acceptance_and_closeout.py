from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.materialize_fin_ia_0_1_2_s4_t05_d_nvda_owner_acceptance_and_closeout import (  # noqa: E402
    DEFAULT_OUTPUT,
    EXPECTED_ASSESSMENT_DIGEST,
    T05DNVDAOwnerAcceptanceError,
    materialize,
    validate_owner_acceptance,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


def _load() -> dict:
    return json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))


def _redigest(value: dict) -> dict:
    value["decision_digest"] = canonical_digest(
        {key: row for key, row in value.items() if key != "decision_digest"}
    )
    return value


def test_explicit_owner_acceptance_closes_T05_D_and_sets_post_transfer_NVDA_R2() -> None:
    decision = materialize()
    assert decision == _load()
    validate_owner_acceptance(decision)
    assert decision["source_formal_assessment"]["assessment_digest"] == (
        EXPECTED_ASSESSMENT_DIGEST
    )
    assert decision["authority"]["user_message"] == "接受"
    assert decision["owner_decision"]["material_gain_accepted"] is True
    assert decision["acceptance_effect"]["S4_T05_D"] == (
        "pass_closed_owner_accepted"
    )
    assert decision["acceptance_effect"]["post_transfer_NVDA_R2"] is True
    assert decision["acceptance_effect"]["S4_T06_entry"] == (
        "authorized_not_started"
    )


def test_acceptance_preserves_quality_release_and_product_boundaries() -> None:
    decision = _load()
    assert decision["preserved_boundaries"]["RC_P36_119"].startswith("open_")
    assert decision["preserved_boundaries"]["RC_P36_125"].startswith("open_")
    assert decision["preserved_boundaries"]["strong_NVDA_investment_thesis"] is False
    assert decision["preserved_boundaries"]["qualified_human_review"] is False
    assert decision["preserved_boundaries"]["NVDA_R3"] is False
    assert decision["preserved_boundaries"]["S4_product_acceptance"] is False
    assert decision["preserved_boundaries"]["release"] == "not_qualified"
    assert decision["preserved_boundaries"]["production"] == "not_qualified"
    assert decision["observed_counts"]["S4_T06_runs"] == 0


def test_non_accept_message_cannot_retain_acceptance_semantics() -> None:
    changed = deepcopy(_load())
    changed["authority"]["user_message"] = "继续"
    _redigest(changed)
    with pytest.raises(
        T05DNVDAOwnerAcceptanceError,
        match="s4_t05_d_nvda_owner_acceptance_semantics_invalid",
    ):
        validate_owner_acceptance(changed)


@pytest.mark.parametrize(
    ("field", "value"),
    [("S4_T06_execution_started", True), ("S4_T06_entry_authorized", False)],
)
def test_owner_acceptance_does_not_silently_execute_T06(
    field: str, value: bool
) -> None:
    changed = deepcopy(_load())
    changed["authority"][field] = value
    _redigest(changed)
    with pytest.raises(
        T05DNVDAOwnerAcceptanceError,
        match="s4_t05_d_nvda_owner_acceptance_boundary_invalid",
    ):
        validate_owner_acceptance(changed)


def test_quality_or_release_claim_mutation_fails_closed() -> None:
    changed = deepcopy(_load())
    changed["preserved_boundaries"]["strong_NVDA_investment_thesis"] = True
    changed["preserved_boundaries"]["release"] = "qualified"
    _redigest(changed)
    with pytest.raises(
        T05DNVDAOwnerAcceptanceError,
        match="s4_t05_d_nvda_owner_acceptance_boundary_invalid",
    ):
        validate_owner_acceptance(changed)
