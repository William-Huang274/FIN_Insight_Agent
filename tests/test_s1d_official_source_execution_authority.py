from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_s1d_execution_authority_is_digest_bound_and_bounded() -> None:
    path = (
        ROOT
        / "configs"
        / "retrieval"
        / "fin_ia_0_1_3_s1d_official_source_execution_authority_v1_0.json"
    )
    authority = json.loads(path.read_text(encoding="utf-8"))
    bound = authority["bound_inputs"]

    for ref_key, digest_key in (
        ("business_disposition_ref", "business_disposition_sha256"),
        ("capture_plan_ref", "capture_plan_sha256"),
    ):
        bound_path = ROOT / bound[ref_key]
        assert hashlib.sha256(bound_path.read_bytes()).hexdigest() == bound[digest_key]

    budget = authority["execution_budget"]
    assert budget == {
        "attempt_id": "live-r1",
        "source_routes": 2,
        "network_attempts_maximum": 2,
        "retries": 0,
        "model_calls": 0,
        "broad_web_search_calls": 0,
        "credentials": "forbidden",
        "capture_before_parse": True,
    }
    assert authority["downstream_authority"]["parse_captured_pdf"] is False


def test_s1d_execution_authority_binds_current_implementation_commit() -> None:
    authority = json.loads(
        (
            ROOT
            / "configs"
            / "retrieval"
            / "fin_ia_0_1_3_s1d_official_source_execution_authority_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    bound_commit = authority["clean_implementation"]["git_commit"]
    assert subprocess.check_output(
        ["git", "cat-file", "-t", bound_commit],
        cwd=ROOT,
        text=True,
    ).strip() == "commit"
