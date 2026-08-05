from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.materialize_fin_ia_0_1_2_s4_t07_entry_identity_and_scope_decision import (  # noqa: E402
    DEFAULT_OUTPUT,
    S4T07EntryDecisionError,
    build_decision,
    validate_entry_decision,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


def _load() -> dict:
    return json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))


def _redigest_observation(decision: dict) -> None:
    observation = decision["source_observation"]
    observation["observation_digest"] = canonical_digest(
        {key: value for key, value in observation.items() if key != "observation_digest"}
    )


def _redigest(decision: dict) -> None:
    decision["decision_digest"] = canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    )


def test_record_is_successor_safe_and_internally_valid() -> None:
    decision = _load()
    validate_entry_decision(decision)
    assert build_decision(decision["source_observation"]) == decision
    assert decision["predecessor"]["T06_C_record_digest"] == (
        "c4990c2e188bc03fd071cf3939cbf3e6e68479bb30edf75140d73668298bd41a"
    )


def test_self_asserted_headers_and_legacy_rows_do_not_establish_identity() -> None:
    decision = _load()
    observation = decision["source_observation"]
    assert observation["api_principal_from_client_headers_only"] is True
    assert observation["frontend_asserts_current_actor_and_permissions"] is True
    assert observation["frontend_has_qualified_review_permission"] is False
    assert observation["trusted_identity_provider_or_server_session_found"] is False
    assert decision["acceptance_boundary"]["authenticated_reviewer_identity"] is False


def test_entry_keeps_T07_actions_and_nvda_r3_false() -> None:
    decision = _load()
    assert decision["authority"]["qualified_review_action_authorized"] is False
    assert decision["authority"]["NVDA_R3_decision_authorized"] is False
    assert decision["hard_boundaries"]["automation_or_Codex_may_sign_human_acceptance"] is False
    assert decision["acceptance_boundary"]["qualified_human_review"] is False
    assert decision["acceptance_boundary"]["NVDA_R3"] is False


def test_recommended_internal_session_keeps_credentials_out_of_git_and_artifacts() -> None:
    decision = _load()
    option = decision["identity_disposition_options"][0]
    assert option["option"] == "A"
    assert option["recommendation"] == "recommended_for_FIN_0_1_2_internal_dogfood"
    assert "credential digest only in append-only control store" in option["scope"]
    assert "No plaintext credential" in option["secret_boundary"]
    assert decision["security_scope_choice"]["status"] == (
        "user_decision_required_before_T07_B"
    )


def test_T07_A_is_safe_while_identity_choice_blocks_T07_B_and_T07_C() -> None:
    decision = _load()
    sequence = decision["recommended_bounded_T07_sequence"]
    assert [row["task"] for row in sequence] == ["T07-A", "T07-B", "T07-C"]
    assert sequence[0]["status"] == "safe_after_entry_decision"
    assert sequence[1]["status"] == "blocked_user_security_scope_choice"
    assert decision["recommended_next"].startswith("FIN-0.1.2-S4-T07-A-")


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        (
            "trusted_identity_provider_or_server_session_found",
            True,
            "s4_t07_entry_identity_observation_invalid",
        ),
        (
            "frontend_has_qualified_review_permission",
            True,
            "s4_t07_entry_identity_observation_invalid",
        ),
    ],
)
def test_identity_observation_mutation_fails_closed(
    field: str, value: object, error: str
) -> None:
    decision = deepcopy(_load())
    decision["source_observation"][field] = value
    _redigest_observation(decision)
    _redigest(decision)
    with pytest.raises(S4T07EntryDecisionError, match=error):
        validate_entry_decision(decision)


def test_automation_acceptance_or_nvda_r3_mutation_fails_closed() -> None:
    decision = deepcopy(_load())
    decision["hard_boundaries"]["automation_or_Codex_may_sign_human_acceptance"] = True
    decision["acceptance_boundary"]["NVDA_R3"] = True
    _redigest(decision)
    with pytest.raises(
        S4T07EntryDecisionError,
        match="s4_t07_entry_hard_boundary_invalid|s4_t07_entry_acceptance_boundary_invalid",
    ):
        validate_entry_decision(decision)


def test_record_digest_mutation_fails_closed() -> None:
    decision = deepcopy(_load())
    decision["recommended_next"] = "mutated"
    with pytest.raises(
        S4T07EntryDecisionError, match="s4_t07_entry_decision_digest_mismatch"
    ):
        validate_entry_decision(decision)
