from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06_unified_supervisor_"
    "independent_fresh_zero_call_proof_result_v1_0.json"
)


def _digest(value: dict) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_fresh_proof_binds_clean_commit_two_workers_and_real_inputs() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "result_digest"}
    assert result["result_digest"] == _digest(body)
    assert result["status"].startswith("pass_two_clean_commit_archives")
    assert result["source_commit"] == {
        "clean": True,
        "commit": "60b66bc9cdda6ac4130c1e2f44d357313bdac0ef",
        "synced": True,
        "upstream_commit": "60b66bc9cdda6ac4130c1e2f44d357313bdac0ef",
    }
    proof = result["independent_proof"]
    assert proof["clean_git_archives"] == proof["fresh_python_processes"] == 2
    assert proof["distinct_disposable_roots"] == 2
    assert proof["normalized_outputs_equal"] is True
    assert proof["worker_result"]["pytest"]["passed"] == 24
    assert proof["worker_result"]["pytest"]["failed"] == 0
    assert proof["worker_result"]["pytest"]["skipped"] == 0

    matrix = proof["worker_result"]["real_frozen_input_matrix"]
    assert {
        case_key: (
            row["supervisor_request_characters"],
            row["node_directives"],
            row["provider_calls"],
        )
        for case_key, row in matrix.items()
    } == {
        "DELL": (33590, 6, 8),
        "MU": (28104, 8, 10),
        "NVDA": (35650, 9, 10),
    }
    assert all(row["provider_execution_authorized"] is False for row in matrix.values())


def test_proof_preserves_raw_and_does_not_promote_engineering_to_product() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    audit = result["source_and_target_read_only_audit"]
    assert audit["source_raw_before"] == audit["source_raw_after"]
    assert audit["target_supervision_before"] == audit["target_supervision_after"]
    assert audit["source_raw_unchanged"] is True
    assert audit["target_supervision_unchanged"] is True

    projection = result["independent_proof"]["clean_worktree_byte_projection"]
    assert len(projection) == 1
    assert next(iter(projection.values()))["normalized_content_matches_git_blob"] is True

    assert set(result["observed_counts"].values()) == {0}
    boundary = result["acceptance_boundary"]
    assert boundary["S2_06_shared_runtime_fresh_reproducibility"] == "pass"
    assert boundary["supervised_recoverability"] == "not_proven"
    assert boundary["corrected_report_quality"] == "not_measured"
    assert boundary["formal_hidden_score"] is False
    assert boundary["business_promotion"] is False
    assert result["next_action_authorized"] is False
    assert result["next_action"].endswith("SUPERVISOR-ADMISSION-AUTHORITY-DECISION")
