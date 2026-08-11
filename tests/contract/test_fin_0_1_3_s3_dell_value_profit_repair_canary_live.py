from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s3_dell_value_profit_repair_canary import (  # noqa: E402
    _normalized_text_sha256,
    compile_repair_canary_material,
    load_repair_canary_policy,
)
from sec_agent.s3_dell_value_profit_repair_canary_live import (  # noqa: E402
    LIVE_EXECUTION_AUTHORITY_SCHEMA,
    LIVE_SCOPE,
    S3DellValueProfitRepairCanaryLiveError,
    credential_presence_only,
    execute_live_canary,
    issue_live_canary_admission,
    validate_live_canary_issuance,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_policy_v1_0.json"
)
DECISION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_repair_canary_"
    "live_value_cost_risk_authority_decision_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "clean_independent_proof_v1_0.json"
)
SOURCE_REFS = (
    "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
    "configs/runtime/fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_policy_v1_0.json",
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_minimum_zero_call_implementation_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_clean_independent_proof_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s3_dell_value_profit_repair_canary_live_value_cost_risk_authority_decision_v1_0.json",
    "src/sec_agent/s3_dell_value_profit_repair_canary.py",
    "src/sec_agent/s3_dell_value_profit_repair_canary_live.py",
    "scripts/releases/issue_fin_ia_0_1_3_s3_dell_value_profit_repair_canary_live_admission.py",
    "scripts/releases/run_fin_ia_0_1_3_s3_dell_value_profit_repair_canary_live.py",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def basis() -> dict:
    policy = load_repair_canary_policy(POLICY_PATH, repo_root=ROOT)
    return {
        "material": compile_repair_canary_material(policy=policy, repo_root=ROOT),
        "decision": _load(DECISION_PATH),
        "proof": _load(PROOF_PATH),
        "preflight": {"status": "pass", "run_scope": LIVE_SCOPE, "errors": []},
        "bindings": [
            {
                "ref": ref,
                "normalized_text_sha256": _normalized_text_sha256(ROOT / ref),
            }
            for ref in SOURCE_REFS
        ],
    }


def _issue(basis: dict) -> dict:
    return issue_live_canary_admission(
        decision=basis["decision"],
        clean_proof=basis["proof"],
        material=basis["material"],
        implementation_commit="1" * 40,
        source_bindings=basis["bindings"],
        project_os_preflight=basis["preflight"],
        credential_preflight={
            "credential_env_name": "DEEPSEEK_API_KEY",
            "credential_present": True,
            "credential_value_read_output_or_persisted": False,
        },
        issued_at="2026-08-11T13:00:00Z",
        expires_at="2026-08-12T13:00:00Z",
        run_nonce="0123456789abcdef0123456789abcdef",
        user_authority="fixture authority only",
    )


def _execution_authority(issuance: dict) -> dict:
    body = {
        "schema_version": LIVE_EXECUTION_AUTHORITY_SCHEMA,
        "status": "authorized_single_exact_once_live_canary_execution",
        "issuance_digest": issuance["issuance_digest"],
        "admission_digest": issuance["admission"]["admission_digest"],
        "execute_provider_call": True,
        "provider_calls_maximum": 1,
        "model_calls_maximum": 1,
        "retries": 0,
        "fallbacks": 0,
        "business_artifact_promotion": False,
    }
    return {**body, "execution_authority_digest": canonical_digest(body)}


def _row(
    cell_id: str,
    *,
    state: str,
    changed: bool,
    support: list[str],
    counter: list[str] | None = None,
    numeric: list[str] | None = None,
    mechanism: str,
    boundary: str,
    wwc: str = "",
) -> dict:
    return {
        "cell_id": cell_id,
        "judgment_state": state,
        "judgment_changed": changed,
        "support_refs": support,
        "counterevidence_refs": counter or [],
        "numeric_refs": numeric or [],
        "mechanism_atom": mechanism,
        "boundary_atom": boundary,
        "wwc_ref": wwc,
    }


def _valid_output() -> dict:
    required_num = "NUM:DELL:OPERATING_MARGIN_TARGET:2894219F450D"
    return {
        "schema_version": (
            "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
            "repair_canary_output_v1_0"
        ),
        "case_key": "DELL",
        "node_id": "dell_value_profit_current_pack_repair_adjudicator_v1",
        "repair_request_id": "evidence_request_0eb73a1c4b81a05d96b7",
        "observation_outcome": "accepted",
        "repair_resolution": "accepted_partial_resolution",
        "accepted_evidence_refs": ["E021"],
        "boundary_evidence_refs": ["E002", "E008", "E023"],
        "evidence_semantics": {
            "e021_evidence_role": "issuer_direct_source",
            "operating_profitability_status": (
                "issuer_management_observed_in_line_with_target"
            ),
            "isg_profit_attribution_status": "forbidden_substitution",
            "gross_margin_status": "typed_gap",
            "cash_conversion_status": "typed_gap",
            "audited_product_profit_bridge_status": "typed_gap",
        },
        "retained_gap_components": [
            "audited_product_profit_bridge",
            "cash_conversion",
            "gross_margin",
        ],
        "affected_cell_readjudications": [
            _row(
                "bottleneck_counterevidence_and_what_would_change",
                state="supported_with_limits",
                changed=True,
                support=["E021"],
                mechanism="Issuer commentary narrows the monitoring question.",
                boundary="Audited product profit and conversion remain unknown.",
                wwc="DELL_W_AI_MARGIN",
            ),
            _row(
                "cross_chain_price_in_and_expectations",
                state="cannot_infer",
                changed=False,
                support=["E002"],
                mechanism="Segment context does not establish market pricing.",
                boundary="No valuation conclusion follows from this evidence.",
            ),
            _row(
                "value_and_profit_capture",
                state="supported_with_limits",
                changed=True,
                support=["E021"],
                counter=["E002", "E008"],
                numeric=[required_num],
                mechanism=(
                    "Issuer commentary supports bounded operating profitability "
                    "while mix evidence limits profit transmission."
                ),
                boundary=(
                    "Segment income cannot replace product profit; gross margin and "
                    "cash conversion remain open."
                ),
                wwc="DELL_W_AI_MARGIN",
            ),
            _row(
                "writer_admission_boundary",
                state="supported_with_limits",
                changed=True,
                support=["E021", "E002"],
                mechanism="The report may state only the bounded issuer comparison.",
                boundary=(
                    "The report cannot claim audited product profit, valuation or "
                    "a recommendation."
                ),
                wwc="DELL_W_AI_MARGIN",
            ),
        ],
        "used_numeric_refs": [required_num],
    }


def test_zero_call_decision_is_digest_valid_and_does_not_authorize_execution(
    basis: dict,
) -> None:
    decision = basis["decision"]
    body = {key: value for key, value in decision.items() if key != "decision_digest"}
    assert decision["decision_digest"] == canonical_digest(body)
    assert decision["authorized_next_implementation"]["register_live_scope"] == (
        LIVE_SCOPE
    )
    assert decision["authorized_next_implementation"]["execute_provider_call"] is False
    assert decision["scope"]["model_calls"] == 0
    assert decision["scope"]["credential_value_read_output_or_persisted"] is False


def test_issuance_binds_clean_proof_source_set_budget_and_expiry(basis: dict) -> None:
    issuance = _issue(basis)
    validate_live_canary_issuance(
        issuance,
        decision=basis["decision"],
        clean_proof=basis["proof"],
        material=basis["material"],
        project_os_preflight=basis["preflight"],
        repo_root=ROOT,
        observed_at="2026-08-11T13:00:01Z",
    )
    assert issuance["status"] == "issued_unconsumed_execution_not_authorized"
    assert issuance["observed_counts"]["provider_calls"] == 0
    assert issuance["admission"]["run_scope"] == LIVE_SCOPE
    with pytest.raises(S3DellValueProfitRepairCanaryLiveError, match="expired"):
        validate_live_canary_issuance(
            issuance,
            decision=basis["decision"],
            clean_proof=basis["proof"],
            material=basis["material"],
            project_os_preflight=basis["preflight"],
            repo_root=ROOT,
            observed_at="2026-08-12T13:00:00Z",
        )


def test_live_execution_is_capture_first_exact_once_and_counts_one_call(
    basis: dict, tmp_path: Path
) -> None:
    issuance = _issue(basis)
    authority = _execution_authority(issuance)
    calls: list[dict] = []

    def provider(request: Mapping[str, object]) -> dict:
        calls.append(dict(request))
        return {
            "status": "ok",
            "content": json.dumps(_valid_output(), ensure_ascii=False),
            "finish_reason": "stop",
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }

    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared.sqlite")
    terminal = execute_live_canary(
        issuance=issuance,
        execution_authority=authority,
        decision=basis["decision"],
        clean_proof=basis["proof"],
        material=basis["material"],
        project_os_preflight=basis["preflight"],
        repo_root=ROOT,
        provider_call=provider,
        runtime_root=tmp_path / "attempt",
        shared_ledger=ledger,
        observed_at="2026-08-11T13:01:00Z",
    )
    assert len(calls) == 1
    assert terminal["terminal_code"] == "s3_live_repair_canary_pass"
    assert terminal["observed_counts"]["provider_calls"] == 1
    assert terminal["observed_counts"]["model_calls"] == 1
    assert terminal["business_artifact_promotion"] is False
    assert (tmp_path / "attempt/raw_model_only/calls/call_01/capture.json").is_file()
    assert (tmp_path / "attempt/validated/successor_program.json").is_file()
    with pytest.raises(SharedAdmissionLedgerError):
        execute_live_canary(
            issuance=issuance,
            execution_authority=authority,
            decision=basis["decision"],
            clean_proof=basis["proof"],
            material=basis["material"],
            project_os_preflight=basis["preflight"],
            repo_root=ROOT,
            provider_call=provider,
            runtime_root=tmp_path / "duplicate",
            shared_ledger=ledger,
            observed_at="2026-08-11T13:02:00Z",
        )


def test_invalid_financial_semantics_terminalizes_after_full_capture(
    basis: dict, tmp_path: Path
) -> None:
    issuance = _issue(basis)
    invalid = deepcopy(_valid_output())
    invalid["evidence_semantics"]["isg_profit_attribution_status"] = (
        "allowed_product_profit_proxy"
    )
    terminal = execute_live_canary(
        issuance=issuance,
        execution_authority=_execution_authority(issuance),
        decision=basis["decision"],
        clean_proof=basis["proof"],
        material=basis["material"],
        project_os_preflight=basis["preflight"],
        repo_root=ROOT,
        provider_call=lambda _request: {
            "status": "ok",
            "content": json.dumps(invalid, ensure_ascii=False),
            "finish_reason": "stop",
        },
        runtime_root=tmp_path / "invalid",
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "invalid.sqlite"),
        observed_at="2026-08-11T13:03:00Z",
    )
    assert terminal["status"] == "failed"
    assert terminal["terminal_phase"] == "contract_validation"
    assert terminal["terminal_code"] == "s3_repair_canary_evidence_semantics_invalid"
    capture = _load(
        tmp_path / "invalid/raw_model_only/calls/call_01/capture.json"
    )
    assert capture["provider_response"]["content"]


def test_credential_check_is_presence_only(basis: dict) -> None:
    profile = basis["material"]["profile"]
    assert credential_presence_only(
        profile=profile, environ={"DEEPSEEK_API_KEY": "fixture-secret"}
    ) == {
        "credential_env_name": "DEEPSEEK_API_KEY",
        "credential_present": True,
        "credential_value_read_output_or_persisted": False,
    }
