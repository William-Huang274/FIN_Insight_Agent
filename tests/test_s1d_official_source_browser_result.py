from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_s1d_browser_result_preserves_terminal_transport_block() -> None:
    result = json.loads(
        (
            ROOT
            / "configs"
            / "retrieval"
            / "fin_ia_0_1_3_s1d_official_source_browser_capture_result_v1_2.json"
        ).read_text(encoding="utf-8")
    )

    assert result["status"] == "terminal_blocked_by_official_site_access_control_no_r3"
    assert result["execution"] == {
        "official_routes": 2,
        "discovery_page_attempts": 2,
        "download_attempts": 0,
        "retries": 0,
        "model_calls": 0,
        "search_provider_calls": 0,
        "captured_official_pdfs": 0,
        "parsed_documents": 0,
        "evidence_promoted": 0,
    }
    assert {row["failure_code"] for row in result["route_results"]} == {
        "official_source_browser_discovery_http_403"
    }
    assert result["stop_decision"] == {
        "automatic_r3_forbidden": True,
        "search_excerpt_as_evidence_forbidden": True,
        "active_object_store_mutation_forbidden": True,
        "s3_model_execution_authorized": False,
        "reason_zh": "合格 Evidence Pack 尚未建立；当前 Evidence Role 只能 advisory，且两项真实补源仍是 typed gap。继续 S3 只会让模型更稳定地消费未经晋升的候选。",
    }
