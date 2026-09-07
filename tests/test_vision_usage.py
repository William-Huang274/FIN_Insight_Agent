import asyncio
from types import SimpleNamespace

import pytest

from sec_agent.research_foundation import vision_reader


@pytest.mark.parametrize("cache", [{}, {"prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 12},
    {"prompt_cache_hit_tokens": 8, "prompt_cache_miss_tokens": 4}])
def test_missing_vision_cache_usage_stays_unknown(monkeypatch, cache):
    usage = SimpleNamespace(prompt_tokens=12, completion_tokens=5, total_tokens=17, **cache)
    response = SimpleNamespace(usage=usage, choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="Revenue 100 USD; period unreadable."))])

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def create(self, **kwargs):
            return response

    monkeypatch.setattr(vision_reader, "AsyncOpenAI", Client)
    monkeypatch.setattr(vision_reader, "wrap_openai", lambda client: client)
    events = []
    read = vision_reader.task_vision_reader(api_key="test-placeholder", public_sink=events.append)
    assert "period unreadable" in asyncio.run(read(b"image-fixture", "Read revenue and period"))
    outcome = next(e for e in events if e["event"] == "outcome")
    assert outcome["input_tokens"] == 12 and outcome["usage_reported"]
    assert outcome["cache_hit_tokens"] == cache.get("prompt_cache_hit_tokens")
    assert outcome["cache_miss_tokens"] == cache.get("prompt_cache_miss_tokens")
