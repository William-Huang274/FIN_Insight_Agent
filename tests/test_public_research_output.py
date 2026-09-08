import json
from sec_agent.agent_runtime.public_research_output import submitted_prose
from scripts.diagnostics.recover_public_research_outputs import recover


def test_legacy_recovery_retains_candidate_and_never_requests_or_reasoning(tmp_path):
    raw = {"actor": "specialist", "call_id": "call1", "messages": [{"content": "PRIVATE REQUEST"}],
        "raw_response": {"content": "PRIVATE PREAMBLE", "additional_kwargs": {"reasoning_content": "PRIVATE REASONING"},
            "tool_calls": [{"id": "submission1", "name": "SubmitWorkpaperAction", "args": {
                "narrative_markdown": "Source-bound candidate with a disclosed limitation.", "private_extra": "PRIVATE EXTRA"}}]}}
    source = tmp_path / "model-context-reasoning.private.jsonl"
    source.write_text(json.dumps(raw), encoding="utf-8")
    (tmp_path / "model-call-events.jsonl").write_text(json.dumps({"call_id": "call1", "recorded_at": "2026-09-09T00:00:00Z"}), encoding="utf-8")
    before = source.read_bytes()
    result = recover(tmp_path)
    recovered = (tmp_path / "public-output-recovery.json").read_text(encoding="utf-8")
    assert result["recovered_outputs"] == 1 and "PRIVATE" not in recovered
    assert source.read_bytes() == before and "recovered_candidate" in recovered
    assert submitted_prose("read_secret", {"narrative_markdown": "must not expose"}) is None


def test_complete_prose_retained_without_character_truncation():
    text = "Detailed research output with limitation. " * 800
    assert submitted_prose("submit_case_report", {"report": {"narrative_markdown": text}}) == text
