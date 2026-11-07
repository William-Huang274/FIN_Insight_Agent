"""Offline replay over user-supplied immutable artifacts; no inference or network."""
import argparse
import json
from hashlib import sha256
from pathlib import Path
from langchain_core.messages import ToolMessage
from sec_agent.agent_runtime.revision_context import revision_wording
from sec_agent.agent_runtime.source_acquisition_view import acquisition_history
from sec_agent.agent_runtime.context_observation import observe_context


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('before','after','review','receipts','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--wire',type=Path)
    args=parser.parse_args()
    paths=[args.before,args.after,args.review,args.receipts]+([args.wire] if args.wire else [])
    hashes={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}
    old,new,opinion=[p.read_text(encoding='utf-8') for p in paths[:3]]
    revision=revision_wording(old,new,opinion)
    for row in revision['related_wording']:
        assert new[row['offset']:].startswith(row['excerpt'])
    records=json.loads(args.receipts.read_text(encoding='utf-8'))
    messages=[ToolMessage(name=r['name'],tool_call_id=r['receipt'],status=r['status'],
        content=r['result'] if isinstance(r['result'],str) else json.dumps(r['result'],ensure_ascii=False)) for r in records]
    sources=acquisition_history(messages)
    result={'input_sha256':hashes,'revision_navigation':revision,
        'source_acquisition':sources,
        'measurements':{'tool_receipts':len(records),'urls':len(sources),'events':sum(len(s['events']) for s in sources),
            'read_after_obstacle':sum(s['read_after_obstacle'] for s in sources),
            'unresolved_after_latest_read':sum(s['unresolved_after_latest_read'] for s in sources),
            'related_excerpts':len(revision['related_wording']),
            'heading_excerpts':sum(r['kind']=='heading' for r in revision['related_wording']),
            'structural_headings':len(revision['delivery_anchors']['headings']),
            'revision_navigation_characters':len(json.dumps(revision,ensure_ascii=False))},
        'limitations':['Exact offsets verified; relatedness is not a semantic verdict.',
            'Receipt export without original arguments cannot attribute every failed read to a URL.',
            'No paid model, source retrieval, research conclusion or persistent artifact was changed.']}
    if args.wire: result['wire_observation']=observe_context(json.loads(args.wire.read_text(encoding='utf-8')))
    assert all(sha256(p.read_bytes()).hexdigest()==hashes[str(p)] for p in paths)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['measurements'],ensure_ascii=False))


if __name__=='__main__': main()
