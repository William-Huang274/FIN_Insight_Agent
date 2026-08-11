from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2]
R7_BINDING_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    build_s4_source_grounded_bounded_agent_input,
)
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
)
from apps.workbench.backend.application.research_runtime import (
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    bind_s4_evidence_role_groups_to_runtime_plan,
    compile_fin01_s3_three_cell_runtime_plan,
    compile_profile_evidence_dispatch,
    prepare_s4_source_grounded_exact_input,
)
import apps.workbench.backend.application.research_runtime as runtime_module
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    ACTOR_ID,
    PERMISSIONS,
    PROJECT_ID,
    TENANT_ID,
    _headers,
    _principal,
    _services,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import (
    S4_CASE_EVIDENCE_ROLE_GROUP_MAPPING_REF,
    S4CaseRuntimeError,
    compile_s4_case_evidence_role_group_mapping,
    compile_s4_case_evidence_slot_alignment,
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)
from test_fin_0_1_s4_t03_case_runtime_injection_and_leakage_preflight import (
    _execute_fixture,
)
from test_fin_0_1_s3_t09_claim_fact_link_policy_zero_call_implementation import (
    _emit_claim_fact_aliases,
)
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s3_t09_research_lead_v5_compact_scoped_reference_dual_capacity_zero_call_implementation import (
    _CompactV5FullFakeProvider,
)


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
DELL_DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_source_grounded_input_materialization_"
    "and_fresh_proof_decision_v1_0.json"
)
DELL_ADMISSION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_fresh_exact_admission_v1_0.json"
)
IMPLEMENTATION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t05_evidence_role_group_mapping_actual_dispatch_"
    "preflight_zero_call_implementation_v1_0.json"
)
TASK_CLAIM_IMPLEMENTATION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t05_task_claim_link_policy_minimum_"
    "zero_call_implementation_v1_0.json"
)
NUMERIC_AUTHORITY_IMPLEMENTATION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "task_assembly_minimum_zero_call_implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_implementation_contract_binds_current_code_and_next_gate() -> None:
    implementation = _load(IMPLEMENTATION)
    task_claim_implementation = _load(TASK_CLAIM_IMPLEMENTATION)
    latest_implementation = _load(R7_BINDING_IMPLEMENTATION)
    assert implementation["status"] == (
        "pass_zero_call_implementation_fixture_proven_"
        "fresh_agent_proof_pending"
    )
    assert implementation["next_action"] == (
        "S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-REPAIR-"
        "FRESH-AGENT-PROOF-DECISION"
    )
    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["historical_contract_disposition"][
        "historical_admission_or_Run_rewritten"
    ] is False
    supersession = task_claim_implementation[
        "historical_exact_binding_supersession"
    ]
    allowed_changed_paths = set(supersession["allowed_changed_paths"])
    latest_allowed_changed_paths = set(
        latest_implementation["historical_exact_binding_supersession"][
            "allowed_changed_paths"
        ]
    )
    assert allowed_changed_paths == {
        "apps/workbench/backend/application/bounded_agent_contract_policies.py",
        "apps/workbench/backend/application/bounded_agent_executor.py",
        "tests/contract/"
        "test_fin_0_1_s4_t05_evidence_role_group_mapping_actual_dispatch_"
        "preflight_implementation.py",
    }
    implementation_ref = IMPLEMENTATION.relative_to(ROOT).as_posix()
    assert supersession["superseded_binding_contracts"][
        implementation_ref
    ] == hashlib.sha256(IMPLEMENTATION.read_bytes()).hexdigest()
    for relative_path, expected_sha256 in implementation[
        "exact_code_bindings"
    ].items():
        current_sha256 = hashlib.sha256(
            (ROOT / relative_path).read_bytes()
        ).hexdigest()
        if current_sha256 != expected_sha256:
            assert relative_path in latest_allowed_changed_paths
    for relative_path, expected_sha256 in task_claim_implementation[
        "exact_code_bindings"
    ].items():
        current_sha256 = hashlib.sha256(
            (ROOT / relative_path).read_bytes()
        ).hexdigest()
        if current_sha256 != expected_sha256:
            assert latest_implementation["exact_code_bindings"][
                relative_path
            ] == current_sha256


