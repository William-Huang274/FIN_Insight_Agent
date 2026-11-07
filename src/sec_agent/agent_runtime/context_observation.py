"""Wire-history measurements for supervision; never a second loop or token estimate."""
import json
from collections import Counter
from hashlib import sha256


def _encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def observe_context(body):
    calls, groups, sizes, blocksizes = {}, {}, Counter(), Counter()
    messages=body.get('messages',[])
    for position,message in enumerate(messages):
        if not isinstance(message,dict): continue
        sizes[str(message.get('role','unknown'))]+=len(_encoded(message))
        toolcalls=list(message.get('tool_calls',[]) or [])
        results=[]
        if isinstance(message.get('content'),list):
            for block in message['content']:
                if not isinstance(block,dict):continue
                blocksizes[str(block.get('type','unknown'))]+=len(_encoded(block))
                if block.get('type')=='tool_use':
                    toolcalls.append({'id':block.get('id'),'function':{'name':block.get('name'),'arguments':block.get('input')}})
                elif block.get('type')=='tool_result':
                    results.append((block.get('tool_use_id'),[block.get('content'),block.get('is_error',False)]))
        for call in toolcalls:
            function=call.get('function',{})
            args=function.get('arguments','')
            if isinstance(args,str):
                try: args=json.loads(args)
                except ValueError: pass
            name=function.get('name','unknown')
            digest=sha256(_encoded([name,args]).encode()).hexdigest()
            group=groups.setdefault(digest,{'tool':name,'argument_digest':digest,'calls':0,'results':Counter(),
                'first_message_index':position,'last_message_index':position})
            group['calls']+=1
            group['last_message_index']=position
            calls[call.get('id')]=group
        if message.get('role')=='tool':results.append((message.get('tool_call_id'),message.get('content')))
        for key,content in results:
            if key not in calls:continue
            digest=sha256(_encoded(content).encode()).hexdigest()
            calls[key]['results'][digest]+=1
    repeated=[{'tool':g['tool'],'argument_digest':g['argument_digest'],'calls':g['calls'],
        'result_variants':len(g['results']), 'identical_result_repeats':sum(n-1 for n in g['results'].values()),
        'unreturned_calls':g['calls']-sum(g['results'].values()),
        'first_message_index':g['first_message_index'],'last_message_index':g['last_message_index']}
        for g in groups.values() if g['calls']>1]
    repeated.sort(key=lambda r:-r['identical_result_repeats'])
    return {'message_count':len(messages),'message_characters_by_role':dict(sizes),
        'content_block_characters_by_type':dict(blocksizes), 'system_characters':len(_encoded(body.get('system',''))),
        'observed_tool_calls':sum(g['calls'] for g in groups.values()),
        'tool_schema_characters':len(_encoded(body.get('tools',[]))),
        'repeated_argument_groups':repeated[:30], 'total_repeated_argument_groups':len(repeated),
        'notice':'Characters are not tokens. Repeated calls may be justified; changed results and normal pagination are distinct. This is evidence for supervision, not a stagnation verdict or automatic stop. Native harness owns compaction.'}
