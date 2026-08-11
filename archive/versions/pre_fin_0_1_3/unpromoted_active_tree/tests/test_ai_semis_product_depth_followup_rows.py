from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "data_expansion" / "build_ai_semis_product_depth_followup_rows.py"

spec = importlib.util.spec_from_file_location("build_ai_semis_product_depth_followup_rows", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
followup = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = followup
spec.loader.exec_module(followup)


def test_followup_materializer_admits_only_verified_parser_rows() -> None:
    def fake_fetch(target, timeout):
        if target.ticker == "005930.KS":
            return "Samsung HBM3E memory bandwidth product page", 200, "verified_public_html_text", None
        return "generic unrelated page", 200, "verified_public_html_text", None

    rows_by_layer, attempts = followup.materialize_followup_rows(
        timeout=1,
        generated_at="2026-06-27T00:00:00Z",
        fetcher=fake_fetch,
    )

    spec_rows = rows_by_layer["product_spec_architecture"]
    assert len(spec_rows) == 1
    assert spec_rows[0]["ticker"] == "005930.KS"
    assert spec_rows[0]["exact_value_authority"] is False
    assert "product_revenue" in spec_rows[0]["forbidden_claims"]
    assert sum(1 for attempt in attempts if attempt["admitted_as_evidence"]) == 1
    assert sum(1 for attempt in attempts if not attempt["admitted_as_evidence"]) == len(followup.TARGETS) - 1


def test_followup_context_rows_preserve_layer_and_boundary() -> None:
    target = followup.FollowupTarget(
        ticker="TST",
        company_name="Test Semi",
        evidence_layer="product_performance_proxy",
        source_id="trusted_proxy",
        source_role="customer_deployment_proxy",
        source_url="https://example.com",
        product_family="AI Server",
        product_or_segment="AI server deployment",
        metric_name="deployment_proxy",
        expected_terms=("ai", "server"),
        counterparty="Cloud Buyer",
        relationship_role="deployed_by_or_adopted_by",
        edge_type="deployed_by_or_adopted_by",
    )

    row = followup.build_context_row(
        target,
        "Cloud Buyer uses AI server deployment from Test Semi.",
        "2026-06-27T00:00:00Z",
        ["ai", "server"],
    )

    assert row["evidence_layer"] == "product_performance_proxy"
    assert row["counterparty"] == "Cloud Buyer"
    assert row["relationship_role"] == "deployed_by_or_adopted_by"
    assert row["exact_value_authority"] is False
    assert "does not prove product revenue" in row["claim_boundary"]
