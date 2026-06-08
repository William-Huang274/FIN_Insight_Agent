from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "merge_jsonl_shards.py"
SPEC = importlib.util.spec_from_file_location("merge_jsonl_shards", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_merge_jsonl_shards_enforces_unique_field(tmp_path: Path) -> None:
    left = tmp_path / "left.jsonl"
    right = tmp_path / "right.jsonl"
    left.write_text(json.dumps({"id": "a"}) + "\n", encoding="utf-8")
    right.write_text(json.dumps({"id": "b"}) + "\n", encoding="utf-8")

    summary = MODULE.merge_jsonl_shards(
        inputs=[left, right],
        output_path=tmp_path / "out.jsonl",
        summary_path=tmp_path / "summary.json",
        require_unique_field="id",
    )

    assert summary["status"] == "pass"
    assert summary["row_count"] == 2
    assert (tmp_path / "out.jsonl").read_text(encoding="utf-8").count("\n") == 2


def test_merge_jsonl_shards_reports_duplicates(tmp_path: Path) -> None:
    left = tmp_path / "left.jsonl"
    right = tmp_path / "right.jsonl"
    left.write_text(json.dumps({"id": "a"}) + "\n", encoding="utf-8")
    right.write_text(json.dumps({"id": "a"}) + "\n", encoding="utf-8")

    summary = MODULE.merge_jsonl_shards(
        inputs=[left, right],
        output_path=tmp_path / "out.jsonl",
        summary_path=tmp_path / "summary.json",
        require_unique_field="id",
    )

    assert summary["status"] == "fail"
    assert summary["duplicate_count"] == 1
