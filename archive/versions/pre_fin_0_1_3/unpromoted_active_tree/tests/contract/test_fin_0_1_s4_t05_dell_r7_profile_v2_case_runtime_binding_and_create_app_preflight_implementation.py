from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    build_s4_source_grounded_bounded_agent_input,
    resolve_s4_case_runtime_binding_for_admission,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s4_source_grounded_exact_input,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    _principal,
    _read_only_execution_rows,
    _services,
    load_execution_target,
    preflight,
)
from sec_agent.s4_case_runtime import (
    S4CaseRuntimeError,
    S4_RUNTIME_CONSUMER_IDS,
    apply_s4_case_runtime_research_profile_overlay,
    assert_s4_case_runtime_research_profile_overlay,
    consume_s4_case_runtime_binding,
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)


R6_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_"
    "atom_fresh_exact_admission_r6.json"
)
R6_ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_"
    "deterministic_assembly_fresh_exact_admission_issuance_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
NEXT_ACTION = (
    "S4-T05-DELL-R7-PROFILE-V2-VERSIONED-CASE-RUNTIME-BINDING-"
    "FRESH-AGENT-PROOF-DECISION"
)
DELL_BASE_BINDING_DIGEST = (
    "78755ee3afa99ae5d33a170ee8184ef073fc895377ff1f668bfaf100358cf187"
)


def _r6() -> tuple[S3ThreeCellBoundedAgentAdmission, object]:
    target = load_execution_target(R6_ISSUANCE)
    return _load_admission(R6_ADMISSION, target), target


def test_frozen_case_loader_is_unchanged_and_overlay_is_deterministic() -> None:
    admission, _ = _r6()
    base_before = load_s4_case_runtime_binding(ROOT, "DELL")
    effective_one, overlay_one = (
        resolve_s4_case_runtime_binding_for_admission(ROOT, admission)
    )
    effective_two, overlay_two = (
        resolve_s4_case_runtime_binding_for_admission(ROOT, admission)
    )
    base_after = load_s4_case_runtime_binding(ROOT, "DELL")

    assert base_before == base_after
    assert base_before.runtime_binding_digest == DELL_BASE_BINDING_DIGEST
    assert base_before.research_profile_ref.endswith(":v1")
    assert effective_one == effective_two
    assert overlay_one == overlay_two
    assert effective_one.research_profile_ref == (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF
    )
    assert effective_one.runtime_binding_digest != DELL_BASE_BINDING_DIGEST
    assert overlay_one.base_runtime_binding_digest == DELL_BASE_BINDING_DIGEST
    assert overlay_one.effective_runtime_binding_digest == (
        effective_one.runtime_binding_digest
    )
    assert_s4_case_runtime_research_profile_overlay(
        effective_one,
        overlay_one.model_dump(mode="json"),
    )


def test_overlay_fails_closed_on_unregistered_or_wrong_scope_profile() -> None:
    admission, _ = _r6()
    with pytest.raises(
        ValueError,
        match="s3_bounded_admission_research_profile_unsupported",
    ):
        resolve_s4_case_runtime_binding_for_admission(
            ROOT,
            admission.model_copy(
                update={"research_profile_ref": "fin01.unknown.profile:v9"}
            ),
        )

    base = load_s4_case_runtime_binding(ROOT, "DELL")
    with pytest.raises(
        S4CaseRuntimeError,
        match="s4_case_runtime_research_profile_overlay_scope_mismatch",
    ):
        apply_s4_case_runtime_research_profile_overlay(
            base,
            research_profile_ref=S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF,
            research_profile_contract_payload={
                "profile_ref": S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF,
                "company": "MU",
                "program_cell_ids": list(base.program_cell_ids),
                "maximum_cell_count": 3,
            },
        )


def test_effective_binding_recomputes_all_seven_consumer_injections() -> None:
    admission, _ = _r6()
    base = load_s4_case_runtime_binding(ROOT, "DELL")
    effective, _ = resolve_s4_case_runtime_binding_for_admission(
        ROOT, admission
    )

    base_digests = {
        consumer_id: consume_s4_case_runtime_binding(
            base, consumer_id
        ).injection_digest
        for consumer_id in S4_RUNTIME_CONSUMER_IDS
    }
    effective_digests = {
        consumer_id: consume_s4_case_runtime_binding(
            effective, consumer_id
        ).injection_digest
        for consumer_id in S4_RUNTIME_CONSUMER_IDS
    }

    assert set(base_digests) == set(S4_RUNTIME_CONSUMER_IDS)
    assert all(
        base_digests[consumer_id] != effective_digests[consumer_id]
        for consumer_id in S4_RUNTIME_CONSUMER_IDS
    )