def _synthetic_surface(case_ticker: str) -> tuple[
    object, list[dict], list[dict]
]:
    binding = load_s4_case_runtime_binding(ROOT, case_ticker)
    mapping = compile_s4_case_evidence_role_group_mapping(binding)
    contract_ref = f"surface:{case_ticker}:v1"
    cells: list[dict] = []
    slots: list[dict] = []
    for group in mapping.role_groups:
        cell_version_ref = f"cell:{case_ticker}:{group.program_cell_id}:v1"
        cells.append(
            {
                "contract_version_id": contract_ref,
                "cell_version_id": cell_version_ref,
                "owner_role": group.owner_role,
            }
        )
        for evidence_role in group.source_evidence_roles:
            slots.append(
                {
                    "cell_version_id": cell_version_ref,
                    "slot_version_id": (
                        f"slot:{case_ticker}:{group.program_cell_id}:"
                        f"{evidence_role}:v1"
                    ),
                    "evidence_role": evidence_role,
                    "acceptance_role": group.owner_role,
                    "entity_scope": [case_ticker],
                    "required": True,
                }
            )
    return binding, cells, slots


@pytest.mark.parametrize("case_ticker", ["DELL", "MU"])
def test_role_groups_are_derived_and_all_fourteen_roles_align_exactly(
    case_ticker: str,
) -> None:
    binding, cells, slots = _synthetic_surface(case_ticker)
    mapping = compile_s4_case_evidence_role_group_mapping(binding)
    receipt = compile_s4_case_evidence_slot_alignment(
        binding,
        case_id=f"case:{case_ticker}",
        decision_surface_contract_ref=f"surface:{case_ticker}:v1",
        cells=cells,
        slots=slots,
    )

    assert mapping.contract_ref == S4_CASE_EVIDENCE_ROLE_GROUP_MAPPING_REF
    assert [len(row.source_evidence_roles) for row in mapping.role_groups] == [
        4,
        5,
        5,
    ]
    assert mapping.exact_role_count == 14
    assert receipt.resolved_role_count == 14
    assert len(receipt.slot_bindings) == 14
    assert len({row.slot_version_ref for row in receipt.slot_bindings}) == 14
    assert receipt.role_group_mapping_digest == (
        mapping.role_group_mapping_digest
    )
    assert all(
        value == 0
        for key, value in receipt.model_dump(mode="json").items()
        if key.endswith("_calls") or key == "canonical_writes"
    )


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("missing", "missing_extra_or_duplicate_role"),
        ("extra", "missing_extra_or_duplicate_role"),
        ("duplicate", "missing_extra_or_duplicate_role"),
        ("unknown_cell", "unknown_cell"),
        ("wrong_acceptance_owner", "slot_owner_or_scope_mismatch"),
        ("wrong_entity_scope", "slot_owner_or_scope_mismatch"),
        ("duplicate_cell_owner", "cell_cardinality"),
    ],
)
def test_alignment_fail_closed_negative_matrix(
    mutation: str,
    error: str,
) -> None:
    binding, cells, slots = _synthetic_surface("DELL")
    cells = deepcopy(cells)
    slots = deepcopy(slots)
    if mutation == "missing":
        slots.pop()
    elif mutation == "extra":
        slots.append(
            {
                **slots[-1],
                "slot_version_id": "slot:DELL:extra:v1",
                "evidence_role": "uncontracted_case_role",
            }
        )
    elif mutation == "duplicate":
        slots.append(
            {
                **slots[-1],
                "slot_version_id": "slot:DELL:duplicate:v1",
            }
        )
    elif mutation == "unknown_cell":
        slots[-1]["cell_version_id"] = "cell:DELL:unknown:v1"
    elif mutation == "wrong_acceptance_owner":
        slots[-1]["acceptance_role"] = "industry_analyst"
    elif mutation == "wrong_entity_scope":
        slots[-1]["entity_scope"] = ["MU"]
    elif mutation == "duplicate_cell_owner":
        cells[-1]["owner_role"] = cells[0]["owner_role"]

    with pytest.raises(S4CaseRuntimeError, match=error):
        compile_s4_case_evidence_slot_alignment(
            binding,
            case_id="case:DELL",
            decision_surface_contract_ref="surface:DELL:v1",
            cells=cells,
            slots=slots,
        )


