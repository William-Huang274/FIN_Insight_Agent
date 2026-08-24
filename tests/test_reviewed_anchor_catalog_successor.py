from __future__ import annotations

from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/research/materialize_reviewed_anchor_catalog_successor.py"
PROGRAM = ROOT / "configs/research/fin_ia_0_1_3_s1_dell_direct_source_anchor_successor_program_v1_0.json"


def _module():
    spec = spec_from_file_location("reviewed_anchor_catalog_successor", SCRIPT)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inputs() -> tuple[dict, dict, dict]:
    program = _json(PROGRAM)
    predecessor = _json(ROOT / program["predecessor_catalog_binding"]["ref"])
    target = _json(ROOT / program["target_pack_binding"]["ref"])
    return program, predecessor, target


def test_dell_r4_anchor_successor_is_exhaustive_and_preserves_other_cases() -> None:
    module = _module()
    program, predecessor, target = _inputs()
    result = module.compile_anchor_catalog_successor(
        program=program,
        predecessor_catalog=predecessor,
        target_pack=target,
        target_pack_artifact_digest=program["target_pack_binding"]["artifact_digest"],
    )

    assert result["new_evidence_item_digests"] == sorted(
        row["evidence_item_digest"] for row in program["new_anchor_decisions"]
    )
    assert result["removed_evidence_item_digests"] == []
    assert result["predecessor_entry_count"] == 79
    assert result["successor_entry_count"] == 86
    assert result["catalog"]["case_pack_bindings"]["DELL"] == {
        "artifact_digest": program["target_pack_binding"]["artifact_digest"],
        "pack_payload_digest": program["target_pack_binding"][
            "pack_payload_digest"
        ],
    }
    assert result["authority"]["new_evidence_created"] is False
    assert result["authority"]["model_or_network_calls"] == 0


def test_anchor_successor_rejects_unreviewed_new_evidence() -> None:
    module = _module()
    program, predecessor, target = _inputs()
    mutated = deepcopy(program)
    mutated["new_anchor_decisions"] = mutated["new_anchor_decisions"][:-1]

    with pytest.raises(
        module.AnchorCatalogSuccessorError,
        match="anchor_successor_new_evidence_not_exhaustively_decided",
    ):
        module.compile_anchor_catalog_successor(
            program=mutated,
            predecessor_catalog=predecessor,
            target_pack=target,
            target_pack_artifact_digest=program["target_pack_binding"][
                "artifact_digest"
            ],
        )


def test_anchor_successor_rejects_non_source_surface() -> None:
    module = _module()
    program, predecessor, target = _inputs()
    mutated = deepcopy(program)
    mutated["new_anchor_decisions"][0]["anchor_text"] = (
        "This reviewer-authored sentence is not present in the captured source."
    )

    with pytest.raises(
        module.AnchorCatalogSuccessorError,
        match="anchor_successor_anchor_surface_invalid",
    ):
        module.compile_anchor_catalog_successor(
            program=mutated,
            predecessor_catalog=predecessor,
            target_pack=target,
            target_pack_artifact_digest=program["target_pack_binding"][
                "artifact_digest"
            ],
        )
