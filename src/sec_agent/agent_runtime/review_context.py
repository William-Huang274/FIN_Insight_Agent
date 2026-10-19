"""Reviewer working view over the unchanged, readable native message journal."""
import json
from copy import deepcopy
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from .research_graph_contracts import canonical_sha256


def handoff_page(artifacts, confirmation, *, section, paper_id=None, offset=0):
    """Read the unchanged handoff, not a regenerated model summary."""
    if offset < 0 or section not in {'catalog', 'revision_confirmation'}:
        raise ValueError('invalid_review_handoff_section_or_offset')
    value = artifacts.catalog() if section == 'catalog' else deepcopy(confirmation)
    if paper_id is not None:
        if paper_id not in artifacts._papers:
            raise ValueError('unknown_paper_id_use_catalog')
        if section == 'catalog':
            value = next(p for p in value['papers'] if p['paper_id'] == paper_id)
        elif value:
            value = {k: (v.get(paper_id) if k in {'paper_version_digests', 'findings_to_confirm',
                'changes', 'author_responses'} else v) for k, v in value.items()}
    text = json.dumps(value, ensure_ascii=False)
    return {'section': section, 'paper_id': paper_id, 'offset': offset,
        'text': text[offset:offset+6000], 'total_characters': len(text),
        'next_offset': offset+6000 if offset+6000 < len(text) else None}


def confirmation_navigation(confirmation):
    """Keep scope/versions/changed fields; character diff coordinates are on demand."""
    result = deepcopy(confirmation)
    for pid, change in (result or {}).get('changes', {}).items():
        removed = False
        for location in change.get('locations', []):
            if 'spans' in location:
                location['span_count'] = len(location.pop('spans'))
                removed = True
        if removed:
            change['exact_changes_read'] = {'tool': 'read_review_handoff',
                'arguments': {'section': 'revision_confirmation', 'paper_id': pid, 'offset': 0}}
    return result


def paper_quote_view(message):
    """Lossless per-result factoring of repeated (source ID, literal quote) pairs.

    All current prose, claims and quote-to-claim bindings remain. This is a model
    view only: native artifacts and source-validation receipts are untouched.
    """
    if not isinstance(message, ToolMessage) or message.status != 'success' or message.name != 'read_research_artifact':
        return message
    try:
        value = json.loads(message.content)
    except (ValueError, TypeError):
        return message
    if not isinstance(value, dict) or 'citation_quote_table' in value or value.get('section') not in {'workpaper', 'claims'}:
        return message
    content = value.get('content')
    claims = content.get('claims') if isinstance(content, dict) else content
    if not isinstance(claims, list):
        return message
    quotes, identities = {}, {}
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get('citation_quotes'), dict):
            continue
        refs = {}
        for source_id, literals in claim['citation_quotes'].items():
            scalar = isinstance(literals, str)
            if scalar:
                literals = [literals]
            if not isinstance(literals, list) or not all(isinstance(q, str) for q in literals):
                return message
            refs[source_id] = []
            for literal in literals:
                key = (source_id, literal)
                if key not in identities:
                    ref = f'Q{len(quotes)+1}'
                    identities[key] = ref
                    quotes[ref] = {'source_id': source_id, 'quote': literal}
                refs[source_id].append(identities[key])
            if scalar:
                refs[source_id] = refs[source_id][0]
        claim.pop('citation_quotes')
        claim['citation_quote_refs'] = refs
    value['citation_quote_table'] = quotes
    value['quote_view_notice'] = ('citation_quote_refs refer to this result\'s citation_quote_table only. '
        'Every original quote and binding is retained; these are author-selected quotes, not independent verification. '
        'The unchanged full receipt remains in read_review_history.')
    encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return message.model_copy(update={'content': encoded}) if len(encoded) < len(message.content) else message


def history_page(messages, *, index=None, offset=0, limit=20):
    if offset < 0 or not 1 <= limit <= 20:
        raise ValueError('history_offset_or_limit_invalid')
    if index is None:
        rows=[{'index':i,'kind':m.type,'tool':getattr(m,'name',None),
            'calls':[{'name':t['name'],'arguments_keys':list(t.get('args',{}))} for t in getattr(m,'tool_calls',[])],
            'preview':str(m.content)[:180]} for i,m in enumerate(messages[offset:offset+limit],offset)]
        return {'messages':rows,'next_offset':offset+limit if offset+limit<len(messages) else None,'total':len(messages)}
    if not 0 <= index < len(messages):raise ValueError('history_index_invalid')
    message=messages[index]
    # Never serialize additional_kwargs/reasoning_content or sibling state.
    text=json.dumps({'kind':message.type,'content':message.content,
        'tool_calls':getattr(message,'tool_calls',[]),'tool':getattr(message,'name',None),
        'tool_call_id':getattr(message,'tool_call_id',None)},ensure_ascii=False)
    return {'index':index,'text':text[offset:offset+6000],
        'next_offset':offset+6000 if offset+6000<len(text) else None,'total_characters':len(text)}


