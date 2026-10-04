"""Reviewer working view over the unchanged, readable native message journal."""
import json
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from .review_check_store import inspection_progress


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


def working_messages(state, artifacts):
    full=state['messages']
    turns=[i for i,m in enumerate(full) if isinstance(m,AIMessage)]
    if len(turns)<=2:return list(full)
    cutoff=turns[-2]
    pinned=[m for m in full[:cutoff] if isinstance(m,HumanMessage)]
    summary=state.get('request_summary',{}).get('message')
    if summary:pinned.append(HumanMessage.model_validate(summary))
    packet={'notice':'Current review working state, not financial evidence. Full own journal remains readable through read_review_history. Saved checks/findings are reviewer assessments, not author repairs. Re-read exact sources before dependent changes; do not restart completed checks.',
        'saved_findings':state.get('recorded_findings',{}),
        'remaining_inspection':inspection_progress(state.get('recorded_inspections',{}),artifacts),
        'archived_messages':cutoff,'history_read_tool':'read_review_history',
        'saved_checks_read_tool':'read_saved_review_checks'}
    return [*pinned,HumanMessage(content=json.dumps(packet,ensure_ascii=False)),*full[cutoff:]]


class ReviewWorkingContext(AgentMiddleware):
    def __init__(self, artifacts):self.artifacts=artifacts

    async def awrap_model_call(self, request, handler):
        return await handler(request.override(messages=working_messages(request.state,self.artifacts)))
