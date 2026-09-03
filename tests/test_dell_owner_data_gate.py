from __future__ import annotations

import hashlib
import json

import pytest

from sec_agent.agent_runtime.dell_agentic_contracts import canonical_digest
from sec_agent.agent_runtime.dell_owner_data_gate import (
    DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST,
    DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_SHA256,
    DEFAULT_OWNER_DATA_GATE_DECISION_PATH,
    DellOwnerDataGateDecision,
    DellOwnerDataGateError,
    load_dell_owner_data_gate_decision,
    validate_trusted_dell_owner_data_gate_decision,
)


def test_checked_in_owner_decision_is_externally_anchored_and_exact() -> None:
    decision = load_dell_owner_data_gate_decision()

    assert decision.decision_digest == DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST
    assert hashlib.sha256(DEFAULT_OWNER_DATA_GATE_DECISION_PATH.read_bytes()).hexdigest() == (
        DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_SHA256
    )
    assert decision.route_catalog_decision.accepted_total_route_count == 32
    assert decision.reviewed_evidence_decision.audited_item_count == 61
    assert decision.reviewed_evidence_decision.executable_item_count == 56
    assert decision.reviewed_evidence_decision.ambiguous_audit_only_item_count == 5
    assert decision.bound_inputs.s2_observation_count == 1_319
    assert decision.bound_inputs.s2_entity_count == 3
    assert decision.bound_inputs.s2_metric_count == 12
    assert decision.authority.model_or_provider_calls_authorized is False
    assert decision.authority.network_calls_authorized is False
    assert decision.authority.paid_calls_authorized is False


def test_schema_valid_resigned_decision_cannot_self_authorize() -> None:
    raw = json.loads(DEFAULT_OWNER_DATA_GATE_DECISION_PATH.read_text(encoding="utf-8"))
    raw["known_boundaries"][0] = "a_schema_valid_but_untrusted_changed_boundary"
    raw["known_boundaries"] = sorted(raw["known_boundaries"])
    raw.pop("decision_digest")
    raw["decision_digest"] = canonical_digest(raw)
    resigned = DellOwnerDataGateDecision.model_validate_json(json.dumps(raw))

    with pytest.raises(
        DellOwnerDataGateError,
        match="owner_data_gate_decision_untrusted_digest",
    ):
        validate_trusted_dell_owner_data_gate_decision(resigned)
