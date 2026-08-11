from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v5_"
    "fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_segmented_"
    "transport_v5_exact_admission_v1_0.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v5_"
    "fresh_exact_admission_issuance_v1_0.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v5_decision_and_issuance_are_exact_and_capture_bound() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    payload = _load(ADMISSION)
    assert payload == decision["prospective_admission"]["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    assert "provider_output_capture_policy_ref" in admission.model_fields_set
    assert admission.provider_output_capture_policy_ref == (
        S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
    )
    assert admission.transport_ref == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF
    digest = canonical_digest(admission.digest_payload())
    assert digest == decision["prospective_admission"]["admission_digest"]
    assert digest == issuance["issued_admission"]["admission_digest"]


def test_v5_issuance_loads_in_existing_runner_without_provider_call() -> None:
    target = load_execution_target(ISSUANCE)
    assert target.research_run_id == "research_run_fin01_1736461952f90e35f104f478"
    assert target.maximum_output_tokens == 16200
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))
    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict[str, object]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=_must_not_call_provider
    )
    assert callback_calls == 0


def test_v5_budget_nonreuse_and_stop_contract_remain_closed() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    assert decision["freshness_and_nonreuse"]["prior_research_run_count"] == 8
    assert decision["freshness_and_nonreuse"]["consumed_prior_identities_reusable"] is False
    envelope = issuance["execution_envelope"]
    assert [
        envelope["maximum_semantic_model_calls"],
        envelope["maximum_provider_calls"],
        envelope["maximum_network_calls"],
    ] == [12, 12, 12]
    assert envelope["retry_budget"] == 0
    assert envelope["automatic_retry_repair_fallback_or_rerun_allowed"] is False
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False


def test_v5_contracts_do_not_persist_plaintext_credentials() -> None:
    rendered = "\n".join(
        path.read_text(encoding="utf-8") for path in (DECISION, ADMISSION, ISSUANCE)
    )
    assert "DEEPSEEK_API_KEY" in rendered
    assert "sk-" not in rendered.lower()
