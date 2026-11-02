import gzip
import json
from pathlib import Path
from types import SimpleNamespace

from audit_current_library_recognition import run,audit_derived
from audit_source_binding_lineage import digest
from report_library_recognition import run as report


def test_one_denominator_keeps_pending_failed_and_limited_rows(tmp_path):
    ledger=tmp_path/'ledger.jsonl'
    rows=[dict(document_id=str(i),url='https://example.test/'+str(i),
        current_parser_artifact=None,processing={'stage':stage}) for i,stage in enumerate([
            'derived_content_processing','parse_current_original','parse_current_original'])]
    ledger.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    originals=tmp_path/'originals';originals.mkdir()
    (originals/'summary.json').write_text(json.dumps(dict(planned=2,processed=1,
        rows=[dict(document_id='1',status='failed',error='dependency_missing')])) )
    output=tmp_path/'out';run(SimpleNamespace(ledger=str(ledger),originals=str(originals),output=str(output)))
    summary=json.loads((output/'summary.json').read_bytes())
    assert summary['total_bindings']==3
    assert summary['counts']=={'limited_derived_bindings':1,'parse_failures':1,'pending_parse_bindings':1}
    assert not summary['quality_pass'] and not summary['full_current_original_execution_complete']
    report(output)
    assert '3 条统一资料' in (output/'current-library.html').read_text(encoding='utf8')
    assert len((output/'parse-plan.jsonl').read_text(encoding='utf8').splitlines())==3


def test_digest_failure_is_visible_and_not_promoted(tmp_path):
    artifact=tmp_path/'document.json.gz';artifact.write_bytes(gzip.compress(b'{}'))
    row=dict(document_id='a',url='https://example.test/a',processing={'stage':'continue_structure_quality'},
        current_parser_artifact=dict(path=str(artifact),sha256='wrong',lane='markdown',version='prior'))
    ledger=tmp_path/'ledger.jsonl';ledger.write_text(json.dumps(row)+'\n')
    originals=tmp_path/'originals';originals.mkdir()
    (originals/'summary.json').write_text(json.dumps(dict(planned=0,processed=0,rows=[])))
    output=tmp_path/'out';run(SimpleNamespace(ledger=str(ledger),originals=str(originals),output=str(output)))
    report=json.loads((output/'summary.json').read_bytes())
    assert report['counts']['audit_failed_artifacts']==1
    assert report['issue_counts']['engineering_audit_failure']==1
    assert not report['quality_pass']


def test_changed_raw_source_blocks_old_successful_artifact(tmp_path):
    source=tmp_path/'original.txt';source.write_text('changed')
    row=dict(document_id='a',url='https://example.test/a',processing={'stage':'continue_structure_quality'},
        current_source=dict(path=str(source),current_sha256=digest(b'original')))
    ledger=tmp_path/'ledger.jsonl';ledger.write_text(json.dumps(row)+'\n')
    originals=tmp_path/'originals';originals.mkdir()
    (originals/'summary.json').write_text(json.dumps(dict(planned=0,processed=0,rows=[])))
    output=tmp_path/'out';run(SimpleNamespace(ledger=str(ledger),originals=str(originals),output=str(output)))
    summary=json.loads((output/'summary.json').read_bytes())
    assert summary['counts']['source_recheck_failures']==1
    assert not summary['source_rechecks_pass'] and not summary['engineering_pass']


def test_derived_nodes_preserve_scope_and_require_exact_spans():
    import pytest
    d=dict(nodes=[dict(node_id='n',parent_document_id='s',content='abc',content_sha256=digest(b'abc'))],
           pre_chunks=[dict(node_index=0,start=0,end=3)])
    assert audit_derived(d,'s')['chunked_nodes']==1
    d['pre_chunks'][0]['start']=1
    with pytest.raises(ValueError,match='span_gap'):audit_derived(d,'s')
    d['pre_chunks'][0]['start']=0;d['nodes'][0]['numeric_authority']=True
    with pytest.raises(ValueError,match='unproved_derived_authority'):audit_derived(d,'s')
