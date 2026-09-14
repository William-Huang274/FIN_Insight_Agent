"""Explicit one-request live DeepSeek qualification; never default pytest work."""
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from dotenv import dotenv_values
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage
from pydantic import SecretStr

from test_native_server_runtime import native
from sec_agent.adapters.model_dispatch_store import ModelDispatchStore
from sec_agent.agent_runtime.case_review_agent import CaseModelAudit, case_chat_model
from sec_agent.agent_runtime.deepseek_structured_agents import TokenBudgetBasis, DeepSeekModelProfile
from sec_agent.agent_runtime.model_dispatch_guard import ModelDispatchGuard, TokenPrices
from sec_agent.agent_runtime.usage_pricing import dated_public_cost, peak_multiplier

pytestmark = [pytest.mark.paid_model, pytest.mark.skipif(
    os.getenv('FIN_NATIVE_QUALIFICATION')!='1' or os.getenv('FIN_PAID_STREAM_PROBE')!='1',
    reason='requires explicit isolated runtime AND one-call paid authority')]


def synthetic_arithmetic_check(answer):
    """Only this fixed synthetic prompt; no general financial-quality adjudication."""
    percentages = [Decimal(value) for value in re.findall(r'([+-]?\d+(?:\.\d+)?)\s*%', answer)]
    changes = [Decimal(value) for value in re.findall(r'([+-]?\d+(?:\.\d+)?)\s*(?:个)?百分点', answer)]
    return {'arithmetic_matches_fixed_input': percentages == [Decimal(25), Decimal(10), Decimal(12)]
            and changes == [Decimal(2)],
            'synthetic_label_present': '合成样本' in answer,
            'three_nonempty_lines': len([line for line in answer.splitlines() if line.strip()]) == 3}


