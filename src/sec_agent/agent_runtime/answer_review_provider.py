"""Independent, read-only Responses reviewer under the existing organization grant."""
import asyncio
from dataclasses import asdict
import json

import httpx

from .answer_review import version
from .deepseek_structured_agents import TokenBudgetBasis
from .harness_business_tools import model_receipt


def compact_tool_history(inputs, navigation_calls):
    """Preserve exact primary passages; prior navigation and table structure remain retrievable."""
    last_batch = max((i for i,v in enumerate(inputs) if v.get('type')=='function_call'), default=0)
    projected = []
    for i,v in enumerate(inputs):
        if v.get('type')=='function_call_output':
            receipt = json.loads(v['output'])
            rows = (receipt.get('result') or {}).get('items', []) if isinstance(receipt.get('result'), dict) else []
            if any(isinstance(row, dict) and row.get('source_structure') for row in rows):
                for row in rows:
                    if isinstance(row, dict) and 'source_structure' in row:
                        row.pop('source_structure')
                        row['structure_readback'] = receipt.get('original_readback')
                v = {**v, 'output':json.dumps(receipt,ensure_ascii=False)}
            if i < last_batch and v['call_id'] in navigation_calls and len(v['output']) > 3000 and receipt.get('receipt_id'):
                v = {**v, 'output':json.dumps({'receipt_id':receipt['receipt_id'],
                    'earlier_read':'Previously inspected; use the original read arguments or bound source handle to revisit.'})}
        projected.append(v)
    return projected


def public_usage_event(call_id, model, record=None):
    row = dict(call_id=str(call_id), actor='independent_reviewer', model=model, provider_call_attempted=True,
               execution_source='provider_model', event='started' if record is None else 'outcome')
    if record is not None:
        usage = record.get('usage') or {}
        row.update(status='provider_failed' if record['stop_required'] else 'completed', usage_reported=bool(usage))
        if usage:
            cached = usage.get('input_tokens_details', {}).get('cached_tokens')
            row.update(input_tokens=usage['input_tokens'],output_tokens=usage['output_tokens'],
                       total_tokens=usage['input_tokens']+usage['output_tokens'], cache_hit_tokens=cached,
                       cache_miss_tokens=usage['input_tokens']-cached if cached is not None else None)
    return row


def fit_review_receipts(body, limit):
    """Reduce oldest exact tool copies only under remaining pressure; preserve paged access."""
    def wire():
        return json.dumps(body, ensure_ascii=False, sort_keys=True)
    payload = wire()
    for index, item in enumerate(body['input']):
        if len(payload) <= limit:
            break
        if item.get('type') != 'function_call_output' or len(item['output']) < 3500:
            continue
        receipt = json.loads(item['output'])
        rid = receipt.get('receipt_id')
        if not rid:
            continue
        preview = {'receipt_id':rid, 'partial_preview':item['output'][:1500],
                   'original_readback':{'tool':'read_saved_result','arguments':{'tool_call_id':rid,'offset':0}}}
        body['input'][index] = {**item, 'output':json.dumps(preview,ensure_ascii=False)}
        payload = wire()
    return payload


