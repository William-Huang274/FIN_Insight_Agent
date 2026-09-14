"""One dated review/repair qualification on the immutable 019 author output.

Existing native agents, MCP and PG audit; no host findings injected, no rerun loop.
"""
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4, UUID

import httpx
from dotenv import dotenv_values
from langchain_core.messages import HumanMessage, messages_to_dict
from langgraph.checkpoint.memory import InMemorySaver
from mcp import Client
from mcp.server.mcpserver import MCPServer
from pydantic import SecretStr
import pytest

from test_native_server_runtime import native
from test_method_transfer_live import QUESTION, transfer_configuration
from sec_agent.adapters.model_dispatch_store import ModelDispatchStore
from sec_agent.agent_runtime.case_artifacts import CaseArtifacts, register_case_artifact_tools, revision_review_target
from sec_agent.agent_runtime.case_review_agent import CaseModelAudit, build_case_reviewer, build_case_review_graph, case_mcp_tools
from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek, TokenBudgetBasis
from sec_agent.agent_runtime.model_dispatch_guard import ModelDispatchGuard, TokenPrices
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent, paper_revision_input
from sec_agent.agent_runtime.research_session import responsible_author_feedback
from sec_agent.agent_runtime.usage_pricing import peak_multiplier
from sec_agent.research_foundation.project_asset_access import require_task_assets
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / '.local/fin014/20260914_e3_amzn_transfer_a1'
MAX_BYTES = 240000
LIMITS = {'counter': (8, 24), 'verifier': (8, 24), 'repair': (10, 24),
          'revision_counter': (6, 16), 'revision_verifier': (6, 16)}
MAX_CALLS = sum(v[0] for v in LIMITS.values())


def node_basis(actor):
    _, profile, prior = transfer_configuration()
    revision = actor.startswith('revision_')
    purpose = ('Reconcile independently reported findings in one responsible AMZN workpaper, preserving correct research' if actor == 'repair'
               else 'Independently inspect only changed claims/prose and necessary dependencies; leave unchecked scope explicit' if revision
               else 'Independently review the original AMZN workpaper and selected official release, without host findings')
    basis = TokenBudgetBasis.model_validate({**prior.model_dump(),
        'node_role': 'counter' if 'counter' in actor else 'specialist', 'node_purpose': purpose,
        'input_scale': 'One ten-claim paper and 38975-character/nine-block source, existing native tool schemas, saved exact calculations;240000 UTF8 bytes per request including history',
        'required_outputs': ('Read full workpaper or supplied revision-only target as appropriate',
            'Check material facts, quoted support, periods/units, inference strength and stated information boundaries against original sources',
            'Provide precise source-bound findings or reasoned disagreements; retain useful conditional hypotheses and correct claims',
            'Submit honest completion and unresolved checks; no product/whole-case acceptance from a partial review'),
        'schema_burden': ('Full replacement prose, changed claims with exact quotes and per-finding responses:8000 output tokens'
                         if actor == 'repair' else 'Native review schema, exact finding anchors/source quotes and explicit unfinished work:6000 output tokens'),
        'comparable_run_evidence': f'019 author6calls/171784tokens/max141265bytes;020 native saved-paper read/review/repair/scoped handoff works locally. No measured autonomous review cost yet. Actor {actor}: {LIMITS[actor][0]} calls allow paper/target read, source checks, calculation or feedback and submission; shared maximum38 calls, one author revision only. Ceiling is a failure boundary, not permission to omit required work.',
        'materiality_quality_risk': 'Wrong corrections, unchanged valid calculations lost, false nondisclosure or strengthened causal stories prevent acceptance. Exact quotes/pytest are not financial proof. Uploaded source remains non-S2.',
        'max_input_characters': MAX_BYTES, 'max_output_tokens': 8000 if actor == 'repair' else 6000})
    return profile, basis


def saved_source():
    seed = json.loads((SOURCE/'specialist_result.json').read_text(encoding='utf-8'))
    tid = str(UUID(seed['run_id'].removeprefix('amzn-transfer-')))
    store = TaskAttachmentStore(SOURCE/'product/attachments')
    require_task_assets(store, tid)
    return CaseArtifacts([seed]), store, tid


