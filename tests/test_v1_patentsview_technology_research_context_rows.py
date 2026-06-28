from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_v1_patentsview_technology_research_context_rows.py"
SRC_PATH = SCRIPT_PATH.parents[2] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sec_agent.exact_slot_contracts import build_exact_slot_rows

SPEC = importlib.util.spec_from_file_location("build_v1_patentsview_technology_research_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _target() -> dict[str, object]:
    return {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "primary_lane_id": "V1",
        "family_ids": ["gpu_accelerator"],
        "family_names": ["GPU / Accelerator"],
        "company_aliases": ["NVIDIA", "NVIDIA Corporation"],
        "product_terms": ["GPU", "Accelerator"],
    }


def test_patentsview_missing_key_writes_attempt_without_promoting_rows(tmp_path: Path) -> None:
    result = MODULE.build_v1_patentsview_technology_research_context_rows(
        targets=[_target()],
        generated_at="2026-06-20T00:00:00Z",
        raw_dir=tmp_path,
        api_key="",
    )

    assert result["rows"] == []
    assert result["attempts"][0]["source_id"] == MODULE.SOURCE_ID
    assert result["attempts"][0]["status"] == "missing_patentsview_api_key"


def test_patentsview_rows_require_assignee_and_topic_binding(tmp_path: Path) -> None:
    payload = {
        "patents": [
            {
                "patent_id": "US1234567B2",
                "patent_title": "GPU accelerator scheduling for parallel processing",
                "patent_date": "2025-01-03",
                "patent_abstract": "A system for GPU accelerator task scheduling.",
                "assignees": [{"assignee_organization": "NVIDIA Corporation"}],
                "cpc_current": [{"cpc_group_id": "G06F"}],
            },
            {
                "patent_id": "US7654321B2",
                "patent_title": "Generic GPU paper without issuer binding",
                "patent_date": "2025-01-04",
                "patent_abstract": "GPU method.",
                "assignees": [{"assignee_organization": "Example University"}],
            },
        ]
    }

    def fake_fetch(url: str, body: bytes, headers: dict[str, str], timeout_s: float) -> tuple[int, str, str]:
        assert url == MODULE.PATENTSEARCH_API_URL
        assert headers["X-Api-Key"] == "test-key"
        assert timeout_s == 2
        query = json.loads(body.decode("utf-8"))
        assert query["q"]
        return 200, "application/json", json.dumps(payload)

    result = MODULE.build_v1_patentsview_technology_research_context_rows(
        targets=[_target()],
        generated_at="2026-06-20T00:00:00Z",
        raw_dir=tmp_path,
        api_key="test-key",
        timeout_s=2,
        fetch=fake_fetch,
    )

    rows = result["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == MODULE.SOURCE_ID
    assert row["source_layer_id"] == "L3"
    assert row["structured_context_type"] == "technology_research_proxy_context"
    assert row["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert row["product_binding_status"] == "technology_topic_bound"
    assert row["source_url"] == MODULE.PATENTSEARCH_API_URL
    assert row["patent_public_url"] == "https://patents.google.com/patent/US1234567B2"
    assert row["exact_value_authority"] is False
    assert "product_sales" in row["forbidden_claims"]
    assert Path(row["raw_path"]).exists()
    assert result["attempts"][0]["status"] == "materialized"

    exact_payload = build_exact_slot_rows(rows, generated_at="2026-06-20T00:00:00Z")
    assert exact_payload["exact_slot_row_count"] == 1
    assert exact_payload["exact_rows"][0]["requirement_id"] == "technology_research_proxy"


def test_patentsview_assignee_or_topic_mismatch_is_not_materialized(tmp_path: Path) -> None:
    payload = {
        "patents": [
            {
                "patent_id": "US1111111B2",
                "patent_title": "Generic semiconductor test method",
                "patent_date": "2025-01-03",
                "patent_abstract": "No configured topic term.",
                "assignees": [{"assignee_organization": "NVIDIA Corporation"}],
            }
        ]
    }

    result = MODULE.build_v1_patentsview_technology_research_context_rows(
        targets=[_target()],
        generated_at="2026-06-20T00:00:00Z",
        raw_dir=tmp_path,
        api_key="test-key",
        fetch=lambda url, body, headers, timeout_s: (200, "application/json", json.dumps(payload)),
    )

    assert result["rows"] == []
    assert result["attempts"][0]["status"] == "no_assignee_topic_bound_patents"
