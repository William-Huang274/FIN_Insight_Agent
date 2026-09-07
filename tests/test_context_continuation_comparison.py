import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.qualification.context_continuation_comparison import BoundedAudit, run, settings


@pytest.mark.parametrize("remaining,flash", [(Path("closed-a1"), None), (None, Path("closed-a3"))])
def test_fresh_postfix_rejects_closed_batch_before_read_or_transport(tmp_path, remaining, flash):
    with pytest.raises(ValueError, match="fresh_postfix_cannot_reuse_closed_batch_authority"):
        asyncio.run(run(tmp_path, tmp_path, True, remaining, flash, postfix_summary=True))


@pytest.mark.parametrize("overrides", [{"calls": 5}, {"spent": 5.0}, {"unknown": True}])
def test_postfix_call_cost_and_unknown_limits_stop_before_transport(overrides):
    profile, basis, _, _ = settings(Path(__file__).resolve().parents[1], postfix=True)
    model = SimpleNamespace(_get_request_payload=lambda *a, **k: {"messages": [], "tools": []})
    shared = {"calls": 0, "spent": 0.0, "unknown": False, "max_calls": 5, **overrides}
    audit = BoundedAudit(shared=shared, model=model, actor="fixture", profile=profile, basis=basis,
        public_sink=lambda _: None, private_sink=lambda _: None)
    async def forbidden(_):
        pytest.fail("A closed budget must not reach provider transport")
    with pytest.raises(ValueError, match="context_batch_reserve_or_call_limit_before_transport"):
        asyncio.run(audit.awrap_model_call(SimpleNamespace(system_message=None, messages=[], tools=[]), forbidden))
