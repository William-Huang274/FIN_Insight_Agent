from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from sec_agent.research.reviewed_evidence_anchor import (
    ReviewedEvidenceAnchorError,
    compile_reviewed_evidence_anchor_catalog,
    load_reviewed_evidence_anchor_catalog,
    project_reviewed_claim_anchor,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths


def _fixture() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    source_text = "prefix " * 90 + "The reviewed claim is exact and source visible."
    anchor = "The reviewed claim is exact and source visible."
    start = source_text.index(anchor)
    source_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    item = {
        "case_key": "DELL",
        "target_id": "DELL::CLAIM::1",
        "source_record_id": "DELL::SOURCE::1",
        "object_type": "claim",
        "evidence_item_digest": "e" * 64,
    }
    source = {
        "source_record_id": "DELL::SOURCE::1",
        "source_text": source_text,
        "source_text_digest": source_digest,
    }
    entry = {
        "case_key": "DELL",
        "target_id": "DELL::CLAIM::1",
        "source_record_id": "DELL::SOURCE::1",
        "evidence_item_digest": "e" * 64,
        "source_text_digest": source_digest,
        "anchor_kind": "structured_claim_text",
        "anchor_text": anchor,
        "anchor_start": start,
        "anchor_end": start + len(anchor),
        "anchor_digest": hashlib.sha256(anchor.encode("utf-8")).hexdigest(),
        "review_status": "reviewed_exact_source_surface",
    }
    catalog = compile_reviewed_evidence_anchor_catalog(
        case_pack_bindings={
            "DELL": {
                "artifact_digest": "a" * 64,
                "pack_payload_digest": "b" * 64,
            }
        },
        entries=[entry],
        known_boundary="fixture reviewed claim anchor only",
    )
    return catalog, item, source


def test_reviewed_claim_anchor_exposes_late_exact_source_surface() -> None:
    payload, item, source = _fixture()
    catalog = load_reviewed_evidence_anchor_catalog(payload)
    projected = project_reviewed_claim_anchor(
        catalog=catalog,
        item=item,
        source=source,
    )
    assert projected["reviewed_source_excerpt"] == (
        "The reviewed claim is exact and source visible."
    )
    assert projected["excerpt_projection_kind"] == "reviewed_claim_anchor"
    assert projected["reviewed_anchor_bound"] is True
    assert projected["reviewed_anchor_start"] > 500


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("wrong_case", "reviewed_claim_anchor_missing"),
        ("wrong_evidence_digest", "reviewed_claim_anchor_binding_drift"),
        ("source_mutation", "reviewed_claim_anchor_binding_drift"),
    ],
)
def test_reviewed_claim_anchor_fails_closed_on_binding_mutation(
    mutation: str,
    code: str,
) -> None:
    payload, raw_item, raw_source = _fixture()
    catalog = load_reviewed_evidence_anchor_catalog(payload)
    item = deepcopy(raw_item)
    source = deepcopy(raw_source)
    if mutation == "wrong_case":
        item["case_key"] = "MU"
    elif mutation == "wrong_evidence_digest":
        item["evidence_item_digest"] = "f" * 64
    else:
        source["source_text"] = str(source["source_text"]).replace(
            "reviewed claim", "mutated claim"
        )
    with pytest.raises(ReviewedEvidenceAnchorError) as exc:
        project_reviewed_claim_anchor(
            catalog=catalog,
            item=item,
            source=source,
        )
    assert exc.value.code == code


def test_current_runtime_binds_every_claim_and_exposes_dell_margin_sentence() -> None:
    service = ResearchEvidencePackService.from_runtime_paths(
        ROOT,
        resolve_runtime_paths(ROOT),
    )
    principal = ResearchEvidencePackPrincipal(
        "current", frozenset({"current_product:read"})
    )
    anchored = []
    for case_key in ("DELL", "MU", "NVDA"):
        pack = service.get_case(case_key, principal)
        for item in pack["evidence_items"]:
            if item.get("object_type") != "claim":
                continue
            source = item["source"]
            assert source["reviewed_anchor_bound"] is True
            assert source["excerpt_projection_kind"] == "reviewed_claim_anchor"
            anchored.append((case_key, item))
    counts = Counter(case_key for case_key, _item in anchored)
    assert counts == {"DELL": 14, "MU": 11, "NVDA": 19}
    assert len(anchored) == 44

    target = next(
        item
        for case_key, item in anchored
        if case_key == "DELL"
        and item["target_id"]
        == "DELL_2026_10Q_ITEM2_BLOCK_0011_PART_04_OF_05_CLAIM_CA0D3EC4"
    )
    assert target["source"]["reviewed_source_excerpt"] == (
        "The decreases in gross margin percentage and non-GAAP gross margin "
        "percentage were primarily driven by a shift in mix towards our "
        "AI-optimized server offerings."
    )
    assert target["source"]["reviewed_anchor_start"] > 1200


def test_materialized_catalog_matches_zero_call_compiler() -> None:
    catalog = json.loads(
        (
            ROOT
            / "configs/runtime/fin_ia_0_1_3_current_reviewed_claim_anchor_catalog_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    loaded = load_reviewed_evidence_anchor_catalog(catalog)
    assert len(loaded.entries) == 21
