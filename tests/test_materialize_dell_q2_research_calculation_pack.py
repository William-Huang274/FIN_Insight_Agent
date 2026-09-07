from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from scripts.data_retrieval.materialize_dell_q2_research_calculation_pack import (
    CALCULATION_MANIFEST_SCHEMA,
    CALCULATION_PACK_SCHEMA,
    DellQ2ResearchCalculationError,
    materialize_research_calculation_pack,
)
from scripts.data_retrieval.materialize_dell_q2_reviewed_evidence_overlay import (
    PACK_STATUS,
    PROJECTION_SCHEMA,
)
from sec_agent.research.reviewed_evidence_pack import (
    REVIEWED_EVIDENCE_PACK_CONTRACT,
    REVIEWED_EVIDENCE_PACK_SCHEMA,
    canonical_digest,
    validate_reviewed_evidence_pack,
)


URL = (
    "https://www.sec.gov/Archives/edgar/data/1571996/"
    "000157199626000039/exhibit991earnings8kq2fy27.htm"
)
RAW_SHA = hashlib.sha256(b"fixture raw Dell FY27 Q2 exhibit").hexdigest()
PARSED_SHA = hashlib.sha256(b"fixture parsed Dell FY27 Q2 exhibit").hexdigest()
QUOTES = {
    "CURRENT_EVENT": (
        "Dell Technologies (NYSE: DELL) announces financial results for its "
        "fiscal 2027 second quarter and provides guidance for its fiscal 2027 "
        "third quarter and full year."
    ),
    "AI_ORDER_REVENUE_BACKLOG": (
        "That’s clearest in our AI server business where we booked a record "
        "$60.9 billion in orders, recognized a record $16.4 billion in revenue "
        "and exited the quarter with a record $95 billion backlog."
    ),
    "COMPANY_SUMMARY": (
        "Second-Quarter Summary • Record revenue of $47.0 billion, up 58% year "
        "over year • Record diluted earnings per share (EPS) of $6.34, up 273% "
        "year over year, and record non-GAAP diluted EPS of $7.04, up 203% • "
        "Cash flow from operations of $2.2 billion"
    ),
    "ISG_SEGMENT": (
        "Infrastructure Solutions Group (ISG) • Record revenue: $31.8 billion, "
        "up 89% year over year • Record AI-Optimized Servers revenue: $16.4 "
        "billion, up 100% year over year • Record Traditional Servers and "
        "Networking revenue: $10.5 billion, up 122% year over year • Record "
        "second-quarter Storage revenue: $4.9 billion, up 26% year over year • "
        "Record operating income: $4.8 billion, up 225% year over year"
    ),
    "CSG_SEGMENT": (
        "Client Solutions Group (CSG) • Revenue: $15.0 billion, up 20% year over "
        "year • Record Commercial Client revenue: $13.2 billion, up 22% year "
        "over year • Consumer revenue: $1.8 billion, up 7% year over year"
    ),
    "FY27_GUIDANCE": (
        "Full-Year Guidance FY27 Previous FY27 Updated (% Y/Y) Revenue $ 167.0 "
        "$ 192.0 69 % AI-Optimized Servers revenue $ 60.0 $ 74.0 200 % GAAP "
        "diluted EPS $ 17.31 $ 24.37 181 % Non-GAAP diluted EPS $ 17.90 $ "
        "25.50 148 %"
    ),
}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence_item(proposition_id: str, quote: str, index: int) -> dict:
    quote_digest = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    record_id = (
        "SEC::DELL::0001571996-26-000039::"
        f"EXHIBIT991EARNINGS8KQ2FY27.HTM::PROP::{proposition_id}"
    )
    material_ref = "source_material_" + canonical_digest(
        {"source_record_id": record_id, "quote_sha256": quote_digest}
    )[:24]
    body = {
        "case_key": "DELL",
        "target_id": f"DELL_Q2_TEST_TARGET_{index:02d}",
        "source_record_id": record_id,
        "object_type": "claim",
        "disposition": "accepted_direct_source_evidence",
        "evidence_role": "issuer_direct_source",
        "publication_date": "2026-09-01",
        "source_reporting_period_end": "2026-07-31",
        "research_as_of": "2026-09-02",
        "relationship_directions": ["subject_self_disclosure"],
        "slot_bindings": [
            {
                "slot_id": "operating_performance",
                "facet_ids": [f"fixture_{proposition_id.lower()}"],
                "qualification_id": f"fixture-{proposition_id.lower()}",
                "business_meaning_zh": "该已审核命题用于测试来源绑定。",
                "claim_boundary_zh": "不得转换成 S2 NumericFact。",
            }
        ],
        "numeric_use_boundary": "Reviewed quote; not an S2 NumericFact.",
        "causal_attribution_authorized": False,
        "writer_citable": True,
        "claim_use": "issuer_direct_source_visible_statement",
        "proposition_id": proposition_id,
        "target_company_exact_numeric_authority": (
            "source_visible_quote_only_not_s2_numeric_fact"
        ),
        "source_material_ref": material_ref,
        "source_content_digest": quote_digest,
    }
    source = {
        "material_ref": material_ref,
        "source_record_id": record_id,
        "evidence_owner_ticker": "DELL",
        "source_tier": "company_authored_unaudited_sec_filing",
        "source_type": "8-K",
        "source_url": URL,
        "publication_date": "2026-09-01",
        "period_end": "2026-07-31",
        "license_scope": "public_sec_filing",
        "redistributable": False,
        "source_text_digest": quote_digest,
        "source_locator": {
            "mode": "normalized_parsed_text_char_span",
            "char_start": index * 1_000,
            "char_end": index * 1_000 + len(quote),
            "quote_sha256": quote_digest,
            "parsed_search_text_sha256": PARSED_SHA,
            "raw_body_sha256": RAW_SHA,
        },
        "source_identity": {
            "accession_number": "0001571996-26-000039",
            "exhibit_document": "exhibit991earnings8kq2fy27.htm",
            "raw_body_sha256": RAW_SHA,
            "parsed_search_text_sha256": PARSED_SHA,
        },
        "reviewed_source_excerpt": quote,
        "excerpt_truncated": False,
        "excerpt_use_boundary": "Case-only reviewed SEC evidence.",
    }
    return {**body, "evidence_item_digest": canonical_digest(body), "source": source}


