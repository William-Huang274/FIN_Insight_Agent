from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s2_selected_evidence_numeric_cocompilation import (  # noqa: E402
    canonical_digest,
)
from sec_agent.s2_selected_evidence_numeric_natural_node_canary import (  # noqa: E402
    _normalized_text_sha256,
    compile_canary_material,
    load_canary_policy,
)
from sec_agent.s2_selected_evidence_numeric_natural_node_canary_live import (  # noqa: E402
    LIVE_EXECUTION_AUTHORITY_SCHEMA,
    LIVE_SCOPE,
    SelectedEvidenceNumericNaturalNodeCanaryLiveError,
    build_no_retry_provider_call,
    credential_presence_only,
    execute_live_canary,
    issue_live_canary_admission,
    validate_live_canary_issuance,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "policy_v1_0.json"
)
DECISION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_value_cost_risk_authority_decision_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "clean_independent_proof_v1_0.json"
)
IMPLEMENTATION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_live_"
    "minimum_zero_call_implementation_v1_0.json"
)
ISSUED_AT = "2026-08-11T10:00:00Z"
EXPIRES_AT = "2026-08-12T10:00:00Z"


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@pytest.fixture(scope="module")
def basis():
    policy = load_canary_policy(POLICY_PATH, repo_root=ROOT)
    material = compile_canary_material(policy=policy, repo_root=ROOT)
    decision = _load(DECISION_PATH)
    proof = _load(PROOF_PATH)
    preflight = run_project_os_preflight(ROOT, run_scope=LIVE_SCOPE)
    refs = (
        "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
        "configs/runtime/fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_policy_v1_0.json",
        "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json",
        "configs/releases/fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_clean_independent_proof_v1_0.json",
        "configs/releases/fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_live_value_cost_risk_authority_decision_v1_0.json",
        "src/sec_agent/s2_selected_evidence_numeric_natural_node_canary.py",
        "src/sec_agent/s2_selected_evidence_numeric_natural_node_canary_live.py",
    )
    source_bindings = [
        {
            "ref": ref,
            "normalized_text_sha256": _normalized_text_sha256(ROOT / ref),
        }
        for ref in refs
    ]
    credential = credential_presence_only(
        profile=material["profile"],
        environ={"DEEPSEEK_API_KEY": "fixture-presence-only-value"},
    )
    issuance = issue_live_canary_admission(
        decision=decision,
        clean_proof=proof,
        material=material,
        implementation_commit="a" * 40,
        source_bindings=source_bindings,
        project_os_preflight=preflight,
        credential_preflight=credential,
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        run_nonce="0123456789abcdef0123456789abcdef",
        user_authority="User said continue; issuance only, no Provider execution.",
    )
    return {
        "material": material,
        "decision": decision,
        "proof": proof,
        "preflight": preflight,
        "source_bindings": source_bindings,
        "credential": credential,
        "issuance": issuance,
    }


def _valid_output() -> dict:
    return {
        "schema_version": (
            "fin_ia_0_1_3_s2_demand_authenticity_numeric_view_atom_"
            "canary_output_v1_0"
        ),
        "case_key": "DELL",
        "node_id": "dell_demand_authenticity_numeric_view_atom_canary_v1",
        "judgment": "supported_with_limits",
        "support_atom": {
            "text": (
                "Dell在FY2027 Q1披露AI服务器收入$16.1 billion，customer count "
                "surpassed 5,000，并披露AI订单$24.4 billion；这些是当前需求存在的直接指标。"
            ),
            "epistemic_state": "fact_supported",
            "evidence_refs": ["E022"],
            "numeric_refs": [
                "NUM:DELL:AI_SERVER_REVENUE:C4947C75D942",
                "NUM:DELL:CUSTOMER_COUNT:8C7F5A41CBF9",
                "NUM:DELL:AI_ORDERS:66F359E8F5E4",
            ],
        },
        "counterevidence_atom": {
            "text": (
                "E018显示竞争对手客户仍在消化此前订单，E023显示内存不确定性可能推动"
                "提前锁定基础设施；二者不能当成Dell直接量化需求证明。"
            ),
            "epistemic_state": "bounded_inference",
            "evidence_refs": ["E018", "E023"],
            "numeric_refs": [],
        },
        "boundary_atom": {
            "text": (
                "这些披露不足以证明订单持续转化，也不能证明客户集中度、产品毛利或"
                "终端需求的可持续性。"
            ),
            "epistemic_state": "cannot_infer",
            "evidence_refs": ["E022", "E018", "E023"],
            "numeric_refs": [],
        },
        "used_numeric_refs": [
            "NUM:DELL:AI_SERVER_REVENUE:C4947C75D942",
            "NUM:DELL:CUSTOMER_COUNT:8C7F5A41CBF9",
            "NUM:DELL:AI_ORDERS:66F359E8F5E4",
        ],
    }


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