def test_runtime_plan_mapping_digest_tamper_fails_closed() -> None:
    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    plan = compile_fin01_s3_three_cell_runtime_plan(
        case_id="case-s4-t05-digest-negative",
        work_unit_id="work-unit-s4-t05-digest-negative",
        attempt_id="attempt-s4-t05-digest-negative",
        research_run_id="run-s4-t05-digest-negative",
        execution_profile_version_ref=(
            S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
        ),
        decision_surface_contract_ref="surface-s4-t05-digest-negative:v1",
    )
    bound = bind_s4_evidence_role_groups_to_runtime_plan(plan, binding)
    tampered = bound.model_copy(
        update={"s4_evidence_role_group_mapping_digest": "0" * 64}
    )
    with pytest.raises(
        ValueError, match="s4_runtime_plan_role_group_digest_mismatch"
    ):
        bind_s4_evidence_role_groups_to_runtime_plan(tampered, binding)


def test_dell_preflight_and_actual_runtime_share_dispatch_before_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / RUNTIME_ROOT.name
    shutil.copytree(RUNTIME_ROOT, runtime_root)
    case_service, local_service, evidence_service = _services(runtime_root)
    materialization = _load(DELL_DECISION)["canonical_materialization"]
    case_id = str(materialization["case_id"])
    decision_surface_ref = str(
        materialization["decision_surface_contract_ref"]
    )
    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    execution_identity = "s4-t05-zero-call-dispatch-parity-fixture-r1"
    prepared = prepare_s4_source_grounded_exact_input(
        case_service,
        evidence_service,
        binding,
        source_pack,
        case_id,
        _principal(),
        decision_surface_contract_ref=decision_surface_ref,
        execution_identity=execution_identity,
    )
    assert prepared.role_group_mapping_digest
    assert prepared.evidence_alignment_digest
    assert prepared.evidence_dispatch_digest

    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(DELL_ADMISSION)
    ).model_copy(
        update={
            "admission_id": "s4-t05-zero-call-actual-runtime-fixture",
            "execution_mode": "exact_live_s4_dell_zero_call_fixture_r1",
        }
    )
    _, fixture_node_executor, fixture_output = _execute_fixture("DELL")

    class _StaticZeroCallExecutor:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def execute(
            self,
            input_pack: object,
            received_admission: object,
            *,
            run_identity: dict[str, str],
        ) -> object:
            self.calls.append(
                {
                    "input_pack": input_pack,
                    "admission": received_admission,
                    "run_identity": run_identity,
                }
            )
            return fixture_output

    executor = _StaticZeroCallExecutor()
    actual_dispatches = []
    original_dispatch = runtime_module.compile_profile_evidence_dispatch

    def _capture_actual_dispatch(*args: object, **kwargs: object) -> object:
        result = original_dispatch(*args, **kwargs)
        if not kwargs.get("prospective_execution_lineage", False):
            actual_dispatches.append(result)
        return result

    monkeypatch.setattr(
        runtime_module,
        "compile_profile_evidence_dispatch",
        _capture_actual_dispatch,
    )
    app = create_app(
        runtime_root / "workbench.sqlite",
        p02_case_service=case_service,
        p03_evidence_service=evidence_service,
        p36_local_research_service=local_service,
        s3_three_cell_bounded_agent_admission=admission,
        s3_three_cell_bounded_agent_executor=executor,
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/cases/{case_id}/work-units",
            headers=_headers(),
            json={
                "work_unit_type": BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
                "expected_case_version": 1,
                "input_head_digest": canonical_digest(
                    (decision_surface_ref,)
                ),
                "actor_ref": ACTOR_ID,
                "idempotency_key": execution_identity,
            },
        )
    assert response.status_code == 202, response.text
    store = case_service._facade.store
    work_unit = store.get_latest(
        "canonical_work_units", prepared.work_unit_id
    )
    assert work_unit and work_unit["state"] == "failed"
    assert len(actual_dispatches) == 1
    actual_dispatch = actual_dispatches[0]
    assert actual_dispatch.evidence_dispatch_digest == (
        prepared.evidence_dispatch_digest
    )
    assert actual_dispatch.role_group_mapping_digest == (
        prepared.role_group_mapping_digest
    )
    assert actual_dispatch.s4_evidence_slot_alignment.alignment_digest == (
        prepared.evidence_alignment_digest
    )
    assert len(executor.calls) == 1
    assert len(fixture_node_executor.calls) == 6
    assert len(fixture_output.artifacts) == 9


