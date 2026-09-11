from threading import Event, Thread
import pytest
from sec_agent.agent_runtime.research_session_runtime import cancellable_model_turn


def test_cancelled_inflight_worker_keeps_receipt_but_cannot_dispatch_again():
    started, release, cancelled = Event(), Event(), Event()
    receipts, errors = [], []
    def provider(request):
        started.set()
        assert release.wait(2)
        receipts.append({'usage':123})
        return {'action':{'tool_calls':[{'name':'paid_followup'}]}}
    wrapped = cancellable_model_turn(provider, cancelled)
    def worker():
        try: wrapped({})
        except RuntimeError as exc: errors.append(str(exc))
    thread=Thread(target=worker); thread.start()
    assert started.wait(2)
    cancelled.set(); release.set(); thread.join(2)
    assert not thread.is_alive()
    assert receipts == [{'usage':123}]
    assert errors == ['research_cancelled_after_model_call']
    with pytest.raises(RuntimeError,match='before_model_call'): wrapped({})
    assert len(receipts)==1


def test_uncancelled_worker_returns_its_real_result():
    assert cancellable_model_turn(lambda r: r,Event())({'result':1}) == {'result':1}
