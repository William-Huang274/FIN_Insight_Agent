from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest
from scripts.releases.assess_fin_ia_0_1_2_s3_t04_nvda_replacement_product import assess


BASELINE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t04_nvda_same_input_"
    "deterministic_baseline_v1_0.json"
)
CLOSEOUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t04_nvda_paired_assessment_"
    "owner_rejection_and_s3_closeout_v1_0.json"
)
EXECUTION_AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_exact_live_"
    "execution_authority_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_current_exact_product_recomputes_L1_and_fails_only_product_quality() -> None:
    result = assess()
    assert result["L1_integrity"]["status"] == "pass"
    assert result["L1_integrity"]["new_L1_found"] is False
    assert result["L2_evidence_reliability_and_coverage"]["fact_supported_cells"] == 1
    assert result["L3_agent_gain"]["structured_followup_tasks"] == 7
    assert result["L4_delivery"]["status"] == "fail_not_analyst_ready"
    assert result["owner_decision"]["S3_T03"] == "pass_closed"
    assert result["owner_decision"]["S3_T04"] == "honest_block_owner_reject"
    assert result["owner_decision"]["third_exact_or_runtime_repair"] is False


def test_durable_baseline_and_closeout_digests_are_self_consistent() -> None:
    baseline = _load(BASELINE)
    closeout = _load(CLOSEOUT)
    assert baseline["baseline_digest"] == canonical_digest(
        {key: value for key, value in baseline.items() if key != "baseline_digest"}
    )
    assert closeout["assessment_digest"] == canonical_digest(
        {key: value for key, value in closeout.items() if key != "assessment_digest"}
    )
    assert closeout["paired_input"]["complete_input_digest"] == baseline[
        "complete_input_digest"
    ]


def test_terminal_child_entrypoint_and_execution_authority_code_hashes_match() -> None:
    authority = _load(EXECUTION_AUTHORITY)
    launch = _load(
        ROOT
        / ".codex_runtime/fin012-s3-t03-nvda-replacement-r2-supervision/launch-receipt.json"
    )
    assert launch["command_projection"][1] == (
        "run_fin_ia_0_1_2_s3_t03_nvda_replacement_controlled_successor.py"
    )
    for ref, expected in authority["code_bindings"].items():
        assert hashlib.sha256((ROOT / ref).read_bytes()).hexdigest() == expected
