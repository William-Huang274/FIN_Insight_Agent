import json
import sys

import pytest

from scripts.qualification.dell_q1_specialist_paid_shadow import compare_review_model_once as diagnostic


@pytest.mark.parametrize("additional", ["PASSAGE:B", "PASSAGE:UNKNOWN"])
def test_prepare_uses_only_original_observations_without_credentials(tmp_path, monkeypatch, capsys, additional):
    def observation(ref):
        return {"references": [{"ref_id": ref}], "content": [{"passage_id": ref, "passage": f"Original {ref}"}]}
    source = {"actor": "specialist:fixture", "call_id": "original-call", "messages": [],
        "raw_response": {"tool_calls": [{"name": "SubmitWorkpaperAction", "args": {
            "claims": [{"claim_id": "C1", "evidence_ids": ["PASSAGE:A"]}]}}]},
        "semantic_input": {"progress": {"observations": [observation("PASSAGE:A"), observation("PASSAGE:A"),
            observation("PASSAGE:B"), observation("PASSAGE:C")]}, "task_context": {"question": "Compare evidence"}}}
    archive, extra, basis = (tmp_path / name for name in ("archive.jsonl", "extra.json", "budget.md"))
    archive.write_text(json.dumps(source), encoding="utf-8")
    extra.write_text(json.dumps([additional]), encoding="utf-8")
    basis.write_text("One bounded diagnostic; no automatic retry.", encoding="utf-8")
    output = tmp_path / "prepared"
    monkeypatch.setattr(diagnostic, "_dotenv", lambda: pytest.fail("prepare must not load credentials"))
    monkeypatch.setattr(sys, "argv", ["diagnostic", "--source-audit", str(archive), "--output-dir", str(output),
        "--task", "submission", "--model", "deepseek-v4-flash", "--effort", "low", "--prepare-only",
        "--budget-basis", str(basis), "--additional-source-ids", str(extra)])
    if additional.endswith("UNKNOWN"):
        with pytest.raises(ValueError, match="additional_source_must_be_observed"):
            diagnostic.main()
        return
    diagnostic.main()
    messages = json.loads((output / "messages.private.json").read_text(encoding="utf-8"))
    packet = json.loads(messages[1]["content"])
    assert [o["content"][0]["passage_id"] for o in packet["observations"]] == ["PASSAGE:A", "PASSAGE:B"]
    assert "prepared_no_model_call" in capsys.readouterr().out
