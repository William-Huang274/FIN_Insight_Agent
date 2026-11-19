"""Derived, scoped acquisition history. No new store and no semantic gap verdict."""
import json
from collections import Counter
from langchain_core.messages import AIMessage, ToolMessage


SOURCE_TOOLS={'read_public_source','read_source_document','read_research_source','read_company_library','read_legislation'}


def acquisition_snapshot(messages):
    """Current journal metadata; authoritative receipts stay in the business store."""
    rows = acquisition_history(messages)
    counts = Counter(e['stage'] for r in rows for e in r['events'])
    return {'snapshot': 'run_start_observations_not_topic_coverage',
            'source_urls': sum(bool(r.get('source_url')) for r in rows), 'events_by_stage': dict(counts),
            'sources_with_obstacle_after_last_read': sum(r['unresolved_after_latest_read'] for r in rows if r.get('source_url')),
            'queries_without_usable_result': sum(r['unresolved_after_latest_read'] for r in rows if r.get('query_key')),
            'research_coverage': 'not_established_by_runtime',
            'boundary_notice': 'Access failures and empty searches are unfinished observations, not proof of nondisclosure. Inspect exact failures and alternative routes; a successful candidate or passage does not certify complete investigation.',
            'readback': {'tool': 'browse_context', 'arguments': {'region': 'acquisition'}},
            'query_readback': {'tool': 'browse_context', 'arguments': {'region': 'sources'}}}


def acquisition_history(messages):
    calls={c['id']:c for m in messages if isinstance(m,AIMessage) for c in m.tool_calls}
    rows={}
    documents={}
    for msg in messages:
        if not isinstance(msg,ToolMessage) or msg.name not in SOURCE_TOOLS: continue
        try: value=json.loads(msg.content)
        except (ValueError,TypeError): value={}
        if not isinstance(value,dict): continue
        # Native wire exports wrap the same receipt; legacy checkpoints store the body.
        if value.get('receipt_id') and isinstance(value.get('result'), dict):
            value=value['result']
        args=calls.get(msg.tool_call_id,{}).get('args',{})
        execution=value.get('execution_receipt') or {}
        operation=value.get('operation') or args.get('operation')
        if operation == 'search':
            from .research_graph_contracts import canonical_sha256
            # Only exact requests share a history, including cutoff/backend/language.
            # Missing arguments must not merge unrelated queries.
            key=canonical_sha256({'tool':msg.name,'arguments':args}) if args else msg.tool_call_id
            row=rows.setdefault('query:'+key, {'source_url':None, 'query_key':key,
                'query':args.get('query'), 'events':[]})
            usable=bool(value.get('items')) and msg.status=='success'
            status=execution.get('status')
            stage=('search_results_observed' if usable else
                   'search_execution_failed' if msg.status=='error' or status=='tool_failure'
                   else 'search_no_usable_result')
            row['events'].append({'receipt_id':msg.tool_call_id,'tool':msg.name,'stage':stage,
                'execution_status':status, 'returned_items':len(value.get('items') or []),
                'readback':{'tool':'read_saved_result','arguments':{'tool_call_id':msg.tool_call_id}}})
        def add(url, stage, detail):
            if not isinstance(url,str) or not url.startswith(('https://','http://')): return
            row=rows.setdefault(url,{'source_url':url,'events':[]})
            event={'receipt_id':msg.tool_call_id,'tool':msg.name,'stage':stage,**detail}
            event['readback']={'tool':'read_saved_result','arguments':{'tool_call_id':msg.tool_call_id}}
            # Only actual supplied navigation is retained; no inferred substitute URLs.
            row['events'].append(event)
        for item in value.get('unresolved_originals',[]) or []:
            if isinstance(item,dict):
                add(item.get('url'),'access_or_verification_unresolved',
                    {k:item[k] for k in ('reason','publisher_search','read_entry') if k in item})
        for item in value.get('items',[]) or []:
            if not isinstance(item,dict): continue
            stage={'retrieval_candidate':'candidate_not_read','source_bound_passage':'passage_read'}.get(item.get('result_state'))
            if not stage: continue
            if item.get('document_id') and item.get('source_url'):
                documents.setdefault(item['document_id'],set()).add(item['source_url'])
            add(item.get('source_url'),'tool_failed' if msg.status=='error' else stage,
                {k:item[k] for k in ('document_id','passage_id','publication_date','source_read_method',
                    'content_sha256','publication_date_status','source_locator','truncated','source_document_completeness_verified','writer_citable') if k in item})
        if msg.status=='error':
            url=args.get('source_url') or args.get('query')
            known=documents.get(args.get('document_id'),set())
            if not (isinstance(url,str) and url.startswith(('https://','http://'))) and len(known)==1:
                url=next(iter(known))
            add(url,'tool_failed',{'error':str(msg.content)[:600],
                'original_arguments':args,'retry_authorized':False})
    result=[]
    for row in rows.values():
        events=row['events']
        if row.get('query_key'):
            row.update(last_observation=events[-1]['stage'], has_read_passage=False,
                read_after_obstacle=False,
                unresolved_after_latest_read=events[-1]['stage']!='search_results_observed',
                research_gap_status='not_inferred_from_tool_history')
            result.append(row)
            continue
        reads=[i for i,e in enumerate(events) if e['stage']=='passage_read']
        blocked=[i for i,e in enumerate(events) if e['stage'] in {'access_or_verification_unresolved','tool_failed'}]
        row.update(last_observation=events[-1]['stage'],has_read_passage=bool(reads),
            read_after_obstacle=bool(reads and blocked and any(b<reads[-1] for b in blocked)),
            unresolved_after_latest_read=bool(blocked and (not reads or blocked[-1]>reads[-1])),
            research_gap_status='not_inferred_from_tool_history')
        result.append(row)
    return result