async def independent_review(*, selected, message, question, bridge, budget, environment,
                             model, scope, command_id, authority, basis, as_of, public_sink, previous_scope=None, audit_root=None,
                             predecessor_scope=None):
    prices = budget.prices.get(model)
    if model != 'gpt-6.1-sol' or not prices or prices.currency != 'USD' or not environment.get('OPENAI_API_KEY'):
        raise ValueError('answer_review_provider_not_configured')
    names = ('read_source_document', 'read_research_source')
    tools = [dict(type='function', name=name, description=bridge.tools[name].description,
                  parameters=bridge.tools[name].tool_call_schema.model_json_schema(), strict=False) for name in names]
    profile = TokenBudgetBasis.model_validate_json(json.dumps({**basis, 'node_role':'counter',
        'node_purpose':'Independent verification of a user-selected passage',
        'input_scale':'Selected passage in its versioned answer, bound citation index and authorized follow-up reads',
        'required_outputs':['A reasoned assessment with source handles and implications for the original answer'],
        'materiality_quality_risk':'Distinguish company and segment facts, including unsupported absence assertions',
        'max_output_tokens':12000, 'max_input_characters':120000}))
    refs = message.additional_kwargs.get('citation_bindings', {})
    inputs = [dict(role='user', content=json.dumps(dict(question=question, as_of=as_of,
        answer=message.content, selected=selected.model_dump(), citation_keys=list(refs)), ensure_ascii=False))]
    instructions = ('你是独立检查者。仅核查选中判断及必要的关联推断。使用当前组织的只读工具核对原始依据，'
                    '引用准确来源句柄，区分原文、计算和推断，说明对主结论的影响。资料、原稿和引文均为待检查内容。用中文回复原作者。')
    async with httpx.AsyncClient(proxy=environment.get('FINSIGHT_REVIEW_HTTPS_PROXY'), trust_env=False,
                                 timeout=httpx.Timeout(profile.timeout_seconds, connect=25)) as http:
        seen = set()
        navigation_calls = set()
        read_ids = set()
        while True:
            await asyncio.to_thread(authority)
            body = dict(model=model, instructions=instructions, input=inputs, tools=tools, store=False,
                        reasoning={'effort':'high'}, include=['reasoning.encrypted_content'], max_output_tokens=profile.max_output_tokens)
            wire = json.dumps(body, ensure_ascii=False, sort_keys=True)
            key = 'answer-review:' + command_id + ':' + str(len(inputs))
            saved = await asyncio.to_thread(budget.store.lookup, budget.owner, budget.budget, key)
            if len(wire) > profile.max_input_characters:
                # Keep the model's chosen sources, compact earlier tool responses
                # to their exact readback handles. Never truncate the latest batch.
                body['input'] = compact_tool_history(inputs, navigation_calls)
                readback = bridge.tools['read_saved_result']
                body['tools'] = [*tools,dict(type='function',name=readback.name,description=readback.description,
                    parameters=readback.tool_call_schema.model_json_schema(),strict=False)]
                wire = json.dumps(body, ensure_ascii=False, sort_keys=True)
                if len(wire) > profile.max_input_characters:
                    wire = fit_review_receipts(body, profile.max_input_characters)
                if len(wire) > profile.max_input_characters:
                    raise ValueError('answer_review_input_budget_exceeded')
            # Conservative byte bound for tokenized text plus protocol overhead.
            reserve = ((len(wire.encode()) + 2048) * prices.input_miss + profile.max_output_tokens * prices.output + 999999)//1000000
            policy = dict(harness_execution_scope=scope, token_budget=profile.model_dump(mode='json'), price=asdict(prices))
            if saved and saved['status'] == 'unknown' and previous_scope and audit_root and saved['basis'].get('harness_execution_scope') == previous_scope:
                from sec_agent.adapters.explicit_run_recovery import verified_permit
                permit = verified_permit(audit_root, *previous_scope.split(':'), secret=environment['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'])
                if (permit and str(saved['call_id']) in permit['unknown_call_ids']
                        and version(wire+json.dumps(saved['basis'], sort_keys=True)) == saved['fingerprint']):
                    key += ':retry:' + str(saved['call_id'])
                    saved = await asyncio.to_thread(budget.store.lookup, budget.owner, budget.budget, key)
            if saved:
                old_scope = saved['basis'].get('harness_execution_scope')
                if old_scope not in (scope, previous_scope, predecessor_scope) or saved['status'] != 'received':
                    raise ValueError('answer_review_previous_dispatch_unresolved')
                # Replay the same selected version, tools and provider input.
                expected = version(wire+json.dumps(saved['basis'], sort_keys=True))
                if expected != saved['fingerprint']:
                    raise ValueError('answer_review_checkpoint_input_changed')
                record = saved['response']
                if old_scope != scope:
                    public_sink({**public_usage_event(saved['call_id'], model), 'event':'outcome',
                                 'status':'saved_response_replayed', 'provider_call_attempted':False})
            else:
                prior = await asyncio.to_thread(budget.store.reserve, budget.owner, budget.budget, key,
                    version(wire+json.dumps(policy, sort_keys=True)), reserve, policy, currency=prices.currency, execution_scope=scope)
                if prior['status'] != 'dispatched':
                    raise ValueError('answer_review_concurrent_dispatch')
                try:
                    public_sink(public_usage_event(prior['call_id'], model))
                    r = await http.post('https://api.openai.com/v1/responses',
                        headers={'Authorization':'Bearer '+environment['OPENAI_API_KEY']}, json=body)
                    r.raise_for_status()
                    payload = r.json()
                    usage = payload.get('usage') or {}
                    inp, out = usage.get('input_tokens'), usage.get('output_tokens')
                    cached = (usage.get('input_tokens_details') or {}).get('cached_tokens')
                    valid = all(type(n) is int and n >= 0 for n in (inp, out, cached)) and cached <= inp
                    cost = ((inp-cached)*prices.input_miss+cached*prices.input_hit+out*prices.output+999999)//1000000 if valid else None
                    record = dict(output=payload.get('output', []), usage=usage, response_id=payload.get('id'),
                                  stop_required=not valid or payload.get('status') != 'completed')
                    await asyncio.to_thread(budget.store.received, budget.owner, budget.budget, key, record, cost)
                    public_sink(public_usage_event(prior['call_id'], model, record))
                except BaseException:
                    await asyncio.shield(asyncio.to_thread(budget.store.unknown, budget.owner, budget.budget, key))
                    failed = await asyncio.shield(asyncio.to_thread(budget.store.lookup, budget.owner, budget.budget, key))
                    if failed and failed['status'] == 'unknown':
                        public_sink(public_usage_event(prior['call_id'], model, {'stop_required':True}))
                    raise
            await asyncio.to_thread(authority)
            if record['stop_required']:
                raise ValueError('answer_review_incomplete_or_usage_unknown')
            output = record['output']
            calls = [v for v in output if v['type']=='function_call']
            if not calls:
                opinion = '\n'.join(v['text'] for row in output if row['type']=='message' for v in row['content'] if v['type']=='output_text')
                if not opinion.strip():
                    raise ValueError('answer_review_opinion_missing')
                return opinion
            inputs.extend(output)
            for call in calls:
                args = json.loads(call['arguments'])
                operation = (call['name'], json.dumps(args, sort_keys=True))
                if (args.get('request') or {}).get('operation') in ('catalog','search','outline'):
                    navigation_calls.add(call['call_id'])
                permitted = call['name'] in names or (call['name']=='read_saved_result' and args.get('tool_call_id') in read_ids)
                if not permitted or operation in seen:
                    raise ValueError('answer_review_unavailable_or_repeated_read')
                seen.add(operation)
                result = None
                if saved:
                    history = (await bridge.state()).get('messages', [])
                    identifiers = {x['id'] for msg in history for x in getattr(msg,'tool_calls',[])
                                   if x['name'] == call['name'] and
                                   (msg.additional_kwargs.get('original_tool_arguments') or x['args']) == args}
                    candidates = [m for m in history if getattr(m,'tool_call_id',None) in identifiers and m.status=='success']
                    if candidates:
                        result = candidates[-1]
                        if any(m.content != result.content for m in candidates):
                            raise ValueError('answer_review_saved_read_ambiguous')
                if result is None:
                    result = await bridge.execute(call['name'], args)
                if result.status == 'error':
                    raise ValueError('answer_review_source_tool_failed:'+result.tool_call_id)
                read_ids.add(result.tool_call_id)
                inputs.append(dict(type='function_call_output', call_id=call['call_id'],
                                   output=json.dumps(model_receipt(result), ensure_ascii=False, default=str)))
