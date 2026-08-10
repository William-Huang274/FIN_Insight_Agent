from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_six_case_local_evidence_pack import (  # noqa: E402
    canonical_digest,
    file_sha256,
)
from sec_agent.s2_fixed_pack_capture_reuse_successor import (  # noqa: E402
    compile_successor_case_input,
    load_predecessor_import_bundle,
    load_successor_contract,
)
from sec_agent.s2_fixed_pack_capture_reuse_successor_live import (  # noqa: E402
    RUN_SCOPE,
    S2FixedPackSuccessorLiveError,
    build_public_successor_result,
    issue_successor_authority,
    validate_clean_proof,
    validate_successor_authority,
)
from sec_agent.s2_fixed_pack_capture_reuse_successor_runtime import (  # noqa: E402
    issue_successor_admission,
)
from sec_agent.s2_fixed_pack_research import (  # noqa: E402
    compile_six_case_model_inputs,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    load_frozen_local_packs,
)


BASE_CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
SUCCESSOR_CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_dell_fixed_pack_capture_reuse_successor_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)
RUNTIME_PATH = ROOT / "src/sec_agent/s2_fixed_pack_capture_reuse_successor_runtime.py"
PROOF_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_dell_capture_reuse_successor_clean_independent_proof_v1_0.json"
)
AUTHORITY_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_dell_capture_reuse_successor_authority_v1_0.json"
)
HASH = "1" * 64
GIT = "2" * 40
NOW = "2026-08-10T10:00:00Z"
EXPIRES = "2026-08-10T14:00:00Z"


@pytest.fixture(scope="module")
def material():
    base_contract = load_fixed_pack_contract(BASE_CONTRACT_PATH, repo_root=ROOT)
    profile = load_fixed_pack_profile(PROFILE_PATH)
    packs = load_frozen_local_packs(contract=base_contract, repo_root=ROOT)
    inputs, _result = compile_six_case_model_inputs(
        contract=base_contract, profile=profile, packs=packs
    )
    base = next(row for row in inputs if row["case_key"] == "DELL")
    successor_contract = load_successor_contract(
        SUCCESSOR_CONTRACT_PATH, repo_root=ROOT
    )
    return {
        "profile": profile,
        "successor": compile_successor_case_input(
            base_case_input=base,
            contract=successor_contract,
            profile=profile,
        ),
        "predecessor": load_predecessor_import_bundle(
            contract=successor_contract, repo_root=ROOT
        ),
    }


def _proof() -> dict:
    body = {
        "schema_version": (
            "fin_ia_0_1_3_s2_dell_capture_reuse_successor_clean_independent_proof_v1_0"
        ),
        "status": (
            "clean_independent_dell_capture_reuse_successor_zero_call_proof_passed"
        ),
        "fresh_worker_count": 2,
        "workers_byte_equivalent": True,
        "credential_environment_scrubbed": True,
        "socket_blocked_in_workers": True,
        "predecessor_imported_nodes": [
            {"node_key": f"node-{index}"} for index in range(5)
        ],
        "failed_predecessor_node": {"promoted_as_usable_output": False},
        "terminal": {
            "status": "completed",
            "observed_counts": {
                "imported_usable_nodes": 5,
                "successor_provider_calls": 8,
                "combined_provider_attempts": 14,
                "logical_outputs_present": 13,
            },
            "logical_node_indices": list(range(6, 14)),
            "business_artifact_promoted": False,
        },
        "observed_counts_across_workers": {
            "real_provider_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "retries": 0,
        },
    }
    return {**body, "proof_digest": canonical_digest(body)}


def _authority(material: dict) -> dict:
    admission = issue_successor_admission(
        case_input=material["successor"],
        predecessor_bundle=material["predecessor"],
        profile=material["profile"],
        execution_git_commit=GIT,
        runtime_sha256=HASH,
        runner_sha256=HASH,
        successor_contract_sha256=HASH,
        base_contract_sha256=HASH,
        profile_sha256=HASH,
        issued_at=NOW,
        expires_at=EXPIRES,
        run_nonce="successor-live-test",
        credential_present=True,
        execution_mode="live",
    )
    return issue_successor_authority(
        admission=admission,
        clean_proof=_proof(),
        implementation_commit=GIT,
        implementation_bindings=[
            {
                "ref": RUNTIME_PATH.relative_to(ROOT).as_posix(),
                "sha256": file_sha256(RUNTIME_PATH),
            }
        ],
        project_os_preflight={
            "status": "pass",
            "run_scope": RUN_SCOPE,
            "open_full_chain_blocker_count": 0,
        },
        user_authority="bounded unit-test authority",
        recorded_at=NOW,
    )


def test_clean_proof_and_authority_bind_only_eight_new_calls(material) -> None:
    proof = _proof()
    validate_clean_proof(proof)
    authority = _authority(material)
    assert authority["execution_ceiling"] == {
        "cases": 1,
        "predecessor_imported_usable_nodes": 5,
        "successor_provider_calls": 8,
        "successor_model_calls": 8,
        "combined_provider_attempts": 14,
        "logical_node_outputs": 13,
        "network_tool_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "business_promotions": 0,
    }
    validate_successor_authority(
        authority,
        clean_proof=proof,
        case_input=material["successor"],
        predecessor_bundle=material["predecessor"],
        profile=material["profile"],
        repo_root=ROOT,
        observed_at=NOW,
    )


