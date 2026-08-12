from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "data_retrieval" / "materialize_s1c_requalified_qrels.py"
POLICY = ROOT / "configs" / "retrieval" / "fin_ia_0_1_3_s1c_ranking_comparison_policy_v1_0.json"
DECISION = ROOT / "configs" / "retrieval" / "fin_ia_0_1_3_s1c_owner_qrel_successor_decision_v1_0.json"


def _module():
    spec = importlib.util.spec_from_file_location("s1c_qrel_materializer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decision() -> dict[str, object]:
    return {
        **json.loads(DECISION.read_text(encoding="utf-8")),
        "_decision_ref": DECISION.as_posix(),
    }


def test_owner_successors_map_all_labels_and_bind_cash_flow_semantics() -> None:
    module = _module()
    result = module.materialize(
        json.loads(POLICY.read_text(encoding="utf-8")), _decision()
    )
    qrels = {row["qrel_id"]: row for row in result["qrels"]}

    assert result["summary"]["mapped_current_target_count"] == 18
    assert result["summary"]["typed_target_gap_count"] == 0
    assert result["summary"]["owner_successor_qrel_count"] == 4
    assert qrels["s1c_qrel_16"]["target_current_source_record_ids"] == [
        "CURRENT_DOC::NVDA::10_Q::0001045810_26_000052::ITEM_1::BLOCK_0001::PART_02_OF_04",
        "CURRENT_DOC::NVDA::10_Q::0001045810_26_000052::ITEM_1::BLOCK_0001::PART_03_OF_04",
    ]
    assert all(
        "PART_01_OF_04" not in target
        for target in qrels["s1c_qrel_16"]["target_current_source_record_ids"]
    )


def test_owner_successor_wrong_company_target_fails_closed() -> None:
    module = _module()
    decision = _decision()
    decision["decisions"] = [dict(row) for row in decision["decisions"]]
    decision["decisions"][0]["accepted_target_current_source_record_ids"] = [
        "CURRENT_DOC::MU::8_K::0000723125_26_000013::ITEM_CURRENT_REPORT::BLOCK_0002::PART_02_OF_03"
    ]

    with pytest.raises(ValueError, match="target_owner_mismatch"):
        module.materialize(
            json.loads(POLICY.read_text(encoding="utf-8")), decision
        )