def source_server(artifacts, store, tid):
    server = MCPServer(name='fin-e3-saved-review')
    @server.tool(name='get_research_method', structured_output=True)
    def read_role_method(method_id: str = '') -> dict[str, Any]:
        """Read the existing answer-free method catalog or a selected role method; not evidence or extra authority."""
        from sec_agent.research_foundation.research_methods import get_research_method
        return get_research_method(method_id)

    observed = {}
    def lookup(ref):
        return observed[ref] if ref in observed else artifacts.source_item(ref)
    register_case_artifact_tools(server, artifacts, source_lookup=lookup,
                                 calculation_observer=lambda item: observed.update({item['calculation_id']: item}))

    @server.tool(name='read_source_document', structured_output=True)
    async def read_document(request: SourceDocumentRequest) -> dict[str, Any]:
        """Read only this task's selected original uploaded document; no web or other cases. Use uploads and the returned document IDs."""
        if request.source_space != 'uploads' or request.operation == 'inspect_image':
            raise ValueError('qualification_only_selected_text_uploads')
        require_task_assets(store, tid)
        result = (await store.read(thread_id=tid, request=request)).model_dump(mode='json')
        observed.update({item['passage_id']: item for item in result['items'] if item.get('passage_id')})
        return result
    return server


async def review_pipeline(make_agent, save):
    artifacts, store, tid = saved_source()
    original = artifacts.read_paper('P01')
    async with Client(source_server(artifacts, store, tid), raise_exceptions=False) as client:
        tools = await case_mcp_tools(client)
        reviewers = {r: make_agent(r, artifacts, tools) for r in ('counter', 'verifier')}
        graph = build_case_review_graph(reviewers=reviewers, artifacts=artifacts, question=QUESTION,
            run_id='review-019-original', run_invocation_id='review-019-original').compile(checkpointer=InMemorySaver())
        cfg = {'configurable': {'thread_id': str(uuid4())}, 'recursion_limit': 100}
        try:
            reviewed = await graph.ainvoke({'run_id': 'review-019-original', 'run_invocation_id': 'review-019-original'}, cfg)
        finally:
            state = await graph.aget_state(cfg)
            save('review_checkpoint', state.values)
        save('initial_review', reviewed)
        if reviewed['phase'] != 'case_review_ready_for_convergence':
            return {'status': 'review_incomplete_no_author_dispatch'}
        feedback = responsible_author_feedback(reviewed, artifacts)
        if not feedback:
            return {'status': 'review_no_material_findings_requires_host_assessment'}
        own = feedback['P01']
        save('author_feedback', own)
        author = make_agent('repair', artifacts, tools, feedback=own)
        repaired = await author.ainvoke({'messages': [HumanMessage(content=json.dumps({
            'question': QUESTION, **paper_revision_input(artifacts, 'P01', own)}, ensure_ascii=False))]},
            {'configurable': {'thread_id': str(uuid4())}, 'recursion_limit': 100})
        save('author_messages', messages_to_dict(repaired['messages']))
        if not repaired.get('output'):
            return {'status': 'author_incomplete_no_second_revision'}
        revision = repaired['output']
        save('revision', revision)
        current = artifacts.with_revisions({'P01': revision})
        target = revision_review_target(artifacts, 'P01', revision)
        save('revision_scope', target)
        # Existing scoped reviewers see the current saved sources, including any
        # new original-source observations made by the author.
        async with Client(source_server(current, store, tid), raise_exceptions=False) as updated:
            updated_tools = await case_mcp_tools(updated)
            for role in ('counter', 'verifier'):
                agent = make_agent('revision_'+role, current, updated_tools, revision_target=target)
                result = await agent.ainvoke({'messages': [HumanMessage(content=json.dumps({
                    'role': role, 'question': QUESTION,
                    'instruction': '独立复核所给修订范围，明确仍需核实的依赖；不扩大为整稿验收。'}, ensure_ascii=False))]},
                    {'configurable': {'thread_id': str(uuid4())}, 'recursion_limit': 80})
                save('revision_'+role+'_messages', messages_to_dict(result['messages']))
                save('revision_'+role, result.get('review'))
        assert artifacts.read_paper('P01') == original
        return {'status': 'one_revision_and_scoped_reviews_recorded_not_quality_acceptance'}


