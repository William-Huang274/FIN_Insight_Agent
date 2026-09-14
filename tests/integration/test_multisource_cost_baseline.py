"""Opt-in single-agent cost baseline over a prepared project, not full-chain acceptance."""
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values
from langchain_core.messages import HumanMessage, messages_to_dict
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import SecretStr

from test_native_server_runtime import native
from sec_agent.adapters.model_dispatch_store import ModelDispatchStore
from sec_agent.agent_runtime.case_review_agent import CaseModelAudit
from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis, ReasoningPreservingChatDeepSeek
from sec_agent.agent_runtime.model_dispatch_guard import ModelDispatchGuard, TokenPrices
from sec_agent.agent_runtime.report_session import session_audit_sinks
from sec_agent.agent_runtime.usage_pricing import peak_multiplier
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from sec_agent.research_foundation.project_asset_access import task_access_check


def load_case():
    path = Path(os.environ['FIN_MULTISOURCE_MANIFEST'])
    case = json.loads(path.read_text(encoding='utf-8'))
    prepared = Path(os.environ['FIN_MULTISOURCE_PREPARED'])
    receipt = json.loads((prepared/'readback.json').read_text(encoding='utf-8'))
    spec = json.loads(Path(os.environ['FIN_MULTISOURCE_PROFILE']).read_text(encoding='utf-8'))
    basis = TokenBudgetBasis.model_validate_json(json.dumps(spec['basis']))
    profile = DeepSeekModelProfile.model_validate_json(json.dumps(spec['profile']))
    return case, prepared, receipt, spec, basis, profile


@pytest.mark.paid_model
@pytest.mark.skipif(os.getenv('FIN_PAID_MULTISOURCE') != '1' or os.getenv('FIN_NATIVE_QUALIFICATION') != '1'
                   or os.getenv('FIN_RETIRED_PREFLIGHT_OVERRIDE') != 'user-approved-maintained-checks',
                   reason='explicit scoped paid baseline and user-approved retired-preflight replacement required')
def test_single_agent_multisource_cost_baseline(native, monkeypatch):
    case, prepared, receipt, spec, basis, profile = load_case()
    for flag in ('LANGSMITH_TRACING', 'LANGCHAIN_TRACING_V2'):
        monkeypatch.setenv(flag, 'false')
    now = datetime.now(timezone.utc).isoformat()
    if not now.startswith(spec['price_verified_date']):
        raise RuntimeError('reverify_price_and_task_authority_for_new_date')
    key = os.getenv('DEEPSEEK_API_KEY') or dotenv_values(Path.cwd()/'.env').get('DEEPSEEK_API_KEY')
    if not key:
        raise RuntimeError('existing_deepseek_key_missing')
    tid = receipt['thread_id']
    attachments = TaskAttachmentStore(prepared/'attachments')
    assert attachments.list(tid) == receipt['materials']
    for source in case['sources']:
        assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() == source['sha256']
    multiplier = peak_multiplier(now)
    prices = TokenPrices('official-'+spec['price_verified_date']+f'-x{multiplier}', profile.model, 'CNY',
        4500000*multiplier, 150000*multiplier, 13500000*multiplier)
    store = ModelDispatchStore('postgresql://probe:'+native.env['FIN_E1_POSTGRES_PASSWORD']+'@127.0.0.1:18416/probe')
    store.install()
    store.create_budget('multisource-baseline', tid, 'CNY', spec['root_limit_micros'], 0)
    reservation = ((spec['max_payload_bytes']+4096)*prices.input_miss+basis.max_output_tokens*prices.output+999999)//1000000
    guard = ModelDispatchGuard(store, owner='multisource-baseline', budget=tid, prices=prices,
        reservation_micros=reservation, reservation_basis='Registered payload byte ceiling plus4096 framing allowance and full output ceiling; conservative scenario, not invoice guarantee')
    public, private = session_audit_sinks(native.output/'audit')
    access = task_access_check({'FINSIGHT_TASK_ATTACHMENTS_ROOT': str(attachments.root), 'FINSIGHT_TASK_THREAD_ID': tid})
    dispatches = []
    async def hook(request):
        if request.url.host != 'api.deepseek.com' or request.url.path != '/chat/completions':
            raise RuntimeError('unexpected_provider_endpoint')
        if len(dispatches) >= spec['model_calls'] or len(request.content) > spec['max_payload_bytes']:
            raise RuntimeError('registered_request_or_payload_limit')
        if peak_multiplier(datetime.now(timezone.utc).isoformat()) != multiplier:
            raise RuntimeError('price_window_changed_no_resend')
        dispatches.append({'at': datetime.now(timezone.utc).isoformat(), 'bytes': len(request.content),
                           'sha256': hashlib.sha256(request.content).hexdigest()})
        native.save('http_dispatches', dispatches)
    source_map = [{'name': Path(s['path']).name, 'url': s['url'], 'publication_date': s['publication_date'], 'role': s['role']} for s in case['sources']]
    prompt = case['question']+'\n宿主资料目录与使用边界（不是研究答案）：'+json.dumps(source_map, ensure_ascii=False)
    prompt += '\n已证访问问题：'+json.dumps(case['open_source_issues'], ensure_ascii=False)
    native.save('paid_preflight', {'case': case, 'spec': spec, 'prices': asdict(prices), 'reservation_micros': reservation,
        'qualification_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'single existing conversation agent, selected sources, SQLite native checkpoints, PG budget; no independent reviewer or full research chain'})
    async def exercise():
        async with httpx.AsyncClient(event_hooks={'request': [hook]}, timeout=basis.timeout_seconds, follow_redirects=False) as client:
            model = ReasoningPreservingChatDeepSeek(model=profile.model, api_key=SecretStr(key), base_url='https://api.deepseek.com',
                max_tokens=basis.max_output_tokens, timeout=basis.timeout_seconds, max_retries=0,
                http_async_client=client, use_responses_api=False, extra_body={'thinking': {'type': profile.thinking}},
                **({'reasoning_effort': profile.reasoning_effort} if profile.thinking == 'enabled' else {}))
            audit = CaseModelAudit(actor='multisource-baseline', profile=profile, basis=basis, public_sink=public,
                private_sink=private, dispatch_guard=guard, source_access_check=access)
            async with AsyncSqliteSaver.from_conn_string(str(native.output/'checkpoints.sqlite')) as saver:
                graph = build_conversation_agent(model=model, grants=conversation_tools(thread_id=tid, attachment_store=attachments),
                    permission_mode='request_standard', checkpointer=saver, middleware=[audit],
                    model_calls=spec['model_calls'], tool_calls=spec['tool_calls'])
                return await graph.ainvoke({'messages': [HumanMessage(content=prompt)]},
                    {'configurable': {'thread_id': tid}, 'recursion_limit': 160})
    try:
        result = asyncio.run(exercise())
        native.save('messages.private', messages_to_dict(result['messages']))
        final = result['messages'][-1]
        (native.output/'research-brief.md').write_text(final.text, encoding='utf-8')
        assert final.type == 'ai' and final.text.strip() and not final.tool_calls
    finally:
        native.save('paid_final_snapshot', store.snapshot('multisource-baseline', tid))
