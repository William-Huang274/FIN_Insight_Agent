from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_six_case_local_evidence_pack import file_sha256  # noqa: E402
from sec_agent.s2_fixed_pack_live import (  # noqa: E402
    RUN_SCOPE,
    S2FixedPackLiveError,
    build_public_dell_canary_result,
    issue_dell_canary_authority,
    load_dell_fixed_pack_material,
    validate_clean_proof,
    validate_dell_canary_authority,
)
from sec_agent.s2_fixed_pack_research_runtime import (  # noqa: E402
    NODE_ORDER,
    issue_case_admission,
)


CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_fixed_pack_successor_clean_independent_proof_v1_0.json"
)
RUNTIME_PATH = ROOT / "src/sec_agent/s2_fixed_pack_research_runtime.py"
GIT = "4" * 40
NOW = "2026-08-10T10:30:00Z"
EXPIRES = "2026-08-10T14:30:00Z"


@pytest.fixture(scope="module")
def material():
    return load_dell_fixed_pack_material(
        repo_root=ROOT,
        contract_path=CONTRACT_PATH,
        profile_path=PROFILE_PATH,
    )


@pytest.fixture(scope="module")
def proof():
    value = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    validate_clean_proof(value)
    return value


def _authority(material: dict, proof: dict) -> dict:
    profile = material["profile"]
    admission = issue_case_admission(
        case_input=material["case_input"],
        profile=profile,
        execution_git_commit=GIT,
        runner_sha256=file_sha256(RUNTIME_PATH),
        contract_sha256=file_sha256(CONTRACT_PATH),
        profile_sha256=file_sha256(PROFILE_PATH),
        issued_at=NOW,
        expires_at=EXPIRES,
        run_nonce="live-authority-fixture",
        credential_present=True,
        execution_mode="live",
    )
    return issue_dell_canary_authority(
        admission=admission,
        clean_proof=proof,
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


def test_registered_scope_passes_without_external_blockers() -> None:
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    assert preflight["status"] == "pass"
    assert preflight["open_full_chain_blocker_count"] == 0


def test_dell_authority_is_one_case_thirteen_calls_no_promotion(
    material, proof
) -> None:
    authority = _authority(material, proof)
    assert authority["case_key"] == "DELL"
    assert authority["execution_ceiling"] == {
        "cases": 1,
        "provider_calls": len(NODE_ORDER),
        "model_calls": len(NODE_ORDER),
        "network_tool_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "business_promotions": 0,
    }
    validate_dell_canary_authority(
        authority,
        clean_proof=proof,
        case_input=material["case_input"],
        profile=material["profile"],
        repo_root=ROOT,
        observed_at=NOW,
    )


def test_authority_mutation_fails_closed(material, proof) -> None:
    authority = _authority(material, proof)
    changed = deepcopy(authority)
    changed["execution_ceiling"]["provider_calls"] = 14
    with pytest.raises(S2FixedPackLiveError) as exc:
        validate_dell_canary_authority(
            changed,
            clean_proof=proof,
            case_input=material["case_input"],
            profile=material["profile"],
            repo_root=ROOT,
            observed_at=NOW,
        )
    assert exc.value.code == "fixed_pack_live_authority_digest_or_scope_invalid"


def test_public_result_excludes_raw_model_outputs(material, proof, tmp_path) -> None:
    authority = _authority(material, proof)
    admission = authority["admission"]
    private = tmp_path / "terminal_with_receipt.json"
    private.write_text("{}\n", encoding="utf-8")
    terminal = {
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "case_key": "DELL",
        "case_input_digest": material["case_input"]["model_visible_digest"],
        "source_pack_digest": material["case_input"]["source_pack_digest"],
        "status": "completed_with_findings",
        "terminal_phase": "verifier",
        "terminal_code": "fixed_pack_chain_completed_raw_candidate_not_promoted",
        "observed_counts": {
            "provider_calls": 13,
            "model_calls": 13,
            "findings": 1,
        },
        "findings": [{"level": "L2", "code": "fixture_finding", "text": "private"}],
        "call_receipts": [
            {
                "call_id": "call_01",
                "node_key": "direct_baseline",
                "capture_digest": "5" * 64,
                "request_digest": "6" * 64,
                "status": "ok",
                "finish_reason": "stop",
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            }
        ],
        "same_input_pair_proven": True,
        "business_artifact_promoted": False,
        "qualified_human_acceptance_required": True,
        "terminal_digest": "7" * 64,
        "raw_outputs": {"secret": "must not become public"},
    }
    result = build_public_dell_canary_result(
        authority=authority,
        terminal=terminal,
        private_terminal_path=private,
        recorded_at=NOW,
    )
    serialized = json.dumps(result, ensure_ascii=False)
    assert "must not become public" not in serialized
    assert '"text": "private"' not in serialized
    assert result["finding_summary"]["codes"] == ["fixture_finding"]
    assert result["raw_model_output_public"] is False
