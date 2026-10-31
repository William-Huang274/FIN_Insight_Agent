"""Offline failed XML-summary request replay, not a generated research summary.

Reconstructs the recorded ordered tool pairs (the old XML serializer omitted
ToolMessage IDs), checks a buffer-string roundtrip, and never writes native state.
Use the canonical-journal replay alongside this narrower request-level check.
"""
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import re
import socket
from unittest.mock import patch
import xml.etree.ElementTree as ET

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import get_buffer_string
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

from sec_agent.agent_runtime.continuous_context_surface import expand_provenance, prefix_fingerprint
from sec_agent.agent_runtime.model_context import RequestSummaryMiddleware, project_tool_history


async def replay(path):
    record=next(json.loads(line) for line in path.open(encoding='utf8')
                if json.loads(line).get('event')=='request')
    prompt=record['messages'][0]['content']
    reference=json.loads(prompt.split('TASK REFERENCE (retained independently):',1)[1]
                         .split('HISTORICAL PREFIX TO SUMMARIZE:',1)[0].strip())
    matches=list(re.finditer(r'<message([^>]*)>(.*?)</message>',prompt,re.S))
    rows=[];pending=[]
    for i,match in enumerate(matches):
        node=ET.fromstring(match.group());kind=node.attrib['type']
        if kind=='ai':
            assert not pending
            calls=[{'id':c.attrib['id'],'name':c.attrib['name'],'args':json.loads(c.text),'type':'tool_call'}
                   for c in node.findall('tool_call')]
            pending.extend(calls)
            rows.append(AIMessage(id=f'xml-{i}',content=node.findtext('content') or '',tool_calls=calls))
        elif kind=='tool':
            call=pending.pop(0)
            rows.append(ToolMessage(id=f'xml-{i}',content=node.text,tool_call_id=call['id']))
        else:
            assert kind=='human' and not pending
            rows.append(HumanMessage(id=f'xml-{i}',content=node.text))
    assert not pending
    # Compare XML trees: indentation/attribute whitespace isn't source content.
    rendered=list(re.finditer(r'<message([^>]*)>(.*?)</message>',get_buffer_string(rows,format='xml'),re.S))
    assert len(rendered)==len(matches)
    for a,b in zip(matches,rendered):
        old,new=ET.fromstring(a.group()),ET.fromstring(b.group())
        assert old.attrib==new.attrib
        if old.attrib['type']=='ai':
            assert old.findtext('content')==new.findtext('content')
            assert [(c.attrib,c.text) for c in old.findall('tool_call')]==[(c.attrib,c.text) for c in new.findall('tool_call')]
        else:assert old.text==new.text
    original=deepcopy(rows)
    view=project_tool_history(rows,policy='continuous_surface',trigger_tokens=None)
    expanded=expand_provenance(view)
    previous_expanded=expand_provenance(original)
    for before,after in zip(previous_expanded,expanded):
        if isinstance(before,ToolMessage):
            try:assert json.loads(before.content)==json.loads(after.content)
            except json.JSONDecodeError:assert before.content==after.content
    task=HumanMessage(id=reference[0]['message_id'],content=reference[0]['content'])
    latest=reference[-1]
    tail=HumanMessage(id='replay-latest-reference',content=latest['content'])
    # The recorded XML is already a request view, not the canonical journal.
    # Restore its shared metadata before simulating a new native checkpoint;
    # otherwise a later segment would retain references to the removed prefix.
    history=[task,*previous_expanded,tail];canonical=prefix_fingerprint(history);calls=[]
    def fake(value):
        calls.append({'messages':len(value),'characters':len(json.dumps([m.model_dump(mode='json',
            exclude={'artifact','response_metadata','usage_metadata'}) for m in value],ensure_ascii=False))})
        return AIMessage(content='OFFLINE STRUCTURAL STUB ONLY. Not a research summary or financial conclusion.')
    middleware=RequestSummaryMiddleware(model=FakeListChatModel(responses=['unused']),audited_model=RunnableLambda(fake),
        context_policy='continuous_surface',trigger_tokens=32000,keep_tokens=12000,navigation_trigger_tokens=12000)
    update=await middleware.abefore_model({'messages':history},None)
    assert prefix_fingerprint(history)==canonical
    return {'paid_calls':0,'network_disabled':True,'xml_pairs_roundtripped':len(rows),
        'lossless_tools_expanded':sum(isinstance(m,ToolMessage) for m in rows),
        'original_prompt_characters':len(prompt),'before_tool_characters':sum(len(m.content) for m in original if isinstance(m,ToolMessage)),
        'after_tool_characters':sum(len(m.content) for m in view if isinstance(m,ToolMessage)),
        'stub_segment_requests':calls,'accepted_stub_segments':(update or {}).get('request_summary',{}).get('count',0),
        'failure':(update or {}).get('request_summary_failure'),'canonical_unchanged':True,
        'scope':'Recorded summary prefix + original/latest reference; no missing recent suffix invented. Stub proves mechanics only, not summary quality or total provider tokens.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    async def offline():
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Offline replay prohibits network')):
            return await replay(args.audit)
    result=asyncio.run(offline());args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=True))
