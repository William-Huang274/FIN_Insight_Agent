from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ingestion.official_source_capture import _TransportResponse
from scripts.data_retrieval.materialize_dell_q2_reviewed_evidence_overlay import (
    PROJECTION_SCHEMA,
    compose_case_projection,
    materialize_overlay,
)
from sec_agent.research.reviewed_evidence_pack import (
    canonical_digest,
    validate_reviewed_evidence_pack,
)


URL = (
    "https://www.sec.gov/Archives/edgar/data/1571996/"
    "000157199626000039/exhibit991earnings8kq2fy27.htm"
)
TITLE = "Dell Technologies Delivers Second Quarter Fiscal 2027 Financial Results"
QUOTES = (
    "Dell Technologies reports the current fiscal second-quarter event and "
    "identifies the issuer, reporting scope, and publication context.",
    "The issuer describes one bounded order proposition with an exact source "
    "sentence that remains textual Evidence rather than NumericFact.",
    "The issuer describes one bounded revenue proposition with an exact source "
    "sentence that remains textual Evidence rather than NumericFact.",
    "The issuer describes one bounded segment proposition and preserves the "
    "aggregate segment boundary without product-profit attribution.",
    "The issuer describes one bounded guidance proposition that remains a "
    "management outlook rather than an observed realized result.",
)


def _html() -> bytes:
    paragraphs = "".join(f"<p>{value}</p>" for value in QUOTES)
    return (
        f"<html><body><h1>{TITLE}</h1><p>{TITLE}</p>{paragraphs}</body></html>"
    ).encode()


def _review(body: bytes) -> dict:
    items = []
    for index, quote in enumerate(QUOTES, start=1):
        items.append(
            {
                "item_id": f"ITEM_{index:02d}",
                "target_id": f"DELL_Q2_TEST_TARGET_{index:02d}",
                "topic": f"fixture_topic_{index}",
                "reviewed_quote": quote,
                "slot_id": "operating_performance",
                "facet_ids": [f"fixture_facet_{index}"],
                "qualification_id": f"fixture-qualification-{index}",
                "business_meaning_zh": "该测试命题可验证来源绑定。",
                "claim_boundary_zh": "不得转换成 S2 NumericFact 或衍生运算。",
            }
        )
    return {
        "schema_version": (
            "fin_ia_dell_fy27_q2_reviewed_evidence_overlay_review_v1_0"
        ),
        "status": "case_only_author_review_complete",
        "reviewed_at": "2026-09-02T05:00:00+08:00",
        "reviewer_id": "codex_case_review",
        "case_key": "DELL",
        "research_as_of": "2026-09-02T05:00:00+08:00",
        "source": {
            "accession_number": "0001571996-26-000039",
            "exhibit_document": "exhibit991earnings8kq2fy27.htm",
            "publication_date": "2026-09-01",
            "reporting_period_end": "2026-07-31",
            "source_url": URL,
            "source_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "expected_raw_body_sha256": hashlib.sha256(body).hexdigest(),
            "expected_raw_body_bytes": len(body),
            "required_document_title": TITLE,
        },
        "items": items,
        "residual_gap": {
            "gap_id": "GAP::DELL::FY27Q2::STRUCTURED_NUMERIC_FACT",
            "gap_code": "current_quarter_structured_numeric_source_pending",
            "slot_id": "current_quarter_structured_numeric_authority",
            "detail_zh": "当前季度衍生运算仍须等待结构化来源进入 S2。",
        },
        "authority": {
            "case_only_reviewed_evidence": True,
            "writer_citable_within_case": True,
            "source_visible_exact_values_quoteable": True,
            "automatic_evidence_promotion": False,
            "qualified_human_review": False,
            "s2_numeric_fact_authority": False,
            "derived_current_q2_arithmetic_authorized": False,
            "product_pack_mutation_authorized": False,
            "method_or_planner_answer_injection": False,
        },
    }


