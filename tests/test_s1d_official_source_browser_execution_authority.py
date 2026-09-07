from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_browser_execution_authority_binds_r1_and_browser_plan() -> None:
    authority = json.loads(
        (
            ROOT
            / "configs"
            / "retrieval"
            / "fin_ia_0_1_3_s1d_official_source_browser_execution_authority_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    bound = authority["bound_inputs"]
    for ref_key, digest_key in (
        ("r1_result_ref", "r1_result_sha256"),
        ("browser_capture_plan_ref", "browser_capture_plan_sha256"),
    ):
        path = ROOT / bound[ref_key]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == bound[digest_key]

    assert authority["execution_budget"] == {
        "attempt_id": "live-r2",
        "routes": 2,
        "document_network_attempts_maximum": 4,
        "retries": 0,
        "model_calls": 0,
        "search_calls": 0,
        "credentials": "forbidden",
    }
    assert authority["downstream_authority"]["parse_on_success"] is False
