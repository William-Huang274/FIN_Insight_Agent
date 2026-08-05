from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_and_issue_fin_ia_0_1_2_s4_t05_d_nvda_post_transfer_agent_fresh_exact_admission import (  # noqa: E402
    ADMISSION_REF,
    DECISION_REF,
    EXECUTION_IDENTITY,
    ISSUANCE_REF,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t05_d_nvda_post_transfer_agent_exact_live import (  # noqa: E402
    DEFAULT_RUNTIME_ROOT,
    prepare_target,
    zero_call_preflight,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


def _load(ref: Path) -> dict:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def test_fresh_decision_admission_and_issuance_are_content_addressed() -> None:
    decision = _load(DECISION_REF)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION_REF))
    issuance = _load(ISSUANCE_REF)
    assert decision["decision_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    )
    assert issuance["issuance_digest"] == canonical_digest(
        {key: value for key, value in issuance.items() if key != "issuance_digest"}
    )
    assert issuance["issued_admission"]["admission_digest"] == canonical_digest(
        admission.digest_payload()
    )
    assert issuance["issued_admission"]["execution_identity"] == EXECUTION_IDENTITY
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    assert decision["capacity_proof"]["aggregate_estimated_input_tokens"] == 85614
    assert decision["capacity_proof"]["input_token_headroom"] == 22386
    assert decision["fresh_proof"]["topology_each"] == [9, 3, 9, 9]
    for binding in decision["immutable_bindings"]:
        assert hashlib.sha256((ROOT / binding["ref"]).read_bytes()).hexdigest() == (
            binding["sha256"]
        )


def test_runner_rehydrates_exact_target_without_provider_call() -> None:
    admission, issuance, prepared = prepare_target()
    assert admission.company == "NVDA"
    assert prepared.execution_identity == EXECUTION_IDENTITY
    assert prepared.input_digest == decision_input_digest(issuance)
    result = zero_call_preflight()
    assert result["status"] == "pass_exact_input_admission_transport_wiring_zero_call"
    assert result["provider_callback_calls"] == 0
    assert result["credential_value_output_or_persisted"] is False
    if DEFAULT_RUNTIME_ROOT.exists():
        terminal = json.loads((DEFAULT_RUNTIME_ROOT / "execution-result.json").read_text(encoding="utf-8"))["terminal"]
        assert terminal["status"] == "success"
        assert terminal["execution_identity"] == EXECUTION_IDENTITY


def decision_input_digest(issuance: dict) -> str:
    return str(issuance["exact_binding"]["complete_input_digest"])
