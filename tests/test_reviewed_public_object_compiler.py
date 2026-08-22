from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from retrieval.contracts import load_financial_research_kernel
from retrieval.reviewed_public_object_compiler import (
    ReviewedPublicObjectCompilationError,
    compile_reviewed_public_source_objects,
)
from retrieval.route_compiler import load_query_object_fact_route_policy


ROOT = Path(__file__).resolve().parents[1]


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _policy():
    kernel = load_financial_research_kernel(
        _json("configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_3.json")
    )
    return load_query_object_fact_route_policy(
        _json("configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_3.json"),
        kernel,
    )


def _pack() -> dict:
    text = (
        "Dell offers integrated racks of accelerated servers with networking, "
        "power and cooling, and tests the solution before deployment."
    )
    return {
        "case_key": "DELL",
        "evidence_items": [
            {
                "source_record_id": "PUBLIC::DELL-EXT::TEST",
                "source_material_ref": "material-1",
                "writer_citable": True,
                "slot_bindings": [{"slot_id": "pricing_mix_value_capture"}],
                "proposition_id": "DELL-PROP-PRICE-CONFIGURATION",
            }
        ],
        "source_materials": [
            {
                "material_ref": "material-1",
                "source_record_id": "PUBLIC::DELL-EXT::TEST",
                "source_type": "PUBLIC_WEB",
                "source_tier": "issuer_regulator_or_government_primary",
                "evidence_owner_ticker": "DELL",
                "speaker_entity": "Dell Technologies Inc.",
                "publication_date": "2024-08-21",
                "period_end": None,
                "source_url": "https://example.test/dell",
                "source_text": text,
                "source_text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "raw_capture_sha256": "a" * 64,
                "license_scope": "public_web_private_research_capture",
                "redistributable": False,
            }
        ],
    }


def test_reviewed_public_source_compiles_label_free_claim_candidates() -> None:
    result = compile_reviewed_public_source_objects(
        evidence_pack=_pack(), route_policy=_policy()
    )
    assert result.summary["unique_public_source_count"] == 1
    assert result.summary["public_source_content_slice_count"] == 1
    assert result.summary["canonical_source_record_count"] == 2
    assert result.summary["relevance_labels_copied_into_candidates"] is False
    source_ids = {row["evidence_id"] for row in result.source_records}
    assert "PUBLIC::DELL-EXT::TEST" in source_ids
    assert any(value.startswith("PUBLIC::DELL-EXT::TEST::SLICE::") for value in source_ids)
    assert any(row["object_kind"] == "claim" for row in result.objects)
    for row in result.objects:
        assert row["candidate_not_evidence"] is True
        assert row["numeric_authority"] is False
        assert row["lineage_source_record_ids"][0] == "PUBLIC::DELL-EXT::TEST"
        assert row["lineage_source_record_ids"][1].startswith(
            "PUBLIC::DELL-EXT::TEST::SLICE::"
        )
        assert row["base_object_view"]["source_record_id"] == row[
            "lineage_source_record_ids"
        ][1]
        rendered = json.dumps(row, ensure_ascii=False)
        assert "DELL-PROP-PRICE-CONFIGURATION" not in rendered
        assert "slot_bindings" not in rendered


def test_reviewed_public_source_fails_closed_on_content_digest_drift() -> None:
    pack = deepcopy(_pack())
    pack["source_materials"][0]["source_text"] += " changed"
    with pytest.raises(
        ReviewedPublicObjectCompilationError,
        match="public_source_text_digest_mismatch",
    ):
        compile_reviewed_public_source_objects(
            evidence_pack=pack, route_policy=_policy()
        )


def test_unreviewed_public_material_is_not_indexed() -> None:
    pack = _pack()
    extra_text = "This unreviewed source must not enter the current index."
    pack["source_materials"].append(
        {
            "material_ref": "material-unreviewed",
            "source_record_id": "PUBLIC::DELL-EXT::UNREVIEWED",
            "source_type": "PUBLIC_WEB",
            "source_tier": "trusted_media_industry_association_or_public_analyst_context",
            "evidence_owner_ticker": "ORG::UNREVIEWED",
            "speaker_entity": "Unreviewed Publisher",
            "publication_date": "2025-01-01",
            "source_url": "https://example.test/unreviewed",
            "source_text": extra_text,
            "source_text_digest": hashlib.sha256(extra_text.encode("utf-8")).hexdigest(),
        }
    )
    result = compile_reviewed_public_source_objects(
        evidence_pack=pack, route_policy=_policy()
    )
    assert result.summary["unique_public_source_count"] == 1
    assert all(
        "UNREVIEWED" not in str(row["base_object_view"]["source_record_id"])
        for row in result.objects
    )