def test_live_scope_is_registered_and_project_os_passes(basis) -> None:
    assert basis["preflight"]["status"] == "pass"
    assert basis["preflight"]["run_scope"] == LIVE_SCOPE
    assert basis["preflight"]["open_full_chain_blocker_count"] == 0


def test_implementation_result_is_canonical_and_honest_zero_call() -> None:
    result = _load(IMPLEMENTATION_PATH)
    body = {key: value for key, value in result.items() if key != "result_digest"}
    assert result["result_digest"] == canonical_digest(body)
    assert result["stage_acceptance"]["fresh_live_admission_issued"] is False
    assert result["stage_acceptance"]["natural_model_canary"] is False
    assert result["observed_calls"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
        "fixture_provider_callbacks": 1,
    }


def test_credential_preflight_is_presence_only_and_adapter_is_no_retry(basis) -> None:
    assert basis["credential"] == {
        "credential_env_name": "DEEPSEEK_API_KEY",
        "credential_present": True,
        "credential_value_read_output_or_persisted": False,
    }
    serialized = json.dumps(basis["issuance"], ensure_ascii=False)
    assert "fixture-presence-only-value" not in serialized
    provider = build_no_retry_provider_call(
        profile=basis["material"]["profile"],
        environ={"DEEPSEEK_API_KEY": "fixture-presence-only-value"},
    )
    assert callable(provider)


def test_live_issuance_is_fresh_unconsumed_and_does_not_authorize_execution(
    basis,
) -> None:
    issuance = basis["issuance"]
    validate_live_canary_issuance(
        issuance,
        decision=basis["decision"],
        clean_proof=basis["proof"],
        material=basis["material"],
        project_os_preflight=basis["preflight"],
        repo_root=ROOT,
    )
    assert issuance["status"] == "issued_unconsumed_execution_not_authorized"
    assert issuance["admission"]["run_scope"] == LIVE_SCOPE
    assert issuance["admission"]["authority_kind"] != "zero_call_test_fixture_only"
    assert issuance["admission"]["execution_enabled_by_issuance"] is False
    assert issuance["observed_counts"]["provider_calls"] == 0
    assert issuance["observed_counts"]["model_calls"] == 0


def test_fixture_or_mutated_admission_cannot_masquerade_as_live(basis) -> None:
    mutated = deepcopy(basis["issuance"])
    mutated["admission"]["authority_kind"] = "zero_call_test_fixture_only"
    body = {
        key: value
        for key, value in mutated["admission"].items()
        if key != "admission_digest"
    }
    mutated["admission"]["admission_digest"] = canonical_digest(body)
    outer = {
        key: value for key, value in mutated.items() if key != "issuance_digest"
    }
    mutated["issuance_digest"] = canonical_digest(outer)
    with pytest.raises(SelectedEvidenceNumericNaturalNodeCanaryLiveError) as exc:
        validate_live_canary_issuance(
            mutated,
            decision=basis["decision"],
            clean_proof=basis["proof"],
            material=basis["material"],
            project_os_preflight=basis["preflight"],
            repo_root=ROOT,
        )
    assert exc.value.code == "live_canary_admission_identity_invalid"


