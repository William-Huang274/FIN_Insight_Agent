"""Fixed-source AMZN transfer qualification. Never enabled by default."""
import asyncio
import hashlib
import json
import os
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from test_native_server_runtime import native
from test_project_materials_live import ROOT, configuration, prepare, compose, run_real_project_materials
from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek, TokenBudgetBasis
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


QUESTION = ('仅依据所选亚马逊2025年第二季度业绩公告，比较截至2025年和2024年6月30日三个月的公司整体与AWS分部：'
    '各自的净销售额、营业利润、营业利润率及其同比百分点变化，明确金额单位。区分季度、半年和滚动十二个月，'
    '使用现有资料读取和来源绑定计算工具，提供精确原文引用。说明两层经营表现能支持哪些判断、有哪些竞争解释和仍需核实的边界，'
    '不要将汇总结果直接归因于某个AI产品。形成中文短底稿；不要读取其他历史案例、财务库或外网，不给投资建议。')
SOURCE_OPTIONS = {'source': ROOT / '.local/fin014/20260914_e3_amzn_source_a2', 'filename': 'amzn-q2-2025.html',
                  'research_question': QUESTION, 'project_name': 'AMZN Q2 2025 method transfer'}
MAX_CALLS, MAX_BYTES = 12, 240000


def transfer_configuration():
    config, profile, old = configuration()
    basis = TokenBudgetBasis.model_validate({**old.model_dump(),
        'node_purpose': 'One new-company fixed-source transfer: compare consolidated and AWS quarter margins, competing explanations and source-inspection boundaries',
        'input_scale': 'SEC official release643232 bytes,38975 parsed characters,nine existing blocks;240000 UTF8 bytes includes method/tool schemas, exact source and calculation history',
        'required_outputs': ('Read selected source and dynamically select relevant methods as needed',
            'Exact 2025/2024 quarter company and AWS net sales/operating income with units; exclude six-month/TTM confusion',
            'Six source-bound margin/change calculations and exact supporting quotes',
            'Chinese short workpaper comparing company/segment, alternatives and defensible gaps; no product causality or investment advice'),
        'schema_burden': 'Company plus segment doubles margin calculations from3 to6; allow6000 output tokens for additional source IDs, period/header quotes and claim records',
        'comparable_run_evidence': '017 Pro arms6-8calls with3-5calculations,max155115-byte payload; source grows23649 to38975 characters.12calls allow2method,4source,3calculation/feedback,1submission and2repairs;24tool actions.240000 bytes allows larger source and complete additional calculation/citation history without dropping required work. This is a new-company development transfer, not randomized causality or blind holdout.',
        'materiality_quality_risk': 'Wrong quarter/unit/company-vs-segment, missing available table or unsupported causal conclusion prevents full acceptance; task upload remains non-S2 authority',
        'max_input_characters': MAX_BYTES, 'max_output_tokens': 6000})
    return config.model_copy(update={'token_budget_basis': {**config.token_budget_basis, 'specialist': basis}}), profile, basis


@pytest.mark.local_data_integration
def test_transfer_source_and_sdk_preflight(tmp_path, monkeypatch):
    for flag in ('LANGSMITH_TRACING', 'LANGCHAIN_TRACING_V2'):
        monkeypatch.setenv(flag, 'false')
    store, tid, question, receipt = prepare(tmp_path, **SOURCE_OPTIONS)
    doc = store.list(tid)[0]['document_id']
    async def read():
        return await store.read(thread_id=tid, request=SourceDocumentRequest(source_space='uploads', operation='read', document_id=doc, limit=20, max_characters=80000))
    source = asyncio.run(read())
    text = '\n'.join(i['passage'] for i in source.items)
    assert len(source.items) == 9 and source.next_offset is None
    assert all(i['raw_body_sha256'] == receipt['sha256'] and i['project_origin'] for i in source.items)
    assert all(v in text for v in ('30,873', '26,281', '10,160', '9,334', '167,702', '147,977', '19,171', '14,672'))
    config, profile, basis = transfer_configuration()
    payloads = []
    def serve(request):
        payload = json.loads(request.content); payloads.append(payload)
        assert len(request.content) < MAX_BYTES
        assert payload['max_tokens'] == 6000
        assert QUESTION in json.dumps(payload, ensure_ascii=False)
        assert '30,873' not in json.dumps(payload)  # No answer values pre-injected.
        return httpx.Response(200, json={'id': 'transfer-preflight', 'object': 'chat.completion', 'created': 1, 'model': profile.model,
            'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'content': '',
                'tool_calls': [{'id': 'stop', 'type': 'function', 'function': {'name': 'RequestHumanReviewAction', 'arguments': json.dumps({
                    'action': 'request_human_review', 'blocker_code': 'transfer_preflight_complete', 'reason_summary': 'Local transport preflight only.'})}}]}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        model = ReasoningPreservingChatDeepSeek(model=profile.model, api_key=SecretStr('local-fixture'), http_client=client,
            max_retries=0, max_tokens=basis.max_output_tokens, use_responses_api=False, extra_body={'thinking': {'type': 'disabled'}})
        adapter = DeepSeekStructuredAgentAdapter(config=config, chat_models={r:model for r in ('planner','specialist','counter','lead')})
        with compose(store, tid, question, adapter.specialist_model_turn, 'amzn-preflight-'+tid) as runtime:
            result = runtime.graph.invoke(runtime.graph_input.model_dump(mode='json'), {'configurable': {'thread_id':tid}, 'recursion_limit':60})
    assert len(payloads) == 1 and 'transfer_preflight_complete' in json.dumps(result)


@pytest.mark.paid_model
@pytest.mark.local_data_integration
@pytest.mark.skipif(os.getenv('FIN_NATIVE_QUALIFICATION') != '1' or os.getenv('FIN_PAID_METHOD_TRANSFER') != '1', reason='explicit one-run AMZN transfer only')
def test_real_amzn_method_transfer(native, monkeypatch):
    comparison = {'baseline': '017 known MSFT negative; no same-question control arm',
        'changed_variable': 'New AMZN question/source after018 navigation repair; existing dynamic methods, Pro non-thinking and source tools',
        'review': 'Host reviews all narrative/claims/counterevidence/gaps against original selected source: correct quarterly company/AWS values and six calculations, complete exact citations, no false non-disclosure, no unsupported product attribution. Tool calls and pytest success alone are not quality acceptance.',
        'qualification_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits': 'One pre-specified new-company development transfer, host has read original source. Not blind, not a causal comparison, no same-case paid tuning or unknown resend.'}
    run_real_project_materials(native, monkeypatch, config_bundle=transfer_configuration(), max_calls=MAX_CALLS,
        max_bytes=MAX_BYTES, max_tool_actions=24, comparison=comparison, tariff_multiplier=1,
        source_options=SOURCE_OPTIONS, attempt_prefix='amzn-transfer')
