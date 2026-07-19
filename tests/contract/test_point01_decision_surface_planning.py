from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.planning_service import (
    CompilerInputContract,
    CompilerInputError,
    DecisionCellSeed,
    DecisionSurfacePlanningService,
    EvidenceSlotSeed,
    PackSelectionDecision,
)
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract


def _command(command_type: str, payload: dict, *, expected: int = 0) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-{command_type}-{expected}",
        command_type=command_type,
        tenant_id="tenant-test",
        project_id="project-test",
        case_id="case-1",
        actor_snapshot_ref="actor-1",
        permission_snapshot_ref="permission-1",
        idempotency_key=f"idem-{command_type}-{expected}",
        expected_state_version=expected,
        correlation_id="correlation-1",
        requested_at=datetime.now(timezone.utc),
        payload=payload,
    )


def _facade(tmp_path) -> RuntimeFacade:
    flags = FeatureFlagRegistry(
        {"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]}
    )
    return RuntimeFacade(SQLiteCanonicalStore(tmp_path / "canonical.sqlite"), FileCanonicalObjectStore(tmp_path / "objects"), flags, mode="shadow", grants={"point01.shadow.write"})


def _input() -> CompilerInputContract:
    return CompilerInputContract(
        tenant_id="tenant-test",
        project_id="project-test",
        case_id="case-1",
        query="Assess durable software demand.",
        as_of=datetime(2026, 7, 12, tzinfo=timezone.utc),
        universe=("CRM", "NOW"),
        language="en",
        compiler_policy_ref="compiler-policy-v1",
        pack_selection=PackSelectionDecision(universal_pack_refs=("universal-v1",), report_type_pack_refs=("deep-research-v1",)),
        required_cells=(
            DecisionCellSeed(
                cell_key="demand",
                decision_question="Is demand durable?",
                origin_type="universal",
                owner_role="software_operator",
                materiality="high",
                stop_rule="issuer evidence plus counterevidence route",
                evidence_slots=(EvidenceSlotSeed(evidence_role="demand_quality", entity_scope=("CRM", "NOW"), period_scope="latest_quarter", source_policy_ref="issuer_first", acceptance_role="primary", required=True),),
            ),
        ),
    )


def _scope() -> dict:
    now = datetime(2026, 7, 12, tzinfo=timezone.utc).isoformat()
    return {"tenant_id": "tenant-test", "project_id": "project-test", "case_id": "case-1", "created_at": now, "recorded_at": now, "actor_snapshot_ref": "actor-1", "permission_snapshot_ref": "permission-1", "correlation_id": "correlation-1"}


def test_deterministic_fixture_validates_without_external_calls() -> None:
    service = DecisionSurfacePlanningService(None)  # type: ignore[arg-type]
    bundle = service.compile_deterministic_fixture(_input(), audit_scope=_scope())
    assert bundle == service.compile_deterministic_fixture(_input(), audit_scope=_scope())
    validation = service.validate_decision_surface_bundle("case-1", bundle)
    assert validation == {**validation, "status": "pass", "errors": [], "external_call_count": 0}
    broken = {**bundle, "cells": []}
    assert service.validate_decision_surface_bundle("case-1", broken)["status"] == "fail"
    with pytest.raises(CompilerInputError, match="audit_scope_case_mismatch"):
        service.compile_deterministic_fixture(_input(), audit_scope={**_scope(), "case_id": "other"})


def test_get_decision_surface_reads_committed_shadow_bundle(tmp_path) -> None:
    facade = _facade(tmp_path)
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "Assess durable software demand.", "accountable_owner_ref": "lead-1"}))
    facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-1", "input_version_refs": []}))
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-1", "attempt_id": "attempt-1"}))
    service = DecisionSurfacePlanningService(facade.store)
    bundle = service.compile_deterministic_fixture(_input(), audit_scope=_scope())
    facade.commit_decision_surface_bundle(_command("COMMIT_DECISION_SURFACE_BUNDLE", {"work_unit_id": "wu-1", "attempt_id": "attempt-1", "artifact_id": "artifact-1", "bundle": bundle}, expected=1))
    surface = service.get_decision_surface(bundle["contract"]["contract_id"])
    assert surface["planning_authority"] == "shadow"
    assert len(surface["cells"]) == 1
    assert len(surface["slots"]) == 1