def test_committed_clean_proof_is_valid_and_bound_to_real_predecessor() -> None:
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    validate_clean_proof(proof)
    assert proof["execution_git_commit"] == (
        "e9090819996be2714a563f1b5b5da6087ca7d199"
    )
    assert proof["proof_digest"] == (
        "a9aef287b10204a5ed2f62d25953f3184f1ff41b1d306be650b706c33210789c"
    )
    assert proof["predecessor_terminal_digest"] == (
        "2ae7ebf162a1b600a3bc2818982ed8b6968f281a0ca914ce5250aa4bad47ab58"
    )
    assert proof["terminal"]["same_input_pair_proven"] is False


def test_issued_authority_is_current_bound_and_unconsumed(material) -> None:
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    authority = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    assert authority["status"] == "issued_unconsumed"
    assert authority["implementation_commit"] == (
        "e08dbc9a46e9e1c05eaa53187270d1ccb9273b49"
    )
    assert authority["authority_digest"] == (
        "f53b343f8ca02ffc70aaf6c075ea06d77eaec412e7ab0d764dea4efe96d09ae0"
    )
    validate_successor_authority(
        authority,
        clean_proof=proof,
        case_input=material["successor"],
        predecessor_bundle=material["predecessor"],
        profile=material["profile"],
        repo_root=ROOT,
        observed_at=authority["recorded_at"],
    )


def test_authority_mutation_fails_closed(material) -> None:
    changed = deepcopy(_authority(material))
    changed["execution_ceiling"]["successor_provider_calls"] = 9
    with pytest.raises(S2FixedPackSuccessorLiveError) as exc:
        validate_successor_authority(
            changed,
            clean_proof=_proof(),
            case_input=material["successor"],
            predecessor_bundle=material["predecessor"],
            profile=material["profile"],
            repo_root=ROOT,
            observed_at=NOW,
        )
    assert exc.value.code == (
        "fixed_pack_successor_live_authority_digest_or_scope_invalid"
    )


def test_public_result_excludes_raw_outputs_and_finding_text(material, tmp_path) -> None:
    authority = _authority(material)
    private = tmp_path / "terminal_with_receipt.json"
    private.write_text("{}\n", encoding="utf-8")
    terminal = {
        "run_id": authority["admission"]["run_id"],
        "attempt_id": authority["admission"]["attempt_id"],
        "case_key": "DELL",
        "base_case_input_digest": material["successor"][
            "base_model_visible_digest"
        ],
        "successor_case_input_digest": material["successor"][
            "model_visible_digest"
        ],
        "numeric_authority_digest": material["successor"]["numeric_authority"][
            "numeric_authority_digest"
        ],
        "source_pack_digest": material["successor"]["source_pack_digest"],
        "predecessor": {
            "run_id": "old",
            "attempt_id": "old-attempt",
            "terminal_digest": "3" * 64,
            "import_bundle_digest": "4" * 64,
            "imported_node_lineage": [{"node_key": str(index)} for index in range(5)],
            "failed_attempt_evidence": {
                "node_key": "specialist::financial_transmission_profit_and_cash",
                "promoted_as_usable_output": False,
            },
            "usage": {"provider_calls": 6},
        },
        "status": "completed_with_findings",
        "terminal_phase": "verifier",
        "terminal_code": "fixture",
        "observed_counts": {"successor_provider_calls": 8},
        "successor_usage": {"provider_calls": 8},
        "cumulative_usage": {"provider_attempts": 14},
        "successor_call_receipts": [
            {
                "call_id": "call_01",
                "logical_node_index": 6,
                "node_key": "specialist::financial_transmission_profit_and_cash",
                "capture_digest": "5" * 64,
                "request_digest": "6" * 64,
                "status": "ok",
                "finish_reason": "stop",
            }
        ],
        "findings": [
            {"level": "L2", "code": "fixture_finding", "text": "private text"}
        ],
        "same_evidence_pack_proven": True,
        "same_input_pair_proven": False,
        "paired_assessment_eligible": False,
        "paired_baseline_required_later": True,
        "business_artifact_promoted": False,
        "qualified_human_acceptance_required": True,
        "terminal_digest": "7" * 64,
        "raw_outputs": {"secret": "must not become public"},
    }
    result = build_public_successor_result(
        authority=authority,
        terminal=terminal,
        private_terminal_path=private,
        recorded_at=NOW,
    )
    serialized = json.dumps(result, ensure_ascii=False)
    assert "must not become public" not in serialized
    assert "private text" not in serialized
    assert result["finding_summary"]["codes"] == ["fixture_finding"]
    assert result["predecessor"]["imported_node_count"] == 5
    assert result["same_input_pair_proven"] is False
