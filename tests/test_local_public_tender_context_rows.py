from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_local_public_tender_context_rows.py"
SRC_PATH = SCRIPT_PATH.parents[2] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sec_agent.exact_slot_contracts import build_exact_slot_rows

SPEC = importlib.util.spec_from_file_location("build_local_public_tender_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_hk_open_data_csv_materializes_supplier_bound_tender_row(tmp_path: Path) -> None:
    csv_body = "\n".join(
        [
            "QPS Contract,Service Category/Group,Bureau/ Department,Work Assignment Title,Date of Award,Contractor Awarded,Awarded Contract Value SOA-QPS3",
            "SOA-QPS3,IT,Digital Policy Office,EV charging systems,2026-01-02,BYD Company Limited,12345",
        ]
    )

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        assert "digitalpolicy.gov.hk" in url
        return 200, "text/csv", csv_body

    result = MODULE.build_local_public_tender_context_rows(
        targets=[
            {
                **MODULE.LOCAL_TENDER_PLANS["1211.HK"],
                "ticker": "1211.HK",
                "company_name": "BYD Company Limited",
            }
        ],
        generated_at="2026-06-20T00:00:00Z",
        raw_dir=tmp_path,
        fetch=fake_fetch,
    )

    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["ticker"] == "1211.HK"
    assert row["source_id"] == "public_tenders_contracts_orders"
    assert row["award_amount"] == "12345"
    assert row["counterparty_binding_status"] == "counterparty_mentioned_in_snapshot"
    assert result["attempts"][0]["status"] == "materialized"

    payload = build_exact_slot_rows(result["rows"], generated_at="2026-06-20T00:00:00Z")
    assert payload["exact_slot_row_count"] >= 1
    assert "public_order_proxy" in {row["requirement_id"] for row in payload["exact_rows"]}


def test_local_portal_without_structured_award_stays_attempt_only(tmp_path: Path) -> None:
    result = MODULE.build_local_public_tender_context_rows(
        targets=[
            {
                **MODULE.LOCAL_TENDER_PLANS["2308.TW"],
                "ticker": "2308.TW",
                "company_name": "Delta Electronics",
            }
        ],
        generated_at="2026-06-20T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (200, "text/html", "<html>public procurement portal</html>"),
    )

    assert result["rows"] == []
    assert result["attempts"][0]["provider"] == "tw_pcc_eprocurement"
    assert result["attempts"][0]["status"] == "no_supplier_bound_award_or_no_structured_award_endpoint"


def test_local_tender_targets_current_public_order_docket_rows() -> None:
    targets = MODULE.build_targets(
        [
            {"ticker": "1211.HK", "company_name": "BYD Company Limited", "requirement_id": "public_order_proxy"},
            {"ticker": "AAPL", "company_name": "Apple", "requirement_id": "channel_offer_proxy"},
        ]
    )

    assert [target["ticker"] for target in targets] == ["1211.HK"]