def source_window_view(message):
    """Project legacy window labels; preserve original receipts in the journal."""
    if not isinstance(message, ToolMessage) or message.status!='success' or message.name!='read_review_source_span':
        return message
    try:
        value=json.loads(message.content)
    except (ValueError,TypeError):
        return message
    if not isinstance(value,dict):return message
    changed=False
    for row in [value,*value.get('candidates',[])]:
        if isinstance(row,dict) and 'quote_span' in row and 'text' in row and 'window_span' not in row:
            row['window_span']=row.pop('quote_span');changed=True
    if not changed:return message
    value['notice']='Legacy reading-window labels projected as window_span; original receipt remains in read_review_history. Submit source_id + chosen exact quote; runtime locates it. Do not copy a context window as selected quote_span.'
    return message.model_copy(update={'content':json.dumps(value,ensure_ascii=False)})


def working_messages(state, artifacts, confirmation=None):
    full=state['messages']
    # Legacy instructions/checklist errors remain in the journal, not active
    # instructions. A contract-transition boundary does not erase source reads.
    boundaries=[i for i,m in enumerate(full) if isinstance(m,HumanMessage) and 'review_handoff_contract_v2' in str(m.content)]
    # A migration boundary retires the old contract once. Resuming again must
    # not discard the work performed under the current contract.
    cutoff=boundaries[0]+1 if boundaries else 0
    question=None
    user_messages=[]
    for m in full:
        if isinstance(m,HumanMessage) and isinstance(m.content,str):
            if 'review_handoff_contract_v2' in m.content:
                continue
            if m.content.startswith('Authors revised the current candidate. Historical paper text'):
                # Legacy runtime-generated transition. The current version and
                # confirmation context below replace its missing-slot mandate.
                continue
            if m.content.startswith('Continue this same review using saved reads, findings and version-bound checks.'):
                continue  # v1 runtime seed; retained in the readable journal
            try:value=json.loads(m.content)
            except (ValueError,TypeError):
                user_messages.append(m)
                continue
            if isinstance(value,dict) and value.get('question'):
                question=value['question']
            elif isinstance(value,dict) and str(value.get('notice','')).startswith('Current review working state, not financial evidence.'):
                continue  # the new packet replaces the previous projection
            else:
                user_messages.append(m)
    reads=set()
    for m in full:
        value=m.artifact if isinstance(m,ToolMessage) and m.status=='success' else None
        if isinstance(value,dict) and m.name=='read_research_artifact' and value.get('section')=='workpaper':
            pid=value.get('paper_id')
            if pid in artifacts._papers and value.get('content')==artifacts.read_paper(pid):reads.add(pid)
    legacy={pid:sum(1 for row in state.get('recorded_inspections',{}).values()
                   if row['paper_id']==pid and row['paper_digest']==canonical_sha256(artifacts.read_paper(pid)))
            for pid in artifacts._papers}
    packet={'notice':'Current review working state, not financial evidence. Full own journal remains readable through read_review_history. Saved checks/findings are reviewer assessments, not author repairs. Re-read exact sources before dependent changes; do not restart completed checks.',
        'contract':'review_handoff_contract_v2', 'question':question, 'catalog':artifacts.catalog(),
        'current_full_paper_reads':sorted(reads), 'revision_confirmation':confirmation_navigation(confirmation),
        'saved_findings':state.get('recorded_findings',{}),
        'legacy_record_counts_for_reference_only':legacy,
        'archived_messages':cutoff,'history_read_tool':'read_review_history',
        'saved_checks_read_tool':'read_saved_review_checks'}
    def runtime_stop(message):
        # Native limit middleware emits these as AI messages, but they are host
        # control receipts, not model completions (and have no thinking state).
        return (isinstance(message,AIMessage) and not message.tool_calls
            and not message.response_metadata and not message.additional_kwargs
            and isinstance(message.content,str) and message.content.startswith((
                'Model call limits exceeded:', 'Tool call limit reached:')))
    recent=[m for m in full[cutoff:] if not runtime_stop(m) and (
        not isinstance(m,HumanMessage) or 'review_handoff_contract_v2' in str(m.content))]
    from .model_context import deduplicate_read_results
    return deduplicate_read_results([*user_messages,
        HumanMessage(id='review-working-state-v2',content=json.dumps(packet,ensure_ascii=False)),
        *(source_window_view(paper_quote_view(m)) for m in recent)])


class ReviewWorkingContext(AgentMiddleware):
    def __init__(self, artifacts, confirmation=None):self.artifacts,self.confirmation=artifacts,confirmation

    async def awrap_model_call(self, request, handler):
        return await handler(request.override(messages=working_messages(request.state,self.artifacts,self.confirmation)))