def test_v2_input_embeds_overlay_and_cannot_reuse_r6_digest() -> None:
    admission, _ = _r6()
    effective, overlay = resolve_s4_case_runtime_binding_for_admission(
        ROOT, admission
    )
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    input_pack = build_s4_source_grounded_bounded_agent_input(
        effective,
        source_pack,
        case_id=str(admission.case_id),
        case_version=int(admission.case_version or 0),
        query="DELL exact case",
        decision_surface_contract_ref="fixture_surface:v1",
        research_profile_overlay=overlay,
    )

    assert input_pack.input_digest != admission.input_digest
    assert input_pack.s4_case_runtime is not None
    assert input_pack.s4_case_runtime["research_profile_overlay"] == (
        overlay.model_dump(mode="json")
    )
    assert input_pack.lineage["S4_research_profile_overlay"]["digest"] == (
        overlay.overlay_digest
    )


def test_executor_requires_overlay_for_versioned_s4_binding() -> None:
    admission, _ = _r6()
    effective, _ = resolve_s4_case_runtime_binding_for_admission(
        ROOT, admission
    )
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    input_pack = build_s4_source_grounded_bounded_agent_input(
        effective,
        source_pack,
        case_id=str(admission.case_id),
        case_version=int(admission.case_version or 0),
        query="DELL exact case",
        decision_surface_contract_ref="fixture_surface:v1",
    )
    exact_admission = admission.model_copy(
        update={"input_digest": input_pack.input_digest}
    )

    class _ForbiddenNode:
        def execute_node(self, *_: object, **__: object) -> dict:
            raise AssertionError("node execution must not start")

    with pytest.raises(
        ValueError,
        match="s4_case_runtime_research_profile_overlay_required",
    ):
        S3ThreeCellBoundedAgentExecutor(_ForbiddenNode()).execute(
            input_pack,
            exact_admission,
            run_identity={
                "case_id": str(admission.case_id),
                "work_unit_id": "wu_fixture",
                "attempt_id": "attempt_fixture",
                "research_run_id": "run_fixture",
            },
        )


def test_r6_preflight_rejects_stale_input_before_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, target = _r6()
    runtime_root = ROOT / target.runtime_root_ref
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(
        RuntimeError,
        match="s3_t09_current_exact_input_or_identity_drift",
    ):
        preflight(runtime_root, R6_ADMISSION, target)


def test_in_memory_r7_candidate_passes_shared_create_app_path_without_calls(
    tmp_path: Path,
) -> None:
    admission, target = _r6()
    runtime_root = ROOT / target.runtime_root_ref
    clone_root = tmp_path / runtime_root.name
    shutil.copytree(runtime_root, clone_root)
    case_service, local_service, evidence_service = _services(clone_root)
    effective, overlay = resolve_s4_case_runtime_binding_for_admission(
        ROOT, admission
    )
    before = _read_only_execution_rows(
        clone_root, str(admission.case_id)
    )
    prepared = prepare_s4_source_grounded_exact_input(
        case_service,
        evidence_service,
        effective,
        load_s4_source_grounded_input_pack(ROOT, "DELL"),
        str(admission.case_id),
        _principal(),
        decision_surface_contract_ref=target.decision_surface_ref,
        execution_identity="fin01-s4-t05-dell-r7-zero-call-fixture",
        research_profile_overlay=overlay,
    )
    prospective = admission.model_copy(
        update={
            "admission_id": "fin01-s4-t05-dell-r7-in-memory-fixture",
            "input_digest": prepared.input_digest,
        }
    )
    provider_calls = 0

    def _forbidden_provider(**_: object) -> dict:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider callback must remain unused")

    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        prospective,
        chat_completion_fn=_forbidden_provider,
    )
    create_app(
        clone_root / "preflight-workbench.sqlite",
        p02_case_service=case_service,
        p03_evidence_service=evidence_service,
        p36_local_research_service=local_service,
        s3_three_cell_bounded_agent_admission=prospective,
        s3_three_cell_bounded_agent_executor=executor,
    )
    after = _read_only_execution_rows(clone_root, str(admission.case_id))

    assert prepared.input_digest != admission.input_digest
    assert prepared.observed_counts == {
        "canonical_writes": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
    }
    assert provider_calls == 0
    assert before == after


def test_implementation_record_closes_only_the_zero_call_gate() -> None:
    implementation = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    program = json.loads(PROGRAM_BACKLOG.read_text(encoding="utf-8"))
    detailed = json.loads(DETAILED_BACKLOG.read_text(encoding="utf-8"))

    assert implementation["status"] == (
        "pass_zero_call_versioned_profile_overlay_shared_resolver_and_"
        "create_app_preflight_fixture_proven_fresh_agent_proof_pending"
    )
    assert implementation["next_action"] == NEXT_ACTION
    assert implementation["stage_acceptance"]["RC_P36_063"] == (
        "fixture_proven_implementation_complete_fresh_agent_proof_pending"
    )
    assert implementation["stage_acceptance"]["DELL_R2"] == "not_proven"
    assert implementation["stage_acceptance"]["S4_T06"] == "not_entered"
    assert implementation["sequence_boundary"][
        "R7_admission_issuance_or_exact_live_execution_in_this_task"
    ] is False
    assert set(implementation["observed_counts"].values()) == {0}
    current_next = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json"
        ).read_text(encoding="utf-8")
    )["next_action"]
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
