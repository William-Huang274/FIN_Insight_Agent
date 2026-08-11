from __future__ import annotations

import inspect
import json
from pathlib import Path

from apps.workbench.backend.application.research_runtime import Fin01ResearchRuntime
from sec_agent.canonical_runtime.facade import RuntimeFacade


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
AUDIT = RELEASES / (
    "fin_ia_0_1_s3_t09_controller_orphan_zero_call_root_cause_audit_v1_0.json"
)
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_controller_orphan_and_verifier_state_machine_"
    "zero_call_root_cause_disposition_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_safe_audit_proves_typed_shape_but_false_green_state_conflict() -> None:
    audit = _load(AUDIT)
    verifier = audit["verifier_safe_structure"]
    assert audit["status"] == "pass_zero_call_dual_failure_root_cause_reconstructed"
    assert verifier["typed_finding_shape_valid"] is True
    assert verifier["statuses"] == ["pass", "pass", "pass", "pass"]
    assert verifier["issue_code_counts"] == [1, 7, 2, 3]
    assert verifier["artifact_or_claim_ref_counts"] == [2, 2, 1, 1]
    assert verifier["decision"] == "accept_for_internal_review"
    assert verifier["false_green_predicate_triggered"] is True
    assert verifier["inferred_local_failure_code"] == (
        "s3_owner_grade_verifier_false_green_forbidden"
    )
    rendered = AUDIT.read_text(encoding="utf-8")
    assert '"assistant_output_text":' not in rendered
    assert "DEEPSEEK_API_KEY" not in rendered
    assert "sk-" not in rendered.lower()


def test_runtime_implements_selected_single_command_failure_terminalization() -> None:
    runtime_source = inspect.getsource(Fin01ResearchRuntime.dispatch_once)
    assert "record_research_run_provider_output_captures" not in runtime_source
    assert '"provider_output_captures": provider_output_captures' in runtime_source
    assert runtime_source.count("self._facade.fail_research_run(failed)") >= 1

    fail_source = inspect.getsource(RuntimeFacade.fail_research_run)
    assert "with self.store.transaction() as tx:" in fail_source
    assert "provider_output_capture_refs = self._persist_provider_output_captures(" in (
        fail_source
    )
    assert 'tx.insert("canonical_research_run_versions"' in fail_source
    assert '"RESEARCH_RUN_FAILED"' in fail_source


def test_disposition_selects_atomic_terminalization_and_closed_state_machine() -> None:
    decision = _load(DECISION)
    disposition = decision["root_cause_disposition"]
    selected = decision["selected_zero_call_implementation_contract"]
    assert decision["status"] == (
        "pass_zero_call_dual_failure_root_cause_frozen_"
        "atomic_terminalization_and_typed_verifier_state_machine_selected"
    )
    assert disposition["RC_P36_049"]["full_chain_blocker"] is False
    assert disposition["RC_P36_051"]["model_only_failure"] is False
    assert disposition["RC_P38_050"]["external_trigger"] == (
        "outer execution command timeout"
    )
    assert selected["atomic_failure_terminalization"][
        "runtime_exception_path_command_count"
    ] == 1
    assert selected["atomic_failure_terminalization"][
        "separate_preterminal_capture_command_for_failure_path_allowed"
    ] is False
    state_machine = selected["typed_verifier_state_machine"]
    assert state_machine["contract_ref"].endswith(":v1")
    assert len(state_machine["safe_failure_subtypes_required"]) == 7
    assert state_machine["normalization_or_silent_rewrite_allowed"] is False


def test_disposition_preserves_authority_and_routes_to_zero_call_implementation() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    expected = (
        "S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-"
        "TYPED-VERIFIER-STATE-MACHINE-ZERO-CALL-IMPLEMENTATION"
    )
    assert decision["next_action"] == expected
    assert decision["authority"]["repair_implementation_authorized"] is False
    assert decision["authority"][
        "replacement_admission_or_second_live_authorized"
    ] is False
    assert set(decision["observed_counts"].values()) == {0}
    assert backlog["next_action"]["item_id"] == expected
    assert backlog["next_action"]["agent_execution_authorized"] is False
    assert backlog["next_action"]["replacement_admission_or_execution_authorized"] is (
        False
    )
