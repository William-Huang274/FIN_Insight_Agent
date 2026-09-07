from __future__ import annotations

import json

import pytest

from scripts.research import materialize_s1_s3_actionable_research_three_case as runner


def test_write_new_is_exact_once(tmp_path) -> None:
    output = tmp_path / "result.json"
    runner._write_new(output, {"status": "pass"})

    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "pass"}
    with pytest.raises(
        FileExistsError, match="three_case_generalization_output_exists"
    ):
        runner._write_new(output, {"status": "replacement_forbidden"})


def test_main_preflights_existing_output(monkeypatch, tmp_path) -> None:
    output = tmp_path / "already-there.json"
    output.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "materialize_s1_s3_actionable_research_three_case.py",
            "--attempt-id",
            "attempt-r1",
            "--output",
            str(output),
        ],
    )
    monkeypatch.setattr(
        runner,
        "materialize",
        lambda **_: pytest.fail("materialize must not run after output collision"),
    )

    with pytest.raises(
        FileExistsError, match="three_case_generalization_output_exists"
    ):
        runner.main()
