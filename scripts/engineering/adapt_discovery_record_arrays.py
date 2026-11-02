"""Resolve saved discovery arrays by record shape, preserving raw source identity."""
import argparse
from collections import Counter
import json
from pathlib import Path
import zlib

from audit_source_binding_lineage import digest,read_lines,readonly
from structured_source_contract import describe


def run(ledger,output):
    rows=read_lines(ledger);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    selected={};changes=[]
    for row in rows:
        a=row.get('current_parser_artifact') or {}
        if a.get('lane')!='structured':continue
        path=a['path'];payload=Path(path).read_bytes()
        if digest(payload)!=a['sha256']:raise ValueError('parent_artifact_changed')
        # This adapter only consumes the unresolved native-array contract.
        if path.endswith('.gz'):continue
        old=json.loads(payload)
        if old.get('kind')!='unresolved_record_array':continue
        if path not in selected:
            source=row['current_source']
            if source.get('path'):raw=Path(source['path']).read_bytes()
            else:
                with readonly(source['database']) as db:
                    result=db.execute('SELECT body_zlib FROM raw_captures WHERE url=? AND digest=?',
                                      (source['url'],source['current_sha256'])).fetchone()
                if not result:raise ValueError('raw_source_unavailable')
                raw=zlib.decompress(result[0])
            if digest(raw)!=source['current_sha256'] or old['source_sha256']!=digest(raw):raise ValueError('source_identity_changed')
            value=json.loads(raw);contract=describe(dict(route='structured_json',structured_object=value))
            if contract['kind']=='unresolved_record_array':continue
            contract.update(source_sha256=digest(raw),source_object_conserved=True,parent_sha256=a['sha256'],
                            parent_artifact=path,raw_source_retained=True)
            target=out/(contract['source_sha256']+'.json')
            target.write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf8')
            selected[path]=dict(path=str(target),sha256=digest(target.read_bytes()),lane='structured',version=out.name,quality_pass=False)
            changes.append(dict(source_sha256=contract['source_sha256'],parent_path=path,parent_sha256=a['sha256'],
                                artifact=selected[path],kind=contract['kind'],records=contract['record_count']))
        row['current_parser_artifact']=selected[path]
        row['processing']['current_parser_artifact']=selected[path]
    assert len(rows)==len({r['document_id'] for r in rows})
    (out/'library-bindings.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf8')
    (out/'summary.json').write_text(json.dumps(dict(bindings=len(rows),changes=changes,
        kinds=dict(Counter(r['kind'] for r in changes)),input_sha256=digest(Path(ledger).read_bytes()),
        implementation_sha256=digest(Path(__file__).read_bytes()),contract_sha256=digest((Path(__file__).parent/'structured_source_contract.py').read_bytes()),
        quality_pass=False,provider_calls=0),ensure_ascii=False,indent=2),encoding='utf8')
    # The input is already fully parsed; the next audit has no new-original backlog.
    empty=out/'no-new-original-backlog';empty.mkdir()
    (empty/'summary.json').write_text(json.dumps(dict(planned=0,processed=0,rows=[])),encoding='utf8')
    print(json.dumps(dict(bindings=len(rows),adapted=len(changes),kinds=dict(Counter(r['kind'] for r in changes)))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ledger',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.ledger,a.output)
