"""Trusted host ownership/role policy must not be replaced by graph input."""
from dataclasses import asdict
from unittest.mock import MagicMock

import pytest
from sec_agent.adapters.model_dispatch_store import DispatchBlocked
from sec_agent.agent_runtime import research_budget as module
from sec_agent.agent_runtime.model_dispatch_guard import TokenPrices
from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile


def test_host_binding_cannot_be_minted_or_reassigned_by_native_metadata(monkeypatch):
    store=MagicMock()
    store.snapshot.return_value={'currency':'CNY'}
    factory=MagicMock(return_value=store)
    monkeypatch.setattr(module,'ModelDispatchStore',factory)
    prices=TokenPrices('synthetic','deepseek-v4-pro','CNY',1000000,0,2000000)
    policy={'reservation_micros':600,'reservation_basis':'Synthetic wire qualification','delivery':False}
    settings={'model_budget_bindings':{'thread':{'owner_id':'alice','budget_id':'approved-root',
        'prices':[asdict(prices)],'roles':{'specialist':policy}}}}
    for thread, metadata in [('thread',{}),('thread',{'owner_id':'bob'}),('other',{'owner_id':'alice'})]:
        with pytest.raises(DispatchBlocked,match='owner_binding_missing'):
            module.budget_from_host(settings,thread_id=thread,metadata=metadata,environment={})
    factory.assert_not_called()
    budget=module.budget_from_host(settings,thread_id='thread',metadata={
        'owner_id':'alice','budget_id':'forged-root','limit_micros':99999999,'delivery':True},
        environment={'POSTGRES_URI':'synthetic-not-a-credential'})
    guard=budget.guard('specialist',DeepSeekModelProfile(model=prices.model,thinking='disabled'))
    assert (guard.owner,guard.budget,guard.delivery)==('alice','approved-root',False)
    store.snapshot.assert_called_once_with('alice','approved-root')
    store.create_budget.assert_not_called()
    with pytest.raises(DispatchBlocked,match='not_authorized'):
        budget.guard('unapproved-role',DeepSeekModelProfile(model=prices.model,thinking='disabled'))
    with pytest.raises(DispatchBlocked,match='not_authorized'):
        budget.guard('specialist',DeepSeekModelProfile(model='deepseek-v4-flash',thinking='disabled'))


def test_absent_host_opt_in_keeps_existing_behavior():
    assert module.budget_from_host({},thread_id='t',metadata={},environment={}) is None


def test_delivery_authority_requires_boolean_host_policy():
    budget=module.ResearchBudget(MagicMock(),owner='alice',budget='root',
        prices={'deepseek-v4-pro':TokenPrices('synthetic','deepseek-v4-pro','CNY',1,0,1)},
        roles={'specialist':{'reservation_micros':1,'reservation_basis':'test','delivery':'false'}})
    with pytest.raises(DispatchBlocked,match='policy_invalid'):
        budget.guard('specialist',DeepSeekModelProfile(model='deepseek-v4-pro',thinking='disabled'))
