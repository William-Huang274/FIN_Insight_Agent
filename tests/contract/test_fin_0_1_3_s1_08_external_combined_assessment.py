from __future__ import annotations

import json
from pathlib import Path

from sec_agent.s1_08_external_combined_assessment import (
    assess_external_combined_live,
)


ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_live_result_v1_0.json"
)
RUNTIME = ROOT / ".codex_runtime/fin013_s1_08/external_combined/live-r1"


def test_r1_assessment_preserves_terminal_and_classifies_two_root_causes() -> None:
    assessment = assess_external_combined_live(
        result=json.loads(RESULT.read_text(encoding="utf-8")),
        runtime_root=RUNTIME,
        resolver=lambda _host: ("198.18.1.10",),
    )
    assert assessment["status"] == (
        "terminal_valid_external_candidate_reachability_blocked"
    )
    assert assessment["capture_integrity"] == {
        "official_content_addressed_objects": 91,
        "official_content_addresses_valid": True,
        "firecrawl_capture_refs": 72,
        "firecrawl_capture_refs_sha_valid": True,
        "raw_request_or_response_content_lost": False,
    }
    assert assessment["official_lane"]["failure_codes"] == {
        "official_source_private_network_forbidden": 26
    }
    assert assessment["query_facet_binding"][
        "attempt_budget_digests_equal_receipt_bound_digests"
    ] is True
    assert assessment["query_facet_binding"]["attempt_query_view_mismatch_count"] == 36
    assert assessment["firecrawl_shadow_lane"]["http_status_counts"] == {
        "200": 5,
        "429": 19,
    }
    assert assessment["firecrawl_shadow_lane"]["credit_exhaustion_failures"] == 19
    assert assessment["firecrawl_shadow_lane"]["successful_queries_by_case"] == {
        "DELL": 5
    }
    assert assessment["root_cause_disposition"]["deepseek_or_model_failure"] is False
    assert assessment["stage_disposition"]["internal_retrieval_started"] is False