def _projection() -> dict:
    items = [
        _evidence_item(proposition_id, quote, index)
        for index, (proposition_id, quote) in enumerate(QUOTES.items(), start=1)
    ]
    body = {
        "schema_version": PROJECTION_SCHEMA,
        "status": "case_only_reviewed_evidence_projection_ready",
        "case_key": "DELL",
        "pack_payload_digest": hashlib.sha256(b"fixture parent pack").hexdigest(),
        "evidence_items": items,
        "authority": {
            "reviewed_evidence": True,
            "automatic_evidence_promotion": False,
            "qualified_human_review": False,
            "s2_numeric_fact_authority": False,
            "derived_current_q2_arithmetic_authorized": False,
            "product_pack_mutation_authorized": False,
        },
    }
    return {**body, "projection_digest": canonical_digest(body)}


def _pack() -> dict:
    projection = _projection()
    evidence_items = []
    source_materials = []
    for projected in projection["evidence_items"]:
        item = deepcopy(projected)
        source = item.pop("source")
        source["source_text"] = source.pop("reviewed_source_excerpt")
        source.pop("excerpt_truncated")
        source.pop("excerpt_use_boundary")
        evidence_items.append(item)
        source_materials.append(source)
    body = {
        "schema_version": REVIEWED_EVIDENCE_PACK_SCHEMA,
        "contract_ref": REVIEWED_EVIDENCE_PACK_CONTRACT,
        "status": PACK_STATUS,
        "case_key": "DELL",
        "research_as_of": "2026-09-02",
        "source_materials": source_materials,
        "evidence_items": evidence_items,
        "rejected_items": [],
        "residual_gaps": [
            {
                "gap_id": "GAP::DELL::FY27Q2::STRUCTURED_NUMERIC_FACT",
                "gap_code": "current_quarter_structured_numeric_source_pending",
                "slot_id": "current_quarter_structured_numeric_authority",
                "detail_zh": "当前季度仍不是 S2 NumericFact。",
            }
        ],
        "observed_counts": {
            "accepted_evidence_items": 6,
            "direct_evidence_items": 6,
            "bounded_context_items": 0,
            "rejected_items": 0,
            "residual_gaps": 1,
            "source_materials": 6,
        },
        "content_gate_basis": "fixture_exact_reviewed_quote_spans",
        "consumer_contract": {
            "writer_may_quote_source_visible_exact_values": True,
            "writer_must_cite_official_source_url": True,
            "current_q2_s2_numeric_fact_authority": False,
            "current_q2_derived_arithmetic_authority": False,
        },
        "known_boundary": "Case-only Reviewed Evidence; not S2 NumericFact.",
    }
    pack = {**body, "pack_payload_digest": canonical_digest(body)}
    validate_reviewed_evidence_pack(pack)
    return pack