def _write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _fetch(body: bytes):
    def fetch(_source: dict) -> _TransportResponse:
        return _TransportResponse(
            status_code=200,
            final_url=URL,
            headers={"content-type": "text/html"},
            redirect_chain=(),
            body=body,
            transport_attempts=1,
        )

    return fetch


def test_materializer_builds_pack_locators_and_mcp_projection(tmp_path: Path) -> None:
    body = _html()
    review_path = tmp_path / "review.json"
    _write(review_path, _review(body))
    result = materialize_overlay(
        review_path,
        tmp_path / "attempts",
        "fixture-a01",
        transport_fetchers={"requests": _fetch(body)},
    )
    root = tmp_path / "attempts" / "fixture-a01"
    pack = json.loads((root / "reviewed-evidence-pack.json").read_text("utf-8"))
    projection = json.loads(
        (root / "reviewed-evidence-case-projection.json").read_text("utf-8")
    )
    validate_reviewed_evidence_pack(pack)
    assert result["status"] == "case_only_reviewed_evidence_overlay_materialized"
    assert result["review"]["item_count"] == 5
    assert result["review"]["mcp_reviewed_evidence_reader"]["status"] == "PASS"
    assert result["source_identity"]["inline_xbrl_ix_tag_count"] == 0
    assert projection["schema_version"] == PROJECTION_SCHEMA
    assert len(projection["evidence_items"]) == 5
    assert all(
        item["source"]["source_locator"]["quote_sha256"]
        == item["source"]["source_text_digest"]
        for item in projection["evidence_items"]
    )
    assert all(
        item["writer_citable"] is True
        and item["causal_attribution_authorized"] is False
        and "not an S2 NumericFact" in item["numeric_use_boundary"]
        for item in projection["evidence_items"]
    )


def test_materializer_rejects_unlocated_review_quote(tmp_path: Path) -> None:
    body = _html()
    review = _review(body)
    review["items"][0]["reviewed_quote"] = (
        "This deliberately absent reviewed proposition is long enough to satisfy "
        "the input contract but cannot be located in the captured source."
    )
    review_path = tmp_path / "review.json"
    _write(review_path, review)
    with pytest.raises(ValueError, match="q2_overlay_quote_not_unique:ITEM_01:0"):
        materialize_overlay(
            review_path,
            tmp_path / "attempts",
            "fixture-a02",
            transport_fetchers={"requests": _fetch(body)},
        )


def test_composite_projection_is_digest_bound_and_collision_closed(
    tmp_path: Path,
) -> None:
    body = _html()
    review_path = tmp_path / "review.json"
    _write(review_path, _review(body))
    materialize_overlay(
        review_path,
        tmp_path / "attempts",
        "fixture-a03",
        transport_fetchers={"requests": _fetch(body)},
    )
    overlay = json.loads(
        (
            tmp_path
            / "attempts"
            / "fixture-a03"
            / "reviewed-evidence-case-projection.json"
        ).read_text("utf-8")
    )
    base_body = {
        "schema_version": "fixture_base_projection",
        "case_key": "DELL",
        "evidence_items": [],
    }
    base = {**base_body, "projection_digest": canonical_digest(base_body)}
    composite = compose_case_projection(base, overlay)
    assert composite["projection_digest"] == canonical_digest(
        {key: value for key, value in composite.items() if key != "projection_digest"}
    )
    assert composite["case_only_evidence_overlay"]["overlay_evidence_count"] == 5
    assert len(composite["evidence_items"]) == 5

    collision_body = deepcopy(base_body)
    collision_body["evidence_items"] = [deepcopy(overlay["evidence_items"][0])]
    collision = {
        **collision_body,
        "projection_digest": canonical_digest(collision_body),
    }
    with pytest.raises(
        ValueError, match="q2_overlay_composite_evidence_identity_collision"
    ):
        compose_case_projection(collision, overlay)