def test_source_binding_drift_fails_closed(basis) -> None:
    mutated = deepcopy(basis["issuance"])
    mutated["authority"]["source_bindings"][0]["normalized_text_sha256"] = "0" * 64
    authority_body = {
        key: value
        for key, value in mutated["authority"].items()
        if key != "authority_digest"
    }
    mutated["authority"]["authority_digest"] = canonical_digest(authority_body)
    mutated["admission"]["authority_digest"] = mutated["authority"]["authority_digest"]
    admission_body = {
        key: value
        for key, value in mutated["admission"].items()
        if key != "admission_digest"
    }
    mutated["admission"]["admission_digest"] = canonical_digest(admission_body)
    outer = {
        key: value for key, value in mutated.items() if key != "issuance_digest"
    }
    mutated["issuance_digest"] = canonical_digest(outer)
    with pytest.raises(SelectedEvidenceNumericNaturalNodeCanaryLiveError) as exc:
        validate_live_canary_issuance(
            mutated,
            decision=basis["decision"],
            clean_proof=basis["proof"],
            material=basis["material"],
            project_os_preflight=basis["preflight"],
            repo_root=ROOT,
        )
    assert exc.value.code == "live_canary_source_binding_sha256_drift"


def test_live_runtime_requires_separate_execution_authority_before_provider(
    basis, tmp_path
) -> None:
    calls: list[dict] = []
    invalid_authority = _execution_authority(basis["issuance"])
    invalid_authority["execute_provider_call"] = False
    with pytest.raises(SelectedEvidenceNumericNaturalNodeCanaryLiveError) as exc:
        execute_live_canary(
            issuance=basis["issuance"],
            execution_authority=invalid_authority,
            decision=basis["decision"],
            clean_proof=basis["proof"],
            material=basis["material"],
            project_os_preflight=basis["preflight"],
            repo_root=ROOT,
            provider_call=lambda request: calls.append(dict(request)) or {},
            runtime_root=tmp_path / "blocked-attempt",
            shared_ledger=SharedAdmissionConsumptionLedger(
                tmp_path / "shared/blocked-ledger.sqlite"
            ),
            observed_at=ISSUED_AT,
        )
    assert exc.value.code == "live_canary_execution_authority_invalid"
    assert calls == []
    assert not (tmp_path / "blocked-attempt").exists()


def test_separately_authorized_fake_live_path_is_capture_first_and_exact_once(
    basis, tmp_path
) -> None:
    calls: list[dict] = []

    def provider(request):
        calls.append(dict(request))
        return {
            "status": "ok",
            "content": json.dumps(_valid_output(), ensure_ascii=False),
            "finish_reason": "stop",
            "input_tokens": 1200,
            "output_tokens": 220,
            "total_tokens": 1420,
        }

    terminal = execute_live_canary(
        issuance=basis["issuance"],
        execution_authority=_execution_authority(basis["issuance"]),
        decision=basis["decision"],
        clean_proof=basis["proof"],
        material=basis["material"],
        project_os_preflight=basis["preflight"],
        repo_root=ROOT,
        provider_call=provider,
        runtime_root=tmp_path / "fake-live-attempt",
        shared_ledger=SharedAdmissionConsumptionLedger(
            tmp_path / "shared/fake-live-ledger.sqlite"
        ),
        observed_at=ISSUED_AT,
    )
    assert len(calls) == 1
    assert terminal["status"] == "completed"
    assert terminal["run_scope"] == LIVE_SCOPE
    assert terminal["business_artifact_promotion"] is False
    assert (
        tmp_path
        / "fake-live-attempt/raw_model_only/calls/call_01/capture.json"
    ).is_file()
