"""Research-lead views. Canonical results and workpapers remain independently readable."""
import json

from langchain_core.messages import ToolMessage

from pydantic import BaseModel, ConfigDict, Field

from sec_agent.research_foundation.source_bound_calculator import sources_from_receipts


class Counterexample(BaseModel):
    model_config = ConfigDict(extra='forbid')
    receipt_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    assessment_excerpt: str = Field(min_length=1, max_length=1000,
        description='The relevant words of your counterevidence field explaining what this observation changes.')
    quote: str = Field(min_length=1, max_length=1200,
        description='Copy the decision-changing observation verbatim from this exact original passage.')


def quote_location(selection, original, reason):
    from .research_workpapers import WorkpaperConflict
    if not selection.assessment_excerpt.strip() or selection.assessment_excerpt not in reason:
        raise WorkpaperConflict('counterexample_requires_exact_assessment_excerpt')
    text = sources_from_receipts([original]).get(selection.source_id, {}).get('passage') or ''
    if (original.get('tool_call_id') != selection.receipt_id or not selection.quote.strip()
            or text.count(selection.quote) != 1):
        raise WorkpaperConflict('counterexample_requires_unique_exact_quote')
    return {**selection.model_dump(), 'offset_in_passage':text.index(selection.quote),
            'readback':{'tool':'read_workpaper_evidence','arguments':{'receipt_id':selection.receipt_id}}}


def paper_decision(paper):
    view = {k:paper[k] for k in ('topic_id','revision','digest','as_of','finding','conditions',
            'counterevidence','competing_explanation','decisive_passages','next_decision','disposition','change',
            'current_revision','requires_reassessment') if k in paper}
    view['remaining'] = paper.get('decision_uncertainty') or paper['remaining']
    view['readback'] = {'tool':'read_research_workpaper','arguments':{
        'topic_id':paper['topic_id'],'revision':paper['revision'],'field':'metadata'}}
    return view


def lead_decision(view):
    result = {k:view[k] for k in ('revision','digest','question','as_of','lead_judgment_ids',
                                   'requires_reassessment','affected_sections')}
    result['view_kind'] = 'research_decision'
    result['judgments'] = {}
    if view.get('issues'):
        result['open_issues'] = [issue for issue in view['issues'] if issue['status']=='open']
    for key, node in view['judgments'].items():
        if node['status'] == 'withdrawn':
            result['judgments'][key] = {k:node[k] for k in ('status','statement','rationale')}
            continue
        judgment = {k:node[k] for k in ('status','statement','rationale','conditions','counterevidence',
                                         'depends_on','representative_receipts') if k in node}
        judgment['remaining'] = node.get('decision_uncertainty') or node['remaining']
        judgment['workpapers'] = [{k:r[k] for k in ('topic_id','revision','digest','use')} for r in node['workpapers']]
        result['judgments'][key] = judgment
    result['readback'] = {'tool':'read_authoring_context','arguments':{
        **({'revision':view['revision']} if view['revision'] else {}),
        'include_history':True, 'include_unplaced':True}}
    return result


