from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
    _sha256,
    _tree_digest,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
ROOT_CAUSE_DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v2_context_"
    "authority_failure_root_cause_decision_v1_0.json"
)
DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_exact_admission_decision_v1_0.json"
)
ADMISSION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_segmented_exact_admission_v1_0.json"
)
ISSUANCE = (
    RELEASES
    / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_exact_admission_issuance_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_issued_payload_exactly_matches_frozen_segmented_v3_contract() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    payload = _load(ADMISSION)
    assert payload == decision["prospective_admission"]["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict[str, object]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_during_issuance_test")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=_must_not_call_provider
    )
    digest = canonical_digest(admission.digest_payload())
    assert callback_calls == 0
    assert digest == decision["prospective_admission"]["admission_digest"]
    assert digest == issuance["issued_admission"]["admission_digest"]
    assert admission.output_contract_ref == "fin01.s3.bounded_agent_three_cell_output:v3"
    assert admission.transport_ref == (
        "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v1"
    )


def test_issuance_is_unconsumed_and_preserves_zero_call_boundary() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    issued = issuance["issued_admission"]
    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert authority["fresh_segmented_exact_admission_issuance_authorized"] is True
    assert authority["admission_consumption_or_execution_authorized"] is False
    assert authority["model_provider_network_source_or_tool_execution_authorized"] is False
    assert issued["fresh_identity"] is True
    assert issued["consumed"] is False
    assert issued["execution_started"] is False
    counts = issuance["observed_counts"]
    assert counts["new_admissions"] == 1
    assert all(value == 0 for key, value in counts.items() if key != "new_admissions")


def test_exact_binding_budget_blinding_and_execution_preconditions_are_frozen() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    binding = issuance["exact_binding"]
    envelope = issuance["execution_envelope"]
    preflight = issuance["zero_call_preflight"]
    identity = decision["fresh_identity"]
    assert binding["input_digest"] == identity["input_digest"]
    assert binding["preparation_digest"] == identity["preparation_digest"]
    assert binding["predicted_work_unit_id"] == identity["work_unit_id"]
    assert binding["predicted_attempt_id"] == identity["attempt_id"]
    assert binding["predicted_research_run_id"] == identity["research_run_id"]
    assert envelope["maximum_semantic_model_calls"] == 12
    assert envelope["maximum_provider_calls"] == 12
    assert envelope["maximum_network_calls"] == 12
    assert envelope["specialist_segment_output_tokens"] == [1600, 1200, 1400]
    assert envelope["maximum_output_tokens_total"] == 16200
    assert envelope["retry_budget"] == 0
    assert envelope["automatic_retry_repair_fallback_or_rerun_allowed"] is False
    assert preflight["baseline_output_body_exposed_to_agent"] is False
    assert preflight["baseline_body_or_artifact_is_provider_input"] is False
    assert preflight["transport_retry_environment_currently_zero"] is False
    assert preflight["credential_value_read_output_or_persisted"] is False


def test_existing_runner_loads_segmented_issuance_without_consuming_it() -> None:
    target = load_execution_target(ISSUANCE)
    assert target.admission_id == (
        "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-exact-admission-r1"
    )
    assert target.execution_identity == (
        "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-live-validation-r1"
    )
    assert target.research_run_id == "research_run_fin01_613dad1d30f9ce5357213b21"
    assert target.maximum_output_tokens == 16200


def test_historical_issuance_hash_and_post_execution_target_truth_are_distinguished() -> None:
    issuance = _load(ISSUANCE)
    preflight = issuance["zero_call_preflight"]
    database_path = RUNTIME_ROOT / "canonical-runtime" / "canonical.sqlite"
    object_root = RUNTIME_ROOT / "canonical-runtime" / "objects"
    snapshot = _logical_snapshot(database_path, "case_ac6fce120bf27977a1b45832")
    assert preflight["canonical_database_sha256"] == (
        "91ea473f1fb2419cc51cd3ea02ea33c5bf974319ebbb89b65c71be8668ecf39c"
    )
    assert _sha256(database_path) != preflight["canonical_database_sha256"]
    assert _tree_digest(object_root) != preflight["canonical_object_tree_sha256"]
    assert len(snapshot["work_unit_ids"]) == 9
    assert len(snapshot["attempt_ids"]) == 9
    assert len(snapshot["research_run_ids"]) == 9
    assert len(snapshot["artifact_refs"]) == 13
    binding = issuance["exact_binding"]
    assert binding["predicted_work_unit_id"] in snapshot["work_unit_ids"]
    assert binding["predicted_attempt_id"] in snapshot["attempt_ids"]
    assert binding["predicted_research_run_id"] in snapshot["research_run_ids"]


def test_backlog_advances_only_to_fresh_segmented_live_execution() -> None:
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["fresh_segmented_exact_admission_issuance_authorized"] is True
    assert next_action["fresh_segmented_exact_admission_issued"] is True
    assert next_action["fresh_segmented_exact_admission_consumed"] is True
    assert next_action["fresh_segmented_exact_live_execution_authorized"] is True
    assert next_action["agent_rerun_authorized"] is False
    assert next_action["owner_review_or_T10_authorized"] is False
    assert next_action["release_or_production_authorized"] is False


def test_issuance_files_do_not_contain_plaintext_credentials() -> None:
    rendered = ADMISSION.read_text(encoding="utf-8") + ISSUANCE.read_text(
        encoding="utf-8"
    )
    assert "DEEPSEEK_API_KEY" in rendered
    assert "sk-" not in rendered.lower()
    assert "fixture-secret" not in rendered.lower()