def _write(path: Path, value: dict) -> str:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return _file_sha256(path)


def _replace_projection_quote(
    projection: dict,
    proposition_id: str,
    old: str,
    new: str,
) -> None:
    item = next(
        row
        for row in projection["evidence_items"]
        if row["proposition_id"] == proposition_id
    )
    source = item["source"]
    quote = source["reviewed_source_excerpt"].replace(old, new)
    assert quote != source["reviewed_source_excerpt"]
    quote_digest = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    material_ref = "source_material_" + canonical_digest(
        {
            "source_record_id": item["source_record_id"],
            "quote_sha256": quote_digest,
        }
    )[:24]
    source["reviewed_source_excerpt"] = quote
    source["source_text_digest"] = quote_digest
    source["source_locator"]["quote_sha256"] = quote_digest
    source["source_locator"]["char_end"] = (
        source["source_locator"]["char_start"] + len(quote)
    )
    source["material_ref"] = material_ref
    item["source_material_ref"] = material_ref
    item["source_content_digest"] = quote_digest
    item_body = deepcopy(item)
    item_body.pop("source")
    item_body.pop("evidence_item_digest")
    item["evidence_item_digest"] = canonical_digest(item_body)
    projection_body = deepcopy(projection)
    projection_body.pop("projection_digest")
    projection["projection_digest"] = canonical_digest(projection_body)


def _materialize(tmp_path: Path, value: dict, attempt_id: str = "fixture-a01") -> dict:
    input_path = tmp_path / f"{attempt_id}-input.json"
    expected_sha = _write(input_path, value)
    return materialize_research_calculation_pack(
        input_path,
        tmp_path / "attempts",
        attempt_id,
        expected_input_sha256=expected_sha,
        materialized_at="2026-09-02T12:00:00+08:00",
    )


@pytest.mark.parametrize("reviewed_input", [_projection, _pack])
def test_materializes_projection_or_pack_with_non_s2_lineage(
    tmp_path: Path,
    reviewed_input,
) -> None:
    result = _materialize(tmp_path, reviewed_input())
    attempt_root = tmp_path / "attempts" / "fixture-a01"
    pack_path = attempt_root / "research-calculation-pack.json"
    manifest_path = attempt_root / "manifest.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert pack["schema_version"] == CALCULATION_PACK_SCHEMA
    assert manifest["schema_version"] == CALCULATION_MANIFEST_SCHEMA
    assert pack["observed_counts"] == {
        "reviewed_evidence_items": 6,
        "source_numeric_observations": 10,
        "research_calculations": 7,
    }
    assert pack["authority"]["model_raw_numbers_accepted"] is False
    assert pack["authority"]["s2_numeric_fact_authority"] is False
    assert pack["authority"]["s2_mart_write_authorized"] is False
    assert all(
        row["source_visible_surface"]
        and row["source_visible_surface_verified"] is True
        and row["evidence_id"].startswith("EV::")
        and row["source_url"] == URL
        and row["source_content_digest"]
        and row["source_reporting_period_end"] == "2026-07-31"
        and row["numeric_fact_authority"] is False
        for row in pack["source_numeric_observations"]
    )
    assert all(
        row["formula_id"]
        and row["input_observation_ids"]
        and row["evidence_ids"]
        and row["source_urls"] == [URL]
        and row["required_short_caveat"]
        and row["issuer_reported_metric"] is False
        and row["numeric_fact_authority"] is False
        for row in pack["research_calculations"]
    )
    assert manifest["checks"]["s2_mart_written"] is False
    assert manifest["checks"]["model_called"] is False
    assert manifest["artifacts"]["research_calculation_pack"]["sha256"] == (
        _file_sha256(pack_path)
    )
    assert result["manifest_file_sha256"] == _file_sha256(manifest_path)
    assert sorted(path.name for path in attempt_root.iterdir()) == [
        "manifest.json",
        "research-calculation-pack.json",
    ]


