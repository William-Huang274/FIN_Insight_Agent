import asyncio
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage
from openai.types.chat import ChatCompletionChunk

from scripts.qualification import ai_memory_model_comparison as probe


def test_conditions_change_only_draft_and_profiles_share_messages(tmp_path, monkeypatch):
    source = ToolMessage(name="read_source_document", tool_call_id="s", content="Original period and units",
        artifact={"operation": "read", "items": [{"result_state": "source_bound_passage"}]})
    monkeypatch.setattr(probe, "archive_messages", lambda *args: ([source], {}))
    monkeypatch.setattr(probe, "public_records", lambda *args: ([], [{"content": source.content}]))
    for relative in ["20260912_phase_checkpoint_paid_r1/revision.md", "20260912_final_evidence_paid_r2/sk-control/answer.md"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        path.write_text("Fallible draft", encoding="utf-8")
    packs, _ = probe.inputs(tmp_path)
    for case in ["mu", "sk"]:
        a, b = packs[case + "-source-only"], packs[case + "-with-draft"]
        assert a[0] == b[0]
        before, after = json.loads(a[1]["content"]), json.loads(b[1]["content"])
        assert after.pop("candidate_draft_unverified") == "Fallible draft"
        assert before == after
        for profile in probe.PROFILES.values():
            assert probe.call_payload(profile, a)["messages"] == a


@pytest.mark.parametrize("known", [True, False])
def test_stream_usage_required_and_private_reasoning_not_in_answer(tmp_path, monkeypatch, known):
    monkeypatch.setenv("QWEN_API_KEY", "fake-test-key")
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.chat = SimpleNamespace(completions=self)
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def create(self, **kwargs):
            assert kwargs["max_completion_tokens"] == 12000
            assert kwargs["extra_body"]["thinking_budget"] == 8192
            async def chunks():
                yield ChatCompletionChunk.model_validate({"id": "response", "created": 1, "model": "qwen3.8-max",
                    "object": "chat.completion.chunk", "choices": [{"index": 0, "finish_reason": "stop",
                    "delta": {"content": "Public answer", "reasoning_content": "Private reasoning"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30} if known else None})
            return chunks()
    monkeypatch.setattr(probe, "AsyncOpenAI", Client)
    output = tmp_path / "run"
    call = probe.once("qwen-max", "mu-source-only", [{"role": "user", "content": "question"}], output)
    if known:
        asyncio.run(call)
    else:
        with pytest.raises(RuntimeError, match="no_automatic_retry"):
            asyncio.run(call)
        assert (output / "failure.json").is_file()
    assert (output / "answer.md").read_text(encoding="utf-8") == "Public answer"
