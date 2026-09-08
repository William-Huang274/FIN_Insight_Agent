"""Qualification failures must retain actual text and stop further paid work."""
import asyncio
import json
from types import SimpleNamespace

import pytest
import openai
from scripts.qualification.context_transfer_compare import run_arm


@pytest.mark.parametrize("finish,reasoning,error", [("stop", 0, json.JSONDecodeError),
    ("length", 0, RuntimeError), ("stop", 20, RuntimeError)])
def test_failed_probe_keeps_public_output_without_private_reasoning(tmp_path, monkeypatch, finish, reasoning, error):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,
            message=SimpleNamespace(content="Candidate output before failure", reasoning_content="PRIVATE REASONING"))],
            usage=SimpleNamespace(model_dump=lambda: {"completion_tokens": 30,
                "completion_tokens_details": {"reasoning_tokens": reasoning}}))
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create))))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "offline-test-only")
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"actor": "fixture", "messages": [{"role": "user", "content": "Read-only fixture."}]}), encoding="utf-8")
    output = tmp_path / "attempt"
    args = SimpleNamespace(input=str(source), output=str(output), arm="unchanged", probe_file=None,
        probe_envelope="continuation", reuse_projection=None)
    with pytest.raises(error):
        asyncio.run(run_arm(args))
    assert len(calls) == 1
    saved = (output / "response-1.json").read_text(encoding="utf-8")
    assert "Candidate output before failure" in saved and "PRIVATE" not in saved
    assert (output / "token-budget-basis.json").exists()