def test_legacy_s3_dispatch_remains_scalar_and_s4_has_no_fixture_fallback() -> None:
    runtime_source = (
        ROOT
        / "apps"
        / "workbench"
        / "backend"
        / "application"
        / "research_runtime.py"
    ).read_text(encoding="utf-8")
    evidence_source = (
        ROOT
        / "apps"
        / "workbench"
        / "backend"
        / "application"
        / "evidence_service.py"
    ).read_text(encoding="utf-8")
    assert "compile_profile_evidence_dispatch(" in runtime_source
    assert runtime_source.count("compile_profile_evidence_dispatch(") >= 3
    s4_method = evidence_source.split(
        "def compile_s4_case_evidence_slot_alignment(", 1
    )[1].split("def _s3_runtime_context(", 1)[0]
    assert "_s3_fixture_candidate_sets" not in s4_method
    assert "ticker ==" not in s4_method


def test_dell_full_fake_provider_reaches_six_nodes_twelve_calls_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    input_pack = build_s4_source_grounded_bounded_agent_input(
        binding,
        source_pack,
        case_id="case-s4-t05-dell-full-fake-provider",
        case_version=1,
        decision_surface_contract_ref="surface-s4-t05-dell:v1",
        query="Exercise the DELL S4 full fake-provider path.",
    )
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(DELL_ADMISSION)
    ).model_copy(
        update={
            "admission_id": "s4-t05-dell-full-fake-provider-fixture",
            "execution_mode": "exact_live_s4_dell_fake_provider_fixture",
            "case_id": input_pack.case_id,
            "case_version": input_pack.case_version,
            "input_digest": input_pack.input_digest,
        }
    )
    _, specialists = _shared_local_id_specialists()

    def _s4_authority_mutation(
        request: dict[str, Any], output: dict[str, Any]
    ) -> dict[str, Any]:
        output = _emit_claim_fact_aliases(request, output)
        segment_id = request.get("segment_id")
        if segment_id == "facts_explanation_and_terminal":
            allowed = request["fact_support_authority_contract"][
                "allowed_refs_by_support_type"
            ]
            for fact in output["fact_layer"]:
                fact["support_type"] = "Evidence"
                fact["support_refs"] = [allowed["Evidence"][0]]
        elif segment_id == "actionable_what_would_change_tasks":
            refs = request["analysis_input"]["cell_input"][
                "authority_refs"
            ]["accepted_evidence_refs"]
            for task in output["what_would_change"]:
                task["authority_refs"] = [refs[0]]
                task["source_target"]["entity_or_owner"] = "DELL"
        return output

    fake = _CompactV5FullFakeProvider(
        specialists,
        mutation=_s4_authority_mutation,
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "run-s4-t05-dell-full-fake-provider",
            "attempt_id": "attempt-s4-t05-dell-full-fake-provider",
        },
    )

    assert result.terminal_reason == (
        "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
