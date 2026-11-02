"""Consume recovered Markdown/JSON using the existing native adapters, offline."""
import argparse
from collections import Counter
import gc
import gzip
import json
from pathlib import Path
import socket

from audit_source_binding_lineage import digest, read_lines


def run(args):
    def forbidden(*args, **kwargs):
        raise RuntimeError("network_disabled_for_recovered_parse")
    socket.create_connection = forbidden
    socket.socket.connect = forbidden
    from native_document_capture import capture_native, validate_capture
    from native_document_adaptation import adapt
    from finalize_structure_prechunks import classify
    from validate_source_structure_audit import validate
    from structured_source_contract import describe
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    rows=[r for r in read_lines(args.ledger) if r.get('recovered_content')]
    results=[]
    code={p.name:digest(p.read_bytes()) for p in [Path(__file__),*(Path(__file__).parent/n for n in
        ('native_document_capture.py','native_document_adaptation.py','finalize_structure_prechunks.py',
         'validate_source_structure_audit.py','structured_source_contract.py'))]}
    for row in rows:
        identity=row['recovered_content'];raw=Path(identity['path']).read_bytes()
        result=dict(document_id=row['document_id'],source_id=row['source_id'],source_sha256=identity['sha256'],
                    quality_pass=False,provider_calls=0)
        folder=out/identity['sha256'];folder.mkdir(exist_ok=True)
        try:
            assert digest(raw)==identity['sha256']
            if Path(identity['path']).suffix=='.md':
                native=capture_native(raw,'markdown',title=row['title'])
                validate_capture(native)
                document=adapt(native)
                errors=validate(document)
                if errors:raise ValueError('structure_contract:'+str(errors))
                if document.get('source_line_partition_complete') is not True:
                    raise ValueError('source_line_partition_incomplete')
                chunks=classify(document)
                artifacts={'native':native,'document':document,'prechunks':chunks}
                result.update(route='markdown',blocks=len(document['blocks']),chapters=len(document['chapter_tree']),
                              source_line_partition_complete=True)
            else:
                value=json.loads(raw)
                contract=describe({'route':'structured_json','structured_object':value})
                if contract.get('column_lengths_consistent') is False:raise ValueError('parallel_columns_mismatch')
                artifacts={'document':{'route':'structured_json','source_sha256':identity['sha256'],'structured_object':value},'records':contract}
                result.update(route='structured_json',record_kind=contract['kind'],records=contract.get('record_count',len(contract.get('records',[]))))
            result['artifacts']={}
            for name,value in artifacts.items():
                packed=gzip.compress(json.dumps(value,ensure_ascii=False).encode(),mtime=0)
                path=folder/(name+'.json.gz');path.write_bytes(packed)
                assert json.loads(gzip.decompress(path.read_bytes()))==value
                result['artifacts'][name]={'path':str(path),'sha256':digest(packed)}
            result['status']='engineering_checked_quality_pending'
            del artifacts
        except Exception as exc:
            result.update(status='failed',error=repr(exc))
        (folder/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        results.append(result);gc.collect()
        if len(results)%20==0:print(json.dumps({'processed':len(results),'planned':len(rows)}),flush=True)
    summary=dict(planned=len(rows),processed=len(results),statuses=dict(Counter(r['status'] for r in results)),
        routes=dict(Counter(r.get('route') for r in results)),code=code,
        ledger_sha256=digest(Path(args.ledger).read_bytes()),quality_pass=False,provider_calls=0,rows=results)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('rows','code')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ledger',required=True);p.add_argument('--output',required=True)
    run(p.parse_args())
