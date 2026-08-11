from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.audit_fin_ia_0_1_s3_t09_nullable_owner_supervision_v2_final_exact_live_failure import (
    ADMISSION_DIGEST,
    NEXT_ACTION,
    OUTPUT,
    audit,
)


def test_final_exact_live_failure_audit_matches_tracked_result() -> None:
    expected = json.loads(OUTPUT.read_text(encoding="utf-8"))
    actual = audit()
    digest_keys = (
        "canonical_database_sha256",
        "canonical_object_tree_sha256",
    )
    historical_digests = {
        key: expected["canonical_terminal_truth"].pop(key)
        for key in digest_keys
    }
    current_digests = {
        key: actual["canonical_terminal_truth"].pop(key)
        for key in digest_keys
    }

    assert actual == expected
    assert all(len(value) == 64 for value in historical_digests.values())
    assert all(len(value) == 64 for value in current_digests.values())
    assert current_digests != historical_digests


def test_final_exact_live_stops_before_t09_acceptance() -> None:
    result = audit()
    assert result["identity"]["admission_digest"] == ADMISSION_DIGEST
    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    assert result["acceptance"] == {
        "RC_P38_053_supervision_v2_fresh_live_proven": True,
        "RC_P36_052_nullable_owner_v2_live_reached": False,
        "nine_artifact_product_complete": False,
        "paired_comparison_performed": False,
        "owner_acceptance_performed": False,
        "S3_T09": "blocked",
        "T09_overall_acceptance_started": False,
    }
    assert result["next_action"] == NEXT_ACTION


def test_failure_result_contains_no_provider_answer_text() -> None:
    result = audit()
    encoded = json.dumps(result, ensure_ascii=False)
    assert "assistant_output_text" not in encoded
    assert result["restricted_capture_audit"][
        "raw_assistant_output_persisted_in_result"
    ] is False
    assert result["research_lead_safe_structure"][
        "provider_output_text_copied_to_result"
    ] is False
