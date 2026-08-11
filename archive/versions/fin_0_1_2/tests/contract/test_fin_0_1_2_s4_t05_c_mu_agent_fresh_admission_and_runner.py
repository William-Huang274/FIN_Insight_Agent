from __future__ import annotations

import copy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "releases")]

from apps.workbench.backend.application.bounded_agent_executor import S3ThreeCellBoundedAgentInputPack  # noqa: E402
from apps.workbench.backend.application.fin_0_1_2_s4_t05_current_case_agent_exact_execution import (  # noqa: E402
    Fin012S4T05CurrentCaseAgentExecutionError,
    prepare_current_case_agent_execution,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import validate_transfer_evidence_pack  # noqa: E402
from prepare_and_issue_fin_ia_0_1_2_s4_t05_c_mu_agent_fresh_exact_admission import (  # noqa: E402
    AGENT_INPUT_REF,
    EVIDENCE_PACK_REF,
    build,
    _load,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import _principal  # noqa: E402


def test_mu_agent_fresh_proof_capacity_and_admission_are_exact() -> None:
    decision, admission, issuance = build(recorded_at="2026-08-05T06:30:00Z")
    assert decision["status"] == "pass_fresh_zero_call_proof_capacity_and_admission_authority"
    assert decision["fresh_proof"]["topology_each"] == [9, 3, 9, 9]
    assert decision["capacity_proof"]["aggregate_estimated_input_tokens"] <= 108000
    assert admission["company"] == "MU"
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["observed_counts"] == {"model_calls": 0, "provider_calls": 0, "network_calls": 0, "business_artifacts": 0}


def test_cross_case_agent_input_fails_before_execution() -> None:
    pack = validate_transfer_evidence_pack(_load(EVIDENCE_PACK_REF), case_key="MU")
    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(_load(AGENT_INPUT_REF))
    wrong = input_pack.model_copy(update={"company": "DELL"})
    with pytest.raises(Fin012S4T05CurrentCaseAgentExecutionError):
        prepare_current_case_agent_execution(
            wrong,
            pack,
            case_key="MU",
            principal=_principal(),
            execution_identity="cross-case-negative",
        )