def test_one_real_stream_settles_and_checkpoint_replays_without_resend(native):
    # Only this process receives the existing DS key, never the Docker graph.
    key=os.getenv('DEEPSEEK_API_KEY') or dotenv_values(Path.cwd()/'.env').get('DEEPSEEK_API_KEY')
    if not key: raise RuntimeError('existing_deepseek_key_missing')
    timestamp=datetime.now(timezone.utc).isoformat()
    # This qualification pins the verified dated announcement, not an evergreen price cache.
    if not timestamp.startswith('2026-09-14'):
        raise RuntimeError('reverify_price_and_authority_before_new_date')
    profile=DeepSeekModelProfile(model='deepseek-v4-pro',thinking='disabled')
    rates=[int(Decimal(str(dated_public_cost(profile.model,*counts,timestamp)))*1000000)
           for counts in ((0,1000000,0),(1000000,0,0),(0,0,1000000))]
    prices=TokenPrices('deepseek-official-20260914:'+str(peak_multiplier(timestamp)),profile.model,'CNY',*rates)
    basis=TokenBudgetBasis(node_role='specialist',node_purpose='One real streaming SDK/usage/PG settlement and saved-node replay qualification',
        input_scale='One Chinese synthetic two-period revenue/profit message; measured SDK payload at most2000 UTF8 bytes',
        required_outputs=('Three short lines: revenue growth, two operating margins and percentage-point change; label synthetic',),
        schema_burden='Plain AIMessage without tools or structured-output wrapper',
        materiality_quality_risk='Check terminal response/usage and arithmetic only; not real company research, advice or general financial quality',
        comparable_run_evidence='E1 SDK MockTransport26 targeted tests; PG/native replay and actual writer factory qualified in007',
        reasoning_profile='agentic_message_history_thinking_disabled',max_input_characters=10000,
        max_output_tokens=1000,timeout_seconds=120,max_transport_attempts=1,retry_policy='none',
        truncation_stop_behavior='fail_closed_no_partial_promotion',input_ceiling_behavior='fail_before_transport')
    prompt='合成数据，不对应真实公司。上期收入120万元、营业利润12万元；本期收入150万元、营业利润18万元。请用中文给出收入同比、两期营业利润率，以及利润率变化（百分点）。只用本段数字，不查网、不调用工具。三行答案并注明合成样本，不生成投资建议。'
    store=ModelDispatchStore('postgresql://probe:'+native.env['FIN_E1_POSTGRES_PASSWORD']+'@127.0.0.1:18416/probe')
    store.install()
    store.create_budget('qualification-owner','one-real-stream','CNY',100000,10000)
    public,private,http_calls=[],[],[]
    def record(event):
        public.append(event)
        with (native.output/'paid_events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(event,ensure_ascii=False)+'\n')
    def private_record(event):
        private.append(event)
        with (native.output/'private_model_audit.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(event,ensure_ascii=False)+'\n')
    async def request_hook(request):
        if http_calls: raise RuntimeError('one_real_request_limit_no_resend')
        if request.url.host!='api.deepseek.com' or request.url.path!='/chat/completions':
            raise RuntimeError('unexpected_provider_endpoint')
        http_calls.append({'timestamp':datetime.now(timezone.utc).isoformat(),'method':request.method,'path':request.url.path})
        native.save('paid_http_dispatches',http_calls)
    async def exercise():
        async with httpx.AsyncClient(event_hooks={'request':[request_hook]},timeout=120,follow_redirects=False) as client:
            model=case_chat_model(profile,basis,SimpleNamespace(base_url='https://api.deepseek.com'),SecretStr(key),streaming=True)
            # Use the real SDK with a bounded, observable HTTP client; no transport replacement.
            model=type(model)(model=profile.model,api_key=SecretStr(key),base_url='https://api.deepseek.com',
                max_tokens=1000,timeout=120,max_retries=0,streaming=True,stream_usage=True,use_responses_api=False,
                http_async_client=client,extra_body={'thinking':{'type':'disabled'}})
            payload=model._get_request_payload([HumanMessage(content=prompt)])
            size=len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))
            if size>2000: raise RuntimeError('probe_input_exceeds_registered_scale')
            # Conservative scenario, not a universal tokenizer/remote-invoice hard bound:
            # <=2000 payload bytes +4096 framing allowance at cache-miss rate, full1000 output.
            reservation=((2000+4096)*prices.input_miss+1000*prices.output+999999)//1000000
            if reservation>90000: raise RuntimeError('probe_reservation_exceeds_authority')
            native.save('paid_preflight',{'timestamp':timestamp,'model':profile.model,'basis':basis.model_dump(mode='json'),
                'prompt':prompt,'payload_utf8_bytes':size,'prices':asdict(prices),'reservation_micros':reservation,
                'root_limit_micros':100000,'delivery_floor_micros':10000,'max_provider_requests':1,
                'price_source':'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
                'reservation_basis':'2000 UTF8 bytes +4096 framing tokens at miss tariff +1000 output; bounded conservative scenario, not invoice guarantee'})
            audit=CaseModelAudit(actor='one-real-stream',profile=profile,basis=basis,public_sink=record,private_sink=private_record,
                dispatch_guard=ModelDispatchGuard(store,owner='qualification-owner',budget='one-real-stream',prices=prices,
                    reservation_micros=reservation,reservation_basis='Registered2000-byte prompt+4096 framing allowance and1000 output at dated miss tariff'))
            runnable=audit.model_runnable(model)
            fail_once=True
            async def node(state,config):
                nonlocal fail_once
                raw=await runnable.ainvoke([HumanMessage(content=prompt)],config)
                if fail_once:
                    fail_once=False
                    raise RuntimeError('synthetic_failure_after_real_response_saved')
                return {'answer':raw.text}
            graph=StateGraph(dict).add_node('one_model',node).add_edge(START,'one_model').add_edge('one_model',END).compile(checkpointer=InMemorySaver())
            config={'configurable':{'thread_id':'one-real-stream'}}
            try:
                await graph.ainvoke({},config)
            except RuntimeError as exc:
                if str(exc)!='synthetic_failure_after_real_response_saved': raise
            else: raise AssertionError('expected_post_response_failure')
            # Resume only after the known saved response; unknown requests never enter this branch.
            return await graph.ainvoke(None,config)
    try:
        result=asyncio.run(exercise())
        snapshot=store.snapshot('qualification-owner','one-real-stream')
        native.save('paid_result',{'answer':result['answer'],'snapshot':snapshot,'provider_requests':len(http_calls),
            'replays':sum(e.get('event')=='replay' for e in public),'price_is_public_estimate_not_invoice':True,
            'synthetic_output_checks':synthetic_arithmetic_check(result['answer'])})
        assert len(http_calls)==1 and sum(e.get('event')=='replay' for e in public)==1
        assert snapshot['known']>0 and snapshot['held']==0
        assert synthetic_arithmetic_check(result['answer'])['arithmetic_matches_fixed_input']
    finally:
        native.save('paid_final_snapshot',store.snapshot('qualification-owner','one-real-stream'))
