from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_public_contract_award_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_public_contract_award_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_usaspending_payload_contains_contract_award_type_codes() -> None:
    payload = MODULE.usaspending_payload({"company_name": "Palantir", "recipient_search_text": ["Palantir"]}, limit=2)
    assert payload["filters"]["recipient_search_text"] == ["Palantir"]
    assert payload["filters"]["award_type_codes"] == ["A", "B", "C", "D"]
    assert payload["limit"] == 2


def test_build_public_contract_award_context_rows_with_fixture_fetch(tmp_path: Path) -> None:
    response = {
        "results": [
            {
                "Award ID": "70ABC26F0001",
                "Recipient Name": "PALANTIR TECHNOLOGIES INC.",
                "Award Amount": 1000000,
                "Start Date": "2026-05-01",
                "End Date": "2027-05-01",
                "Awarding Agency": "Department of Homeland Security",
                "Award Description": "software platform support",
            }
        ]
    }

    def fake_fetch(url: str, payload: dict, timeout_s: float) -> tuple[int, str, str]:
        assert url == MODULE.USA_SPENDING_URL
        assert payload["filters"]["award_type_codes"] == ["A", "B", "C", "D"]
        assert timeout_s == 2
        return 200, "application/json", json.dumps(response)

    result = MODULE.build_public_contract_award_context_rows(
        probes=[
            {
                "ticker": "PLTR",
                "company_name": "Palantir Technologies",
                "company_names": ["Palantir Technologies", "PALANTIR TECHNOLOGIES INC"],
                "recipient_search_text": ["Palantir Technologies"],
                "product_terms": ["AIP", "Foundry", "software"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
        fetch=fake_fetch,
    )

    rows = result["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == MODULE.SOURCE_ID
    assert row["provider"] == "usaspending"
    assert row["source_layer_id"] == "L3"
    assert row["structured_context_type"] == "public_tender_contract_context"
    assert row["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert row["counterparty_binding_status"] == "counterparty_mentioned_in_snapshot"
    assert row["exact_value_authority"] is False
    assert row["award_id"] == "70ABC26F0001"
    assert Path(row["raw_path"]).exists()


def test_public_contract_award_coverage_gate_passes_with_issuer_and_counterparty_rows(tmp_path: Path) -> None:
    result = MODULE.build_public_contract_award_context_rows(
        probes=[
            {
                "ticker": "MSFT",
                "company_name": "Microsoft",
                "company_names": ["Microsoft", "MICROSOFT CORPORATION"],
                "recipient_search_text": ["Microsoft Corporation"],
                "product_terms": ["Azure", "cloud"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, payload, timeout_s: (
            200,
            "application/json",
            json.dumps(
                {
                    "results": [
                        {
                            "Award ID": "47QTCA24D0001",
                            "Recipient Name": "MICROSOFT CORPORATION",
                            "Award Amount": 2000000,
                            "Start Date": "2026-06-01",
                            "End Date": "2027-06-01",
                            "Awarding Agency": "General Services Administration",
                            "Award Description": "cloud software",
                        }
                    ]
                }
            ),
        ),
    )
    source_rows = [
        {
            "source_id": MODULE.SOURCE_ID,
            "layer_id": "L3",
            "evidence_graph_status": "runtime_ready_context",
            "can_crawl_or_download": True,
            "can_structure": True,
            "runtime_ready_context": True,
            "exact_value_authority_ready": False,
            "can_support_company_exact_fact": False,
        }
    ]

    coverage = MODULE.build_public_contract_award_coverage_gate(
        context_rows=result["rows"],
        source_layer_rows=source_rows,
        generated_at="2026-06-17T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["requirement_id"] == "public_order_proxy"
    assert req["status"] == "pass"
    assert req["entity_bound_row_count"] == 1


def test_public_contract_award_fetch_retries_transient_failure(tmp_path: Path) -> None:
    calls = 0

    def flaky_fetch(url: str, payload: dict, timeout_s: float) -> tuple[int, str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("transient read failure")
        return (
            200,
            "application/json",
            json.dumps(
                {
                    "results": [
                        {
                            "Award ID": "A1",
                            "Recipient Name": "ORACLE AMERICA INC",
                            "Start Date": "2026-01-01",
                            "Awarding Agency": "Department of Defense",
                        }
                    ]
                }
            ),
        )

    result = MODULE.build_public_contract_award_context_rows(
        probes=[
            {
                "ticker": "ORCL",
                "company_name": "Oracle",
                "company_names": ["Oracle", "ORACLE AMERICA INC"],
                "recipient_search_text": ["Oracle America"],
                "product_terms": ["database"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch_retries=1,
        fetch=flaky_fetch,
    )

    assert calls == 2
    assert len(result["rows"]) == 1
    assert result["attempts"][0]["status"] == "materialized"
