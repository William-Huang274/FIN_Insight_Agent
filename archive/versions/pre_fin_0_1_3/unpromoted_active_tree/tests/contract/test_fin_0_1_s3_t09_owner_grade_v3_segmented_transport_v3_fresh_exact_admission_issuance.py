from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF,
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
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_"
    "fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_segmented_"
    "transport_v3_exact_admission_v1_0.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_"
    "fresh_exact_admission_issuance_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"
RUNTIME_ROOT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_issue(issue_id: str) -> dict[str, object]:
    latest: dict[str, dict[str, object]] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[str(row["issue_id"])] = row
    return latest[issue_id]


def test_issued_payload_exactly_matches_frozen_transport_v3_contract() -> None:
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
    assert admission.transport_ref == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF
    assert admission.output_contract_ref == "fin01.s3.bounded_agent_three_cell_output:v3"


def test_issuance_is_unconsumed_and_preserves_zero_call_boundary() -> None:
    issuance = _load(ISSUANCE)
    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert issuance["authority"][
        "fresh_transport_v3_exact_admission_issuance_authorized"
    ] is True
    assert issuance["authority"]["admission_consumption_or_execution_authorized"] is False
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    counts = issuance["observed_counts"]
    assert counts["new_admissions"] == 1
    assert all(value == 0 for key, value in counts.items() if key != "new_admissions")


def test_binding_budget_nonreuse_blinding_and_stop_line_are_frozen() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    binding = issuance["exact_binding"]
    identity = decision["fresh_identity"]
    assert binding["input_digest"] == identity["input_digest"]
    assert binding["preparation_digest"] == identity["preparation_digest"]
    assert binding["predicted_work_unit_id"] == identity["work_unit_id"]
    assert binding["predicted_attempt_id"] == identity["attempt_id"]
    assert binding["predicted_research_run_id"] == identity["research_run_id"]
    envelope = issuance["execution_envelope"]
    assert [
        envelope["maximum_semantic_model_calls"],
        envelope["maximum_provider_calls"],
        envelope["maximum_network_calls"],
    ] == [12, 12, 12]
    assert envelope["maximum_output_tokens_total"] == 16200
    assert envelope["retry_budget"] == 0
    assert envelope["same_context_authority_failure_disposition"] == (
        "stop_prompt_only_repair_and_move_to_provider_route_disposition"
    )
    preflight = issuance["zero_call_preflight"]
    assert preflight["prior_research_run_nonreuse_count"] == 6
    assert preflight["baseline_output_body_exposed_to_agent"] is False
    assert preflight["transport_retry_environment_currently_zero"] is False
    assert issuance["product_proof_target"] == decision["product_proof_target"]


def test_existing_runner_loads_transport_v3_issuance_without_consuming_it() -> None:
    target = load_execution_target(ISSUANCE)
    assert target.admission_id == (
        "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-"
        "transport-v3-exact-admission-r1"
    )
    assert target.execution_identity == (
        "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-"
        "transport-v3-live-validation-r1"
    )
    assert target.research_run_id == "research_run_fin01_9bc3ffd904ae98b26b5cba95"
    assert target.maximum_output_tokens == 16200


def test_issued_identity_is_now_exactly_once_consumed_without_artifact() -> None:
    decision = _load(DECISION)
    preflight = _load(ISSUANCE)["zero_call_preflight"]
    database_path = RUNTIME_ROOT / "canonical-runtime" / "canonical.sqlite"
    object_root = RUNTIME_ROOT / "canonical-runtime" / "objects"
    snapshot = _logical_snapshot(database_path, "case_ac6fce120bf27977a1b45832")
    assert [
        len(snapshot["work_unit_ids"]),
        len(snapshot["attempt_ids"]),
        len(snapshot["research_run_ids"]),
        len(snapshot["artifact_refs"]),
    ] == [9, 9, 9, 13]
    assert decision["fresh_identity"]["work_unit_id"] in snapshot["work_unit_ids"]
    assert decision["fresh_identity"]["attempt_id"] in snapshot["attempt_ids"]
    assert decision["fresh_identity"]["research_run_id"] in snapshot[
        "research_run_ids"
    ]
    assert _tree_digest(object_root) != preflight["canonical_object_tree_sha256"]


def test_current_project_os_advances_only_to_zero_call_root_cause_decision() -> None:
    next_action = _load(BACKLOG)["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["transport_v3_fresh_exact_admission_issuance_authorized"] is True
    assert next_action["transport_v3_fresh_exact_admission_issued"] is True
    assert next_action["transport_v3_fresh_exact_admission_consumed"] is True
    assert next_action["transport_v3_fresh_live_execution_authorized"] is True
    assert next_action["transport_v3_fresh_artifact_count"] == 0
    assert next_action["agent_rerun_authorized"] is False
    issue = _latest_issue(
        "RC-P36-039-s3-owner-grade-v3-first-specialist-schema-and-observability-gap"
    )
    assert issue["status"] == (
        "closed_transport_v5_live_completed_all_three_specialists_and_"
            "nine_segments"
    )
    assert issue["full_chain_blocker"] is False


def test_issuance_files_do_not_contain_plaintext_credentials() -> None:
    rendered = ADMISSION.read_text(encoding="utf-8") + ISSUANCE.read_text(
        encoding="utf-8"
    )
    assert "DEEPSEEK_API_KEY" in rendered
    assert "sk-" not in rendered.lower()
    assert "fixture-secret" not in rendered.lower()
