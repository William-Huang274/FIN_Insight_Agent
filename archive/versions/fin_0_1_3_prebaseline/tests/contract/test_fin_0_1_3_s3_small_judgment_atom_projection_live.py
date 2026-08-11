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
)
from sec_agent.s3_small_judgment_atom_projection import (  # noqa: E402
    compile_small_judgment_material,
    load_small_judgment_projection_policy,
)
from sec_agent.s3_small_judgment_atom_projection_live import (  # noqa: E402
    LIVE_EXECUTION_AUTHORITY_SCHEMA,
    LIVE_SCOPE,
    S3SmallJudgmentAtomLiveError,
    credential_presence_only,
    execute_successor_live_canary,
    issue_successor_live_admission,
    validate_successor_live_issuance,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_policy_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_clean_independent_"
    "proof_v1_0.json"
)
DECISION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_small_judgment_atom_successor_natural_canary_"
    "value_cost_risk_decision_v1_0.json"
)
SOURCE_REFS = (
    "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
    "configs/runtime/fin_ia_0_1_3_s3_small_judgment_atom_projection_policy_v1_0.json",
    "src/sec_agent/s3_small_judgment_atom_projection.py",
    "src/sec_agent/s3_small_judgment_atom_projection_live.py",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_output() -> dict:
    return {
        "schema_version": "fin_ia_0_1_3_s3_small_judgment_atom_output_v1_0",
        "case_key": "DELL",
        "node_id": "dell_value_profit_small_judgment_atom_v1",
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
        "used_numeric_refs": [
            "NUM:DELL:OPERATING_MARGIN_TARGET:2894219F450D"
        ],
        "profitability_direction": (
            "management_target_consistent_product_profit_unproven"
        ),
        "attribution_boundary": "segment_profit_not_product_profit",
        "mechanism_atom": (
            "E021 supports bounded operating profitability while E008 limits "
            "transmission to product profit."
        ),
        "boundary_atom": (
            "E002 prevents segment income from replacing product profit; cash "
            "conversion remains open."
        ),
    }


@pytest.fixture(scope="module")
def basis() -> dict:
    policy = load_small_judgment_projection_policy(POLICY_PATH, repo_root=ROOT)
    material = compile_small_judgment_material(policy=policy, repo_root=ROOT)
    return {
        "material": material,
        "proof": _load(PROOF_PATH),
        "decision": _load(DECISION_PATH),
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
    profile = basis["material"]["predecessor"]["profile"]
    return issue_successor_live_admission(
        decision=basis["decision"],
        clean_proof=basis["proof"],
        material=basis["material"],
        implementation_commit="1" * 40,
        source_bindings=basis["bindings"],
        project_os_preflight=basis["preflight"],
        credential_preflight=credential_presence_only(
            profile=profile, environ={"DEEPSEEK_API_KEY": "fixture-secret"}
        ),
        issued_at="2026-08-11T16:00:00Z",
        expires_at="2026-08-12T16:00:00Z",
        run_nonce="0123456789abcdef0123456789abcdef",
        user_authority="fixture issuance only; execution separate",
    )


def _execution_authority(issuance: dict) -> dict:
    body = {
        "schema_version": LIVE_EXECUTION_AUTHORITY_SCHEMA,
        "status": "authorized_single_exact_once_successor_natural_canary_execution",
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


def test_issuance_is_fresh_exact_once_and_execution_separate(basis: dict) -> None:
    issuance = _issue(basis)
    validate_successor_live_issuance(
        issuance,
        decision=basis["decision"],
        clean_proof=basis["proof"],
        material=basis["material"],
        project_os_preflight=basis["preflight"],
        repo_root=ROOT,
        observed_at="2026-08-11T16:00:01Z",
    )
    assert issuance["status"] == "issued_unconsumed_execution_not_authorized"
    assert issuance["admission"]["run_scope"] == LIVE_SCOPE
    assert issuance["admission"]["execution_authorized"] is False
    assert issuance["observed_counts"]["provider_calls"] == 0
    with pytest.raises(S3SmallJudgmentAtomLiveError, match="expired"):
        validate_successor_live_issuance(
            issuance,
            decision=basis["decision"],
            clean_proof=basis["proof"],
            material=basis["material"],
            project_os_preflight=basis["preflight"],
            repo_root=ROOT,
            observed_at="2026-08-12T16:00:00Z",
        )


def test_success_terminal_materializes_parsed_validated_projection_and_one_call(
    basis: dict, tmp_path: Path
) -> None:
    issuance = _issue(basis)
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
    terminal = execute_successor_live_canary(
        issuance=issuance,
        execution_authority=_execution_authority(issuance),
        decision=basis["decision"],
        clean_proof=basis["proof"],
        material=basis["material"],
        project_os_preflight=basis["preflight"],
        repo_root=ROOT,
        provider_call=provider,
        runtime_root=tmp_path / "attempt",
        shared_ledger=ledger,
        observed_at="2026-08-11T16:01:00Z",
    )
    assert len(calls) == 1
    assert terminal["status"] == "completed"
    assert terminal["terminal_code"] == "s3_small_atom_live_pass"
    assert terminal["parsed_output_ref"] == "parsed/small_judgment_output.json"
    assert terminal["validated_output_ref"] == (
        "validated/small_judgment_output.json"
    )
    assert terminal["projection_ref"] == "validated/projection.json"
    assert terminal["business_artifact_promotion"] is False
    assert (tmp_path / "attempt/validated/successor_program.json").is_file()
    with pytest.raises(SharedAdmissionLedgerError):
        execute_successor_live_canary(
            issuance=issuance,
            execution_authority=_execution_authority(issuance),
            decision=basis["decision"],
            clean_proof=basis["proof"],
            material=basis["material"],
            project_os_preflight=basis["preflight"],
            repo_root=ROOT,
            provider_call=provider,
            runtime_root=tmp_path / "duplicate",
            shared_ledger=ledger,
            observed_at="2026-08-11T16:02:00Z",
        )


def test_semantic_failure_keeps_parsed_and_never_claims_validated(
    basis: dict, tmp_path: Path
) -> None:
    issuance = _issue(basis)
    invalid = deepcopy(_valid_output())
    invalid["profitability_direction"] = "cannot_infer"
    terminal = execute_successor_live_canary(
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
        observed_at="2026-08-11T16:03:00Z",
    )
    assert terminal["status"] == "failed"
    assert terminal["terminal_phase"] == "contract_validation"
    assert terminal["terminal_code"] == "s3_small_atom_financial_boundary_invalid"
    assert terminal["parsed_output_ref"] == "parsed/small_judgment_output.json"
    assert terminal["validated_output_ref"] is None
    assert terminal["projection_ref"] is None
    assert (tmp_path / "invalid/parsed/small_judgment_output.json").is_file()
    assert not (tmp_path / "invalid/validated").exists()


def test_source_binding_drift_fails_before_execution(basis: dict) -> None:
    issuance = _issue(basis)
    drifted = deepcopy(issuance)
    drifted["authority"]["source_bindings"][0]["normalized_text_sha256"] = "0" * 64
    authority_body = {
        key: value
        for key, value in drifted["authority"].items()
        if key != "authority_digest"
    }
    drifted["authority"]["authority_digest"] = canonical_digest(authority_body)
    drifted["admission"]["authority_digest"] = drifted["authority"][
        "authority_digest"
    ]
    admission_body = {
        key: value
        for key, value in drifted["admission"].items()
        if key != "admission_digest"
    }
    drifted["admission"]["admission_digest"] = canonical_digest(admission_body)
    issuance_body = {
        key: value for key, value in drifted.items() if key != "issuance_digest"
    }
    drifted["issuance_digest"] = canonical_digest(issuance_body)
    with pytest.raises(S3SmallJudgmentAtomLiveError, match="source_binding_drift"):
        validate_successor_live_issuance(
            drifted,
            decision=basis["decision"],
            clean_proof=basis["proof"],
            material=basis["material"],
            project_os_preflight=basis["preflight"],
            repo_root=ROOT,
            observed_at="2026-08-11T16:00:01Z",
        )