@pytest.mark.local_data_integration
def test_native_review_sdk_preflight(tmp_path, monkeypatch):
    for flag in ('LANGSMITH_TRACING', 'LANGCHAIN_TRACING_V2'):
        monkeypatch.setenv(flag, 'false')
    artifacts, store, tid = saved_source()
    wires = []
    async def serve(request):
        body = json.loads(request.content); wires.append(body)
        assert len(request.content) < MAX_BYTES and body['max_tokens'] == 6000
        messages = body['messages']
        if len(wires) == 1:
            name, args = 'get_research_method', {'method_id': 'counter'}
        elif len(wires) == 2:
            assert any(m['role'] == 'tool' and json.loads(m['content']).get('method_id') == 'counter' for m in messages)
            name, args = 'read_research_artifact', {'paper_id': 'P01', 'section': 'workpaper'}
        else:
            assert 'counterevidence' in json.dumps(messages, ensure_ascii=False)
            name, args = 'submit_case_review', {'review': {'summary': 'Local SDK preflight only; no autonomous financial review was executed.',
                'assessments': [{'paper_id': 'P01', 'assessment': 'The full original paper reached the native SDK; all semantic checks remain unperformed.'}],
                'completion': 'incomplete', 'unresolved_data_requests': ['Local transport fixture did not perform financial review.']}}
        return httpx.Response(200, json={'id': str(uuid4()), 'object': 'chat.completion', 'created': 1, 'model': 'deepseek-v4-pro',
            'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'content': '',
                'tool_calls': [{'id': str(uuid4()), 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 40, 'total_tokens': 140, 'prompt_cache_hit_tokens': 0}})
    async def exercise():
        async with Client(source_server(artifacts, store, tid), raise_exceptions=False) as client, httpx.AsyncClient(transport=httpx.MockTransport(serve)) as http:
            tools = await case_mcp_tools(client)
            reader = next(t for t in tools if t.name == 'read_source_document')
            result = await reader.ainvoke({'name': 'read_source_document', 'id': 'outline', 'type': 'tool_call',
                'args': {'request': {'source_space': 'uploads', 'operation': 'outline',
                                     'document_id': store.list(tid)[0]['document_id'], 'limit': 20}}})
            assert result.status == 'success', result.content
            assert len(result.artifact['items']) == 9
            profile, basis = node_basis('verifier')
            model = ReasoningPreservingChatDeepSeek(model=profile.model, api_key=SecretStr('local-fixture'), http_async_client=http,
                max_retries=0, max_tokens=basis.max_output_tokens, use_responses_api=False, extra_body={'thinking': {'type': 'disabled'}})
            audit = CaseModelAudit(actor='preflight', profile=profile, basis=basis, public_sink=lambda _: None, private_sink=lambda _: None)
            agent = build_case_reviewer(role='verifier', model=model, tools=tools, artifacts=artifacts, audit=audit, max_model_calls=3)
            output = await agent.ainvoke({'messages': [HumanMessage(content=QUESTION)]})
            assert output['review']['unresolved_data_requests']
    asyncio.run(exercise())
    assert len(wires) == 3
    for actor in LIMITS:
        assert node_basis(actor)[1].max_transport_attempts == 1


@pytest.mark.paid_model
@pytest.mark.local_data_integration
@pytest.mark.skipif(os.getenv('FIN_NATIVE_QUALIFICATION') != '1' or os.getenv('FIN_PAID_REVIEW_REPAIR') != '1', reason='explicit one-run review/repair qualification only')
def test_real_review_repair(native, monkeypatch):
    for flag in ('LANGSMITH_TRACING', 'LANGCHAIN_TRACING_V2'):
        monkeypatch.setenv(flag, 'false')
    key = os.getenv('DEEPSEEK_API_KEY') or dotenv_values(ROOT/'.env').get('DEEPSEEK_API_KEY')
    if not key:
        raise RuntimeError('existing_deepseek_key_missing')
    budget = ModelDispatchStore('postgresql://probe:'+native.env['FIN_E1_POSTGRES_PASSWORD']+'@127.0.0.1:18416/probe')
    budget.install()
    bid = str(uuid4())
    budget.create_budget('review-probe', bid, 'CNY', 8000000, 100000)
    prices = TokenPrices('deepseek-official-20260914-offpeak', 'deepseek-v4-pro', 'CNY', 4500000, 150000, 13500000)
    native.save('paid_preflight', {'nodes': {a: {'basis': node_basis(a)[1].model_dump(mode='json'), 'limits': LIMITS[a]} for a in LIMITS},
        'max_requests': MAX_CALLS, 'max_utf8_bytes': MAX_BYTES, 'root_micros': 8000000, 'delivery_floor_micros': 100000,
        'prices': asdict(prices), 'price_source': 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
        'source_sha256': hashlib.sha256((SOURCE/'specialist_result.json').read_bytes()).hexdigest(),
        'qualification_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'Original019 author output; no host findings/corrections supplied. One independent review, optional one author revision, scoped rereview. No lead/writer/full-chain, no unknown resend or paid tuning.'})
    dispatches = []
    def sink(name):
        def write(event):
            with (native.output/(name+'.jsonl')).open('a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False)+'\n')
        return write
    async def hook(request):
        now = datetime.now(timezone.utc).isoformat()
        digest = hashlib.sha256(request.content).hexdigest()
        if not now.startswith('2026-09-14') or peak_multiplier(now) != 1:
            raise RuntimeError('reverify_dated_tariff_before_new_dispatch')
        if request.url.host != 'api.deepseek.com' or request.url.path != '/chat/completions' or request.method != 'POST':
            raise RuntimeError('unexpected_provider_endpoint')
        if len(dispatches) >= MAX_CALLS or any(d['sha256'] == digest for d in dispatches) or len(request.content) > MAX_BYTES:
            raise RuntimeError('request_limit_duplicate_or_payload_boundary')
        dispatches.append({'at': now, 'bytes': len(request.content), 'sha256': digest})
        native.save('http_dispatches', dispatches)
    async def exercise():
        _, store, tid = saved_source()
        async with httpx.AsyncClient(event_hooks={'request': [hook]}, timeout=120, follow_redirects=False) as http:
            def make_agent(actor, artifacts, tools, **kwargs):
                profile, basis = node_basis(actor)
                reserve = ((MAX_BYTES+4096)*prices.input_miss+basis.max_output_tokens*prices.output+999999)//1000000
                guard = ModelDispatchGuard(budget, owner='review-probe', budget=bid, prices=prices, reservation_micros=reserve,
                    reservation_basis='240000 UTF8 bytes+4096 framing conservative miss-token scenario plus task-specific output ceiling; estimate not invoice guarantee')
                audit = CaseModelAudit(actor=actor, profile=profile, basis=basis, public_sink=sink('model_events'), private_sink=sink('private_model_audit'),
                    dispatch_guard=guard, source_access_check=lambda: require_task_assets(store, tid))
                model = ReasoningPreservingChatDeepSeek(model=profile.model, api_key=SecretStr(key), base_url='https://api.deepseek.com',
                    http_async_client=http, max_retries=0, max_tokens=basis.max_output_tokens, timeout=basis.timeout_seconds,
                    temperature=0, streaming=False, use_responses_api=False, extra_body={'thinking': {'type': 'disabled'}})
                calls, actions = LIMITS[actor]
                if actor == 'repair':
                    return build_case_output_agent(role='repair', model=model, tools=tools, artifacts=artifacts, paper_id='P01',
                        feedback=kwargs['feedback'], limits={'model_calls': calls, 'tool_calls': actions}, audit=audit)
                return build_case_reviewer(role=actor.removeprefix('revision_'), model=model, tools=tools, artifacts=artifacts,
                    max_model_calls=calls, max_tool_calls=actions, audit=audit, **kwargs)
            return await review_pipeline(make_agent, native.save)
    try:
        native.save('outcome', asyncio.run(exercise()))
    finally:
        native.save('final_budget', budget.snapshot('review-probe', bid))