def test_expected_values_and_semantic_labels_are_bounded(tmp_path: Path) -> None:
    _materialize(tmp_path, _projection())
    pack = json.loads(
        (
            tmp_path
            / "attempts"
            / "fixture-a01"
            / "research-calculation-pack.json"
        ).read_text(encoding="utf-8")
    )
    calculations = {
        row["calculation_id"]: row for row in pack["research_calculations"]
    }
    expected_displays = {
        "dell_ai_server_revenue_share_of_isg_q2_fy27": "51.6%",
        "dell_ai_server_revenue_share_of_company_q2_fy27": "34.9%",
        "dell_isg_operating_margin_recalculated_q2_fy27": "15.1%",
        "dell_ai_server_orders_to_revenue_multiple_q2_fy27": "3.71x",
        "dell_ai_server_backlog_to_revenue_multiple_q2_fy27": "5.79x",
        "dell_ai_server_revenue_guidance_uplift_fy27": "23.3%",
        "dell_company_revenue_guidance_uplift_fy27": "15.0%",
    }
    assert {
        calculation_id: row["display_value"]
        for calculation_id, row in calculations.items()
    } == expected_displays
    assert "not AI-server margin" in calculations[
        "dell_isg_operating_margin_recalculated_q2_fy27"
    ]["semantic_caveat"]
    for calculation_id in (
        "dell_ai_server_orders_to_revenue_multiple_q2_fy27",
        "dell_ai_server_backlog_to_revenue_multiple_q2_fy27",
    ):
        row = calculations[calculation_id]
        assert "conversion" not in row["metric_label"].lower()
        assert "duration" not in row["metric_label"].lower()
        assert "not" in row["semantic_caveat"].lower()
    backlog = calculations[
        "dell_ai_server_backlog_to_revenue_multiple_q2_fy27"
    ]
    assert "不是转化率或持续期" in backlog["required_short_caveat"]
    assert Decimal(backlog["value_decimal"]) > Decimal("5.79")


def test_rejects_digest_valid_input_without_required_source_surface(
    tmp_path: Path,
) -> None:
    projection = _projection()
    _replace_projection_quote(
        projection,
        "ISG_SEGMENT",
        "Record AI-Optimized Servers revenue: $16.4 billion",
        "Record accelerated systems sales: $16.4 billion",
    )
    input_path = tmp_path / "missing-surface.json"
    expected_sha = _write(input_path, projection)
    with pytest.raises(
        DellQ2ResearchCalculationError,
        match=(
            "research_calculation_source_observation_missing_or_ambiguous:"
            "dell_ai_server_revenue_q2_fy27"
        ),
    ):
        materialize_research_calculation_pack(
            input_path,
            tmp_path / "attempts",
            "fixture-a02",
            expected_input_sha256=expected_sha,
            materialized_at="2026-09-02T12:00:00+08:00",
        )


def test_rejects_zero_denominator_before_writing_artifacts(tmp_path: Path) -> None:
    projection = _projection()
    _replace_projection_quote(
        projection,
        "COMPANY_SUMMARY",
        "$47.0 billion",
        "$0.0 billion",
    )
    input_path = tmp_path / "zero-denominator.json"
    expected_sha = _write(input_path, projection)
    with pytest.raises(
        DellQ2ResearchCalculationError,
        match=(
            "research_calculation_denominator_zero:"
            "dell_ai_server_revenue_share_of_company_q2_fy27"
        ),
    ):
        materialize_research_calculation_pack(
            input_path,
            tmp_path / "attempts",
            "fixture-a03",
            expected_input_sha256=expected_sha,
            materialized_at="2026-09-02T12:00:00+08:00",
        )
    assert not (tmp_path / "attempts" / "fixture-a03").exists()


def test_rejects_input_file_sha_or_authority_drift(tmp_path: Path) -> None:
    projection = _projection()
    input_path = tmp_path / "projection.json"
    expected_sha = _write(input_path, projection)
    with pytest.raises(
        DellQ2ResearchCalculationError,
        match="research_calculation_input_file_sha256_mismatch",
    ):
        materialize_research_calculation_pack(
            input_path,
            tmp_path / "attempts",
            "fixture-a04",
            expected_input_sha256="0" * 64,
            materialized_at="2026-09-02T12:00:00+08:00",
        )

    projection["authority"]["s2_numeric_fact_authority"] = True
    body = deepcopy(projection)
    body.pop("projection_digest")
    projection["projection_digest"] = canonical_digest(body)
    expected_sha = _write(input_path, projection)
    with pytest.raises(
        DellQ2ResearchCalculationError,
        match="research_calculation_projection_input_invalid",
    ):
        materialize_research_calculation_pack(
            input_path,
            tmp_path / "attempts",
            "fixture-a05",
            expected_input_sha256=expected_sha,
            materialized_at="2026-09-02T12:00:00+08:00",
        )
