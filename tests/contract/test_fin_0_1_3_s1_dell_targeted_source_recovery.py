from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_dell_targeted_source_recovery import (  # noqa: E402
    DellTargetedSourceRecoveryError,
    compile_recovery_result,
    load_recovery_policy,
    validate_recovery_result,
)
from sec_agent.s1_six_case_local_evidence_pack import file_sha256  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_targeted_source_recovery_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_targeted_source_recovery_result_v1_0.json"
)


def _synthetic_capture(tmp_path: Path) -> tuple[Path, str, str]:
    text = (
        "<html><body>Earlier mature-node discussion promised enough capacity. "
        + ("unrelated material " * 300)
        + "For advanced packaging, very large reticle size CoWoS lets us give "
        "enough capacity to customers. Today the main supply remains large-sized CoWoS."
        "</body></html>"
    )
    body = text.encode("utf-8")
    body_digest = hashlib.sha256(body).hexdigest()
    capture = {
        "schema_version": "fin_ia_0_1_3_official_source_capture_v1_0",
        "capture_kind": "source_response",
        "status_code": 200,
        "final_url": "https://investor.tsmc.com/fixture",
        "headers": {"content-type": "text/html"},
        "redirect_chain": [],
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_sha256": body_digest,
        "body_bytes": len(body),
        "capture_before_parse": True,
        "credential_cookie_authorization_present": False,
    }
    path = tmp_path / "capture.json"
    path.write_text(
        json.dumps(capture, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path, file_sha256(path), body_digest


def test_synthetic_replay_recovers_coherent_fragment_and_refuses_authority(
    tmp_path: Path,
) -> None:
    policy = deepcopy(load_recovery_policy(POLICY_PATH, repo_root=ROOT))
    capture_path, capture_digest, body_digest = _synthetic_capture(tmp_path)
    policy["tsmc_capture_replay"].update(
        {
            "private_capture_ref": str(capture_path),
            "capture_digest": capture_digest,
            "body_sha256": body_digest,
            "max_anchor_span": 500,
        }
    )
    result = compile_recovery_result(
        policy=policy,
        repo_root=ROOT,
        recorded_at="2026-08-10T15:45:00Z",
    )
    replay = result["tsmc_capture_replay"]
    assert replay["selected_coherent_anchor_span"] < 300
    assert replay["legacy_first_occurrence_anchor_span"] > 4000
    assert replay["character_ceiling_increased"] is False
    assert result["authority_decision"]["status"] == "not_ready"
    assert result["authority_decision"]["blocking_gates"] == [
        "market_point_in_time_executable_exact_date_request_unproven"
    ]
    assert result["observed_counts"]["network_calls"] == 0


def test_materialized_real_replay_result_is_digest_valid() -> None:
    policy = load_recovery_policy(POLICY_PATH, repo_root=ROOT)
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    validate_recovery_result(result, policy=policy)
    assert result["tsmc_capture_replay"]["capture_digest"] == (
        "39805472768ede6729a8c4dd168e22d5653ec5eb7560c1c55f394787c891352d"
    )
    assert result["market_point_in_time_contract"]["expected_close_value_bound"] is False


def test_recovery_result_mutation_fails_closed() -> None:
    policy = load_recovery_policy(POLICY_PATH, repo_root=ROOT)
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    result["authority_decision"]["status"] = "ready"
    with pytest.raises(
        DellTargetedSourceRecoveryError,
        match="dell_targeted_recovery_result_invalid",
    ):
        validate_recovery_result(result, policy=policy)
