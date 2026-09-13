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
