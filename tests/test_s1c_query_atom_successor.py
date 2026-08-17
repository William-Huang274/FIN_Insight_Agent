from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.query_atom_shadow import (  # noqa: E402
    QUERY_ATOM_EVAL_SCHEMA_VERSION,
    QUERY_ATOM_EVAL_SUCCESSOR_SCHEMA_VERSION,
    load_query_atoms,
)
from scripts.data_retrieval.materialize_s1c_runtime_query_atoms import (  # noqa: E402
    _labels_from_object_keys,
    _object_key_index,
)


SOURCE_EVAL = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_eval_v1_0.json"
)
SUCCESSOR_EVAL = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_eval_v1_1.json"
)
TARGET_OBJECTS = (
    ROOT
    / "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/v2/objects.jsonl"
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_index() -> tuple[dict[str, dict], dict[str, list[dict]]]:
    by_id: dict[str, dict] = {}
    by_key: dict[str, list[dict]] = {}
    with TARGET_OBJECTS.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            by_id[row["compiled_object_id"]] = row
            by_key.setdefault(row["base_object_view"]["object_key"], []).append(row)
    return by_id, by_key


def _atom(payload: dict, atom_id: str) -> dict:
    return next(row for row in payload["atoms"] if row["atom_id"] == atom_id)


def test_qrel_successor_preserves_requests_and_binds_only_current_objects() -> None:
    source = _read_json(SOURCE_EVAL)
    successor = _read_json(SUCCESSOR_EVAL)
    target_by_id, _ = _target_index()

    assert source["schema_version"] == QUERY_ATOM_EVAL_SCHEMA_VERSION
    assert successor["schema_version"] == QUERY_ATOM_EVAL_SUCCESSOR_SCHEMA_VERSION
    assert len(load_query_atoms(source)) == 18
    assert len(load_query_atoms(successor)) == 18
    assert successor["query_contract"]["unchanged"] is True
    assert successor["query_contract"]["source_query_digest"] == successor[
        "query_contract"
    ]["target_query_digest"]
    assert [row["request"] for row in successor["atoms"]] == [
        row["request"] for row in source["atoms"]
    ]
    for row in successor["atoms"]:
        target = row["request"]["target_entities"][0]
        for field in (
            "positive_object_ids",
            "hard_negative_object_ids",
            "unjudged_object_ids",
        ):
            for object_id in row["labels"][field]:
                assert object_id in target_by_id
                assert target_by_id[object_id]["base_object_view"]["ticker"] == target


def test_qrel_successor_replaces_fragment_and_reclassifies_weak_mu_quote() -> None:
    successor = _read_json(SUCCESSOR_EVAL)
    target_by_id, target_by_key = _target_index()

    fragment_key = (
        "CURRENT_DOC::NVDA::10_Q::0001045810_26_000052::ITEM_1A::"
        "BLOCK_0002::PART_03_OF_04::claim::06"
    )
    capacity_key = (
        "CURRENT_DOC::NVDA::10_Q::0001045810_26_000052::ITEM_1A::"
        "BLOCK_0002::PART_03_OF_04::claim::01"
    )
    fragment_id = target_by_key[fragment_key][0]["compiled_object_id"]
    capacity_id = target_by_key[capacity_key][0]["compiled_object_id"]

    for atom_id in (
        "S1C_ATOM_05_DELL_UPSTREAM_NVDA",
        "S1C_ATOM_11_MU_DOWNSTREAM_NVDA",
    ):
        labels = _atom(successor, atom_id)["labels"]
        assert fragment_id not in labels["positive_object_ids"]
        assert fragment_id in labels["hard_negative_object_ids"]
        assert capacity_id in labels["positive_object_ids"]
        assert target_by_id[capacity_id]["model_text"].startswith(
            "We continue to increase our supply and capacity purchases"
        )

    weak_quote_key = (
        "CURRENT_DOC::MU::8_K::0000723125_26_000013::ITEM_CURRENT_REPORT::"
        "BLOCK_0002::PART_01_OF_03::claim::04"
    )
    weak_quote_id = target_by_key[weak_quote_key][0]["compiled_object_id"]
    for atom_id in (
        "S1C_ATOM_04_DELL_UPSTREAM_MU",
        "S1C_ATOM_17_NVDA_UPSTREAM_MU",
    ):
        labels = _atom(successor, atom_id)["labels"]
        assert weak_quote_id not in labels["hard_negative_object_ids"]
        assert weak_quote_id in labels["unjudged_object_ids"]


def _object(object_id: str, key: str, ticker: str, text: str) -> dict:
    return {
        "compiled_object_id": object_id,
        "object_kind": "claim",
        "model_text": text,
        "base_object_view": {"object_key": key, "ticker": ticker},
        "structured_projection": {},
    }


def test_successor_locator_fails_closed_on_ambiguity_and_overlap() -> None:
    objects = {
        "A": _object("A", "KEY-A", "DELL", "first"),
        "B": _object("B", "KEY-A", "DELL", "second"),
    }
    index = _object_key_index(objects)
    with pytest.raises(ValueError, match="adjudication_locator_not_unique"):
        _labels_from_object_keys(
            {
                "positive_object_keys": ["KEY-A"],
                "hard_negative_object_keys": [],
                "unjudged_object_keys": [],
                "expected_roles_by_object_key": {},
            },
            target_by_key=index,
        )

    unique = _object_key_index({"A": objects["A"]})
    with pytest.raises(ValueError, match="adjudication_label_overlap"):
        _labels_from_object_keys(
            {
                "positive_object_keys": ["KEY-A"],
                "hard_negative_object_keys": ["KEY-A"],
                "unjudged_object_keys": [],
                "expected_roles_by_object_key": {},
            },
            target_by_key=unique,
        )


def test_successor_expected_roles_support_structured_metric_locator() -> None:
    first = _object("A", "TABLE-KEY", "NVDA", "Operating cash flow used")
    first["object_kind"] = "metric_row"
    first["structured_projection"] = {
        "metric_row_label": "Operating cash flow used for operating leases"
    }
    second = _object("B", "TABLE-KEY", "NVDA", "Net cash provided")
    second["object_kind"] = "metric_row"
    second["structured_projection"] = {
        "metric_row_label": "Net cash provided by operating activities"
    }
    index = _object_key_index({"A": first, "B": second})

    labels = _labels_from_object_keys(
        {
            "positive_object_keys": [
                {
                    "object_key": "TABLE-KEY",
                    "object_kind": "metric_row",
                    "metric_row_label": "Net cash provided by operating activities",
                }
            ],
            "hard_negative_object_keys": [
                {
                    "object_key": "TABLE-KEY",
                    "object_kind": "metric_row",
                    "metric_row_label": "Operating cash flow used for operating leases",
                }
            ],
            "unjudged_object_keys": [],
            "expected_roles_by_object_key": {},
            "expected_roles_by_locator": [
                {
                    "locator": {
                        "object_key": "TABLE-KEY",
                        "object_kind": "metric_row",
                        "metric_row_label": "Net cash provided by operating activities",
                    },
                    "roles": ["financial_statement_or_reconciliation"],
                },
                {
                    "locator": {
                        "object_key": "TABLE-KEY",
                        "object_kind": "metric_row",
                        "metric_row_label": "Operating cash flow used for operating leases",
                    },
                    "roles": ["financial_statement_or_reconciliation"],
                },
            ],
        },
        target_by_key=index,
    )

    assert labels["positive_object_ids"] == ["B"]
    assert labels["hard_negative_object_ids"] == ["A"]
    assert labels["expected_roles_by_object_id"] == {
        "A": ["financial_statement_or_reconciliation"],
        "B": ["financial_statement_or_reconciliation"],
    }
