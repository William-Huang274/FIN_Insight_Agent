import gzip
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/engineering'))
import repair_library_section_scopes as stage


def test_scope_repair_replays_ledger_and_rejects_corrupted_resume(tmp_path, monkeypatch):
    parent = tmp_path/'parent.json.gz'
    document = {
        'route':'edgartools', 'issues':[], 'source_containers':[],
        'blocks':[
            {'kind':'heading','text':'Item 5.02 Officers','level':1,'source_font_size_pt':10},
            {'kind':'heading','text':'Appointments','level':1,'source_font_size_pt':10},
            {'kind':'text','text':'Complete description.','chapter_ids':['chapter:1'],'chapter_blocks':[1]}],
        'chapter_tree':[
            {'id':'chapter:0','title':'Item 5.02 Officers','level':1,'parent_id':None,'basis':'sec_part_item_label'},
            {'id':'chapter:1','title':'Appointments','level':1,'parent_id':None,'basis':'parser_heading'}],
        'outline':[],
        'pre_chunks':[{'kind':'prose','block':2,'start':0,'end':21,'chapter_ids':['chapter:1']}],
    }
    parent.write_bytes(gzip.compress(json.dumps(document).encode()))
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'source_bindings':1,'sources':[{'document_id':'binding'}],
                                    'jobs':[{'id':'original','bindings':['binding']}]}))
    ledger = tmp_path/'ledger.jsonl'
    row = {'document_id':'binding','original_id':'original','artifact_path':str(parent),
           'artifact_sha256':stage.digest(parent),'route':'edgartools','issues':{},'headings':2,
           'execution_state':'prior_parse_retained','quality_state':'type_quality_review_required'}
    ledger.write_text(json.dumps(row)+'\n')
    output = tmp_path/'output'
    monkeypatch.setattr(sys,'argv',['repair','--manifest',str(manifest),'--ledger',str(ledger),'--output',str(output)])
    stage.main()
    updated = json.loads((output/'bindings.jsonl').read_text())
    assert updated['execution_state']=='section_scope_repaired'
    assert updated['parent_artifact_sha256']==row['artifact_sha256']
    artifact = Path(updated['artifact_path'])
    result = json.loads(gzip.decompress(artifact.read_bytes()))
    assert result['chapter_tree'][1]['parent_id']=='chapter:0'
    assert result['blocks'][2]['chapter_ids']==['chapter:0','chapter:1']
    assert parent.read_bytes() and stage.digest(parent)==row['artifact_sha256']
    stage.main()
    artifact.write_bytes(b'changed')
    with pytest.raises(ValueError,match='resume_artifact_changed'):
        stage.main()
