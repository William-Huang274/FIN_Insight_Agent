from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.evidence_service import EvidenceService
from apps.workbench.backend.application.local_research_service import (
    P36LocalResearchService,
)
from apps.workbench.backend.application.research_runtime import (
    Fin01ResearchRuntime,
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
)
from scripts.releases.issue_fin_ia_0_1_s4_t04_dell_fresh_exact_admission import (
    ADMISSION,
    EXPECTED_ADMISSION_DIGEST,
    ISSUANCE,
    NEXT_ACTION,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t04_dell_source_grounded_input_and_fresh_proof import (
    PLANNING_PROFILE_PATH,
    RUNTIME_ROOT,
    _case_service,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
    preflight,
)
from sec_agent.canonical_runtime.models import canonical_digest

S4_T05_IMPLEMENTATION = (
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
R7_BINDING_IMPLEMENTATION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_case_runtime_"
    "binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_admission_is_issued_unconsumed_and_digest_bound() -> None:
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(ADMISSION)
    )

    admission.assert_profile_admissible()
    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert canonical_digest(admission.digest_payload()) == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert issuance["issued_admission"]["admission_digest"] == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False


def test_issuance_reprepared_source_grounded_proof_and_fresh_identity() -> None:
    issuance = _load(ISSUANCE)
    proof = issuance["proof_reverification"]

    assert proof["generator_rerun_before_materialization"] is True
    assert proof["frozen_and_regenerated_decision_byte_equal"] is True
    assert proof["double_prepare_equal"] is True
    assert proof["source_pack_digest_equal"] is True
    assert all(proof["freshness_and_nonreuse"].values())
    assert proof["exact_code_binding_count"] == 6
    assert proof[
        "runtime_dispatch_consumes_source_grounded_S4_pack"
    ] is True
    assert proof["runner_preflight_dispatches_to_S4_exact_prepare"] is True
    counts = proof["canonical_execution_counts"]
    assert counts["canonical_work_units"] == 0
    assert counts["canonical_attempts"] == 0
    assert counts["canonical_research_run_versions"] == 0
    assert counts["canonical_artifact_versions"] == 0


def test_issued_exact_code_bindings_still_match_current_bytes() -> None:
    bindings = _load(ISSUANCE)["proof_reverification"]["exact_code_bindings"]
    implementation = _load(S4_T05_IMPLEMENTATION)
    task_claim_implementation = _load(TASK_CLAIM_IMPLEMENTATION)
    latest_implementation = _load(R7_BINDING_IMPLEMENTATION)
    allowed_changed_paths = set(
        latest_implementation["historical_exact_binding_supersession"][
            "allowed_changed_paths"
        ]
    )

    assert len(bindings) == 6
    for relative_path, expected_sha256 in bindings.items():
        current_sha256 = hashlib.sha256(
            (ROOT / relative_path).read_bytes()
        ).hexdigest()
        if current_sha256 != expected_sha256:
            assert (
                implementation["exact_code_bindings"].get(relative_path)
                == current_sha256
                or relative_path in allowed_changed_paths
            )
    assert implementation["historical_contract_disposition"][
        "historical_admission_or_Run_rewritten"
    ] is False
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


def test_runtime_selects_s4_source_grounded_adapter_without_calls() -> None:
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(ADMISSION)
    )
    planning_profile = _load(PLANNING_PROFILE_PATH)
    case_service = _case_service(
        RUNTIME_ROOT / "canonical-runtime", planning_profile
    )
    local_service = P36LocalResearchService.from_case_service(
        case_service, repo_root=ROOT
    )
    evidence_service = EvidenceService.from_case_service(
        case_service, repo_root=ROOT
    )
    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider callback invoked during runtime wiring")

    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    runtime = Fin01ResearchRuntime(
        case_service._facade,
        local_service,
        evidence_service,
        s3_three_cell_bounded_agent_admission=admission,
        s3_three_cell_bounded_agent_executor=executor,
        repo_root=ROOT,
    )
    adapter = runtime._adapters[S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF]

    assert adapter._s4_binding.case_ticker == "DELL"
    assert adapter._s4_source_pack.case_ticker == "DELL"
    assert adapter._s4_source_pack.source_pack_digest == (
        "27842233fdc469d5824bdc30ba21b752e35948781254c20adb1fed38df3fe639"
    )
    assert callback_calls == 0


def test_runner_zero_call_preflight_rejects_the_now_consumed_exact_identity(
    tmp_path: Path, monkeypatch
) -> None:
    issuance = _load(ISSUANCE)
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)
    clone_runtime = tmp_path / RUNTIME_ROOT.name
    shutil.copytree(RUNTIME_ROOT, clone_runtime)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(str(admission.api_key_env), "fixture-not-a-real-key")

    with pytest.raises(
        RuntimeError,
        match="s3_t09_exact_execution_identity_already_consumed",
    ):
        preflight(
            clone_runtime,
            ADMISSION,
            target,
            output_prefix="s4_t04_issuance_fixture",
        )

    assert issuance["exact_binding"]["input_digest"] == admission.input_digest
    assert issuance["issuance_boundary"]["admission_consumed"] is False
    assert issuance["observed_counts"]["model_calls"] == 0
    assert issuance["observed_counts"]["provider_calls"] == 0


def test_authority_stops_before_exact_live_and_s4_t05() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    boundary = issuance["issuance_boundary"]

    assert authority["fresh_exact_admission_issuance_authorized"] is True
    assert authority[
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert authority["paired_comparison_or_Human_review_authorized"] is False
    assert authority["S4_T05_or_later_authorized"] is False
    assert boundary["admission_issued"] is True
    assert boundary["admission_consumed"] is False
    assert boundary["execution_started"] is False
    assert boundary["model_or_provider_call_started"] is False
    assert issuance["next_action"] == NEXT_ACTION