def inspected_window(tool, receipt_id, body):
    """An exact read operation can be repeated even when the parent source or paper changes."""
    if not isinstance(body,dict):
        return None
    if tool == 'read_authoring_context' and body.get('result_digest') and (
            body.get('view_kind') == 'research_decision' or
            ('selected_sections' not in body and 'lead_judgment_ids' in body and 'judgments' in body)
            or body.get('include_history') or body.get('historical_read')):
        return {'receipt_id':receipt_id,'status':'success','result':{
            'context_state':'inspected_research_window','revision':body.get('revision'),
            'result_digest':body['result_digest'],
            'readback':{'tool':'read_saved_result','arguments':{'tool_call_id':receipt_id}}}}
    if (tool == 'read_public_source' and body.get('operation') == 'search' and body.get('items')
            and body.get('source_snapshot_sha256')):
        return {'receipt_id':receipt_id,'status':'success','result':{
            'context_state':'inspected_research_window','operation':'search',
            'result_digest':body.get('result_digest') or body['source_snapshot_sha256'],
            'returned_candidates':len(body['items']),
            'unresolved_originals':[{k:i[k] for k in ('url','reason') if k in i}
                for i in (body.get('unresolved_originals') or []) if isinstance(i,dict)],
            'readback':{'tool':'read_saved_result','arguments':{'tool_call_id':receipt_id}}}}
    if (tool == 'read_public_source' and body.get('operation') == 'read' and body.get('source_snapshot_sha256')
            and body.get('items') and all(isinstance(i,dict) and i.get('result_state')=='source_bound_passage'
                                         and i.get('passage_id') for i in body['items'])):
        index = [{k:i[k] for k in ('passage_id','title','period','unit','publication_date','source_url')
                  if k in i} for i in body['items']]
        return {'receipt_id':receipt_id,'status':'success','result':{
            'context_state':'inspected_research_window','result_digest':body.get('result_digest') or body['source_snapshot_sha256'],
            'passages':index,'readback':{'tool':'read_saved_result','arguments':{'tool_call_id':receipt_id}}}}
    if tool == 'read_workpaper_evidence' and isinstance(body.get('text'),str):
        args = {'receipt_id':body['receipt_id'],'offset':body['offset'],
                'max_characters':max(1,len(body['text']))}
    elif tool == 'read_research_workpaper' and isinstance(body.get('body'),str):
        args = {'topic_id':body['topic_id'],'revision':body['revision'],'field':'body',
                'offset':body['offset'],'max_characters':max(1,len(body['body']))}
    elif tool == 'read_research_workpaper' and body.get('topic_id') and body.get('digest'):
        args = {'topic_id':body['topic_id'],'revision':body['revision'],
                'field':'outline' if 'argument_sections' in body else 'metadata'}
    elif tool == 'read_saved_result' and 'original_tool_call_id' in body and isinstance(body.get('content'),str):
        args = {'tool_call_id':body['original_tool_call_id'],'offset':body['offset'],
                'max_characters':max(1,len(body['content']))}
        if 'json_pointer' in body:
            args['json_pointer'] = body['json_pointer']
    else:
        return None
    digest = body.get('result_digest') or receipt_id
    result = {k:body[k] for k in ('topic_id','revision','digest','source_evidence','original_status',
                                   'record_kind','next_offset','total_characters') if k in body}
    result.update(result_digest=digest, context_state='inspected_research_window',
                  readback={'tool':tool,'arguments':args})
    if tool == 'read_research_workpaper':
        for field in ('requires_reassessment','reviewed_counterexamples','decisive_passages'):
            if body.get(field):
                result[field] = body[field]
    return {'receipt_id':receipt_id,'status':'success','result':result}


def resolved_feedback(messages):
    """Retire matched registration errors or a failed acquisition retried with identical arguments."""
    from .source_acquisition_view import SOURCE_TOOLS
    names = {'assess_research_result','publish_research_workpaper'} | SOURCE_TOOLS
    calls = {c['id']:c for m in messages for c in getattr(m,'tool_calls',[]) if c['name'] in names}
    completed = {}
    replacements = {}
    for m in reversed(messages):
        if not isinstance(m,ToolMessage) or m.name not in names or m.tool_call_id not in calls:
            continue
        args = calls[m.tool_call_id]['args']
        if m.name == 'assess_research_result':
            identity = (m.name,args.get('task_id'),args.get('result_digest'))
            flag = 'decision_recorded'
        elif m.name == 'publish_research_workpaper':
            # Each owner's checkpointer has one publication topic. Never infer identity for imported calls.
            identity = (m.name,args.get('base_revision'))
            flag = 'saved'
        else:
            if not args:
                continue
            identity = (m.name,json.dumps(args,sort_keys=True,ensure_ascii=False))
            flag = None
        if None in identity:
            continue
        try:
            body = json.loads(m.content)
        except (ValueError,TypeError):
            continue
        if not isinstance(body,dict):
            continue
        acquired = any(isinstance(i,dict) and i.get('result_state')=='source_bound_passage'
                       and i.get('passage_id') for i in (body.get('items') or []))
        if m.status == 'success' and (body.get(flag) is True if flag else acquired):
            completed[identity] = m.tool_call_id
        elif identity in completed and (m.status=='error' or (body.get(flag) is False and body.get('error'))):
            digest = body.get('result_digest') or body.get('source_snapshot_sha256') or m.tool_call_id
            replacements[m.tool_call_id] = {'receipt_id':m.tool_call_id,'status':m.status,'result':{
                'context_state':'resolved_research_feedback','result_digest':digest,
                'successful_receipt':completed[identity],'readback':{'tool':'read_saved_result',
                'arguments':{'tool_call_id':m.tool_call_id}}}}
    return replacements
