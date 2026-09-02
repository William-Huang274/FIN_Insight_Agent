from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from sec_agent.agent_runtime.dell_a02_offline_replay import (
    LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
    LEGACY_A02_PLANNER_OUTCOME_REF,
    LEGACY_A02_PLANNER_OUTCOME_SHA256,
    LEGACY_A02_PLANNER_PARSED_PAYLOAD_SHA256,
    LegacyA02ReplaySourceRecord,
    replay_legacy_a02_planner_payload,
)
from sec_agent.canonical_runtime.contracts_v1_2 import canonical_json_sha256


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "dell_a02_planner_parsed_payload.json"
)
RECEIPT_PATH = (
    Path(__file__).parents[1]
    / "configs"
    / "research"
    / "evals"
    / "fin_ia_0_1_3_dell_a02_saved_planner_payload_offline_replay_v1_0.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _source_record() -> LegacyA02ReplaySourceRecord:
    body: dict[str, Any] = {
        "schema_version": "fin_ia_dell_a02_replay_source_record_v1_0",
        "source_record_id": "artifact-registry://dell/A02/planner-outcome",
        "resolver_ref": "resolver://immutable-qualification-artifact/current",
        "store_revision": 1,
        "artifact_store_snapshot_digest": canonical_json_sha256(
            {"snapshot": "immutable-a02-qualification"}
        ),
        "paid_full_chain_execution_id": LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
        "attempt_state": "start_failed",
        "authority_mode": "immutable_audit_only",
        "source_artifact_ref": LEGACY_A02_PLANNER_OUTCOME_REF,
        "source_artifact_sha256": LEGACY_A02_PLANNER_OUTCOME_SHA256,
        "parsed_payload_digest": LEGACY_A02_PLANNER_PARSED_PAYLOAD_SHA256,
        "resume_allowed": False,
        "successor_authorized": False,
        "issued_by": "host_immutable_artifact_resolver",
    }
    return LegacyA02ReplaySourceRecord(
        **body,
        source_record_digest=canonical_json_sha256(body),
    )


class _HostA02SourceResolver:
    def __init__(self, record: LegacyA02ReplaySourceRecord | None) -> None:
        self.record = record

    def resolve_current_immutable_a02_planner_outcome(
        self,
    ) -> LegacyA02ReplaySourceRecord | None:
        return self.record


def test_immutable_a02_saved_payload_replays_to_typed_feedback_without_calls() -> None:
    fixture = _fixture()
    assert fixture["extraction_policy"] == "parsed_payload_only_raw_response_omitted"
    assert "raw_response" not in fixture
    assert fixture["paid_full_chain_execution_id"] == LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID
    assert fixture["source_attempt_state"] == "start_failed"
    assert fixture["authority_mode"] == "immutable_audit_only"
    assert fixture["resume_allowed"] is False
    assert fixture["successor_authorized"] is False
    assert fixture["source_artifact_ref"] == LEGACY_A02_PLANNER_OUTCOME_REF
    assert fixture["source_artifact_sha256"] == LEGACY_A02_PLANNER_OUTCOME_SHA256
    assert fixture["parsed_payload_sha256"] == LEGACY_A02_PLANNER_PARSED_PAYLOAD_SHA256

    receipt = replay_legacy_a02_planner_payload(
        parsed_payload=fixture["parsed_payload"],
        source_resolver=_HostA02SourceResolver(_source_record()),
    )

    assert receipt.schema_validation_status == "schema_invalid"
    assert receipt.paid_full_chain_execution_id == LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID
    assert receipt.a02_attempt_state == "start_failed"
    assert receipt.authority_mode == "immutable_audit_only"
    assert receipt.resume_allowed is False
    assert receipt.successor_authorized is False
    assert receipt.task_count == 9
    assert receipt.evidence_request_count == 17
    assert receipt.fact_request_count == 2
    assert receipt.parsed_payload_digest == fixture["parsed_payload_sha256"]
    assert receipt.issue_count == 4
    assert receipt.model_calls == receipt.network_calls == receipt.provider_calls == 0
    assert receipt.raw_response_persisted is False
    assert [issue.issue_code for issue in receipt.issues] == [
        "local_evidence_request_scope_underbounded",
        "local_evidence_request_scope_underbounded",
        "external_request_local_retrieval_scope_forbidden",
        "planner_task_evidence_requests_too_short",
    ]
    assert [issue.branch_id for issue in receipt.issues] == [
        "Q6_MODEL_COMPUTE_DEMAND",
        "Q7_EXPORT_CONTROL_CHINA",
        "Q9_COUNTEREVIDENCE_WWC",
        "Q9_COUNTEREVIDENCE_WWC",
    ]
    assert json.loads(RECEIPT_PATH.read_text(encoding="utf-8")) == receipt.model_dump(
        mode="json"
    )


def test_replay_rejects_any_payload_other_than_the_exact_saved_a02_projection() -> None:
    payload = _fixture()["parsed_payload"]
    payload["tasks"][0]["objective"] = "Caller-authored replacement payload."
    with pytest.raises(ValueError, match="parsed_payload_not_exact_source"):
        replay_legacy_a02_planner_payload(
            parsed_payload=payload,
            source_resolver=_HostA02SourceResolver(_source_record()),
        )


def test_replay_requires_current_host_source_and_rejects_tampered_record() -> None:
    payload = _fixture()["parsed_payload"]
    with pytest.raises(ValueError, match="source_resolver_required"):
        replay_legacy_a02_planner_payload(
            parsed_payload=payload,
            source_resolver=None,
        )
    with pytest.raises(ValueError, match="source_record_missing"):
        replay_legacy_a02_planner_payload(
            parsed_payload=payload,
            source_resolver=_HostA02SourceResolver(None),
        )

    tampered = _source_record().model_copy(update={"source_record_id": "forged://row"})
    with pytest.raises(ValueError, match="source_record_digest_invalid"):
        replay_legacy_a02_planner_payload(
            parsed_payload=payload,
            source_resolver=_HostA02SourceResolver(tampered),
        )

    forged_body = _source_record().model_dump(
        mode="json", exclude={"source_record_digest"}
    )
    forged_body["successor_authorized"] = True
    forged = _source_record().model_copy(
        update={
            "successor_authorized": True,
            "source_record_digest": canonical_json_sha256(forged_body),
        }
    )
    with pytest.raises(ValidationError):
        replay_legacy_a02_planner_payload(
            parsed_payload=payload,
            source_resolver=_HostA02SourceResolver(forged),
        )
