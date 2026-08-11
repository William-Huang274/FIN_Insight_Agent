from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from sec_agent.canonical_runtime.models import ActorSnapshot, CANONICAL_MODELS, CommandEnvelope
from sec_agent.canonical_runtime.schema_export import build_schema_bundle


pytestmark = pytest.mark.fast_contract


def _actor_payload() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "tenant_id": "tenant-test",
        "project_id": "project-test",
        "case_id": None,
        "created_at": now,
        "recorded_at": now,
        "actor_snapshot_ref": "actor-1",
        "permission_snapshot_ref": "permission-1",
        "correlation_id": "correlation-1",
        "current_status": "active",
        "actor_snapshot_id": "actor-1",
        "snapshot_version": 1,
        "actor_id": "user-1",
        "actor_type": "human",
        "display_name": "Test User",
    }


def test_registry_has_15_distinct_models_and_deterministic_schema_bundle() -> None:
    assert len(CANONICAL_MODELS) == 15
    assert len({model.__name__ for model in CANONICAL_MODELS}) == 15
    first = build_schema_bundle()
    second = build_schema_bundle()
    assert first == second
    assert set(first["models"]) >= {model.__name__ for model in CANONICAL_MODELS}


def test_model_names_match_frozen_machine_registry() -> None:
    root = Path(__file__).resolve().parents[2]
    registry = json.loads(
        (root / "configs" / "engineering_handoff" / "point01_canonical_object_registry_v0_2.json").read_text(
            encoding="utf-8"
        )
    )
    assert {row["object_name"] for row in registry["objects"]} == {model.__name__ for model in CANONICAL_MODELS}


def test_checked_in_schema_bundle_matches_runtime_export() -> None:
    root = Path(__file__).resolve().parents[2]
    checked_in = json.loads(
        (root / "configs" / "engineering_handoff" / "point01_generated_json_schemas_v1_0.json").read_text(
            encoding="utf-8"
        )
    )
    assert checked_in == build_schema_bundle()


def test_models_are_frozen_and_reject_unknown_fields() -> None:
    actor = ActorSnapshot.model_validate(_actor_payload())
    with pytest.raises(ValidationError):
        ActorSnapshot.model_validate({**_actor_payload(), "unknown": True})
    with pytest.raises(ValidationError):
        actor.display_name = "Changed"


def test_naive_timestamp_is_rejected() -> None:
    payload = _actor_payload()
    payload["created_at"] = datetime.now()
    with pytest.raises(ValidationError, match="timezone_aware_utc_required"):
        ActorSnapshot.model_validate(payload)


def test_command_envelope_rejects_naive_requested_at() -> None:
    with pytest.raises(ValidationError, match="timezone_aware_utc_required"):
        CommandEnvelope(
            command_id="command-1",
            command_type="CREATE_RESEARCH_CASE",
            tenant_id="tenant-test",
            project_id="project-test",
            actor_snapshot_ref="actor-1",
            permission_snapshot_ref="permission-1",
            idempotency_key="idem-1",
            expected_state_version=0,
            correlation_id="correlation-1",
            requested_at=datetime.now(),
            payload={},
        )
