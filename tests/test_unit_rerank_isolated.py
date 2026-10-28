from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.engineering.prepare_unit_rerank_isolated import prepare_isolated, digest, encode


def fixture(tmp_path):
    paths={k:tmp_path/k for k in ('index','overlay','contexts','metadata','queries')}
    paths['overlay'].mkdir();paths['contexts'].mkdir()
    for path in (paths['index'],paths['overlay']/'overlay.json',paths['contexts']/'context.json',paths['metadata']):
        path.write_text('{}')
    paths['queries'].write_bytes(encode({'questions':[{'id':f'q{i}','query':f'Question{i}','vector':[i]} for i in range(3)]}))
    code={'source':'frozen-code'};calls=[]
    def invoke(command,directory,question,spec):
        calls.append(question['id']);directory.mkdir()
        assert command[command.index('--query-id')+1]==question['id']
        assert 'run' not in command
        name=question['id']+'.raw.jsonl'
        (directory/name).write_text('original-channel-evidence\n')
        job={'id':question['id'],'query':question['query'],
             'receipt':{'file':name,'sha256':digest(directory/name)}}
        path=directory/(question['id']+'.input.json');path.write_bytes(encode(job))
        plan={'inputs':spec['inputs'],'code_sha256':spec['code_sha256'],
              'jobs':[{'id':question['id'],'input_sha256':digest(path)}],
              'role':'regression','instruction':'fixed','pipeline':{'model':'same'},
              'index_digest':'fixed-index','relevance_boundary':None,
              'TokenBudgetBasis':{'input_scale':{'queries':1,'candidate_occurrences':48,'utf8_bytes':123},
                                  'limits':{'requests':1,'concurrency':1,'automatic_retries':0}}}
        (directory/'plan.json').write_bytes(encode(plan))
        return 0
    return paths,code,calls,invoke


def test_all_queries_have_one_process_and_exact_same_frozen_inputs(tmp_path):
    paths,code,calls,invoke=fixture(tmp_path);output=tmp_path/'result'
    result=prepare_isolated(paths,output,invoke=invoke,code_reader=lambda:code)
    assert calls==['q0','q1','q2']
    assert result['input_scale']=={'queries':3,'candidate_occurrences':144,'utf8_bytes':369}
    plan=json.loads((output/'plan.json').read_bytes())
    assert plan['TokenBudgetBasis']['limits']=={'requests':3,'concurrency':1,'automatic_retries':0}
    assert [j['id'] for j in plan['jobs']]==calls
    for item in plan['jobs']:
        assert digest(output/(item['id']+'.input.json'))==item['input_sha256']
        assert (output/(item['id']+'.raw.jsonl')).read_text()=='original-channel-evidence\n'
    assert plan['isolated_preparation']['all_queries_same_frozen_state']


def test_failed_worker_stops_without_retry_then_explicit_resume_reuses_verified_job(tmp_path):
    paths,code,calls,invoke=fixture(tmp_path);output=tmp_path/'result'
    def fail(command,directory,question,spec):
        if question['id']=='q1':
            calls.append('q1-failed');directory.mkdir();(directory/'partial.txt').write_text('preserve')
            return 1
        return invoke(command,directory,question,spec)
    with pytest.raises(RuntimeError,match='no_automatic_retry'):
        prepare_isolated(paths,output,invoke=fail,code_reader=lambda:code)
    assert calls==['q0','q1-failed'] and not (output/'plan.json').exists()
    assert json.loads((output/'preparation-status.json').read_bytes())['provider_calls']==0
    prepare_isolated(paths,output,resume=True,invoke=invoke,code_reader=lambda:code)
    assert calls==['q0','q1-failed','q1','q2']
    assert (output/'parts/0001/attempt-0001/partial.txt').read_text()=='preserve'


@pytest.mark.parametrize('mutation,expected',[
    ('inputs','frozen_state'),('code','frozen_state'),('query','query_changed'),
    ('input_bytes','input_changed'),('trace','trace_changed'),('escape','path_outside'),
    ('job','question_mismatch'),('pipeline','pipeline_changed'),
])
def test_child_mismatch_never_seals_unified_plan(tmp_path,mutation,expected):
    paths,code,calls,invoke=fixture(tmp_path);output=tmp_path/'result'
    def corrupt(command,directory,question,spec):
        result=invoke(command,directory,question,spec)
        if question['id']!='q1':return result
        pp=directory/'plan.json';p=json.loads(pp.read_bytes())
        jp=directory/'q1.input.json';j=json.loads(jp.read_bytes())
        if mutation=='inputs':p['inputs']['bad']='bad'
        elif mutation=='code':p['code_sha256']['bad']='bad'
        elif mutation=='job':p['jobs'][0]['id']='q0'
        elif mutation=='pipeline':p['pipeline']['model']='other'
        elif mutation=='input_bytes':jp.write_bytes(jp.read_bytes()+b' ')
        elif mutation=='trace':(directory/'q1.raw.jsonl').write_text('altered')
        else:
            if mutation=='query':j['query']='wrong question'
            if mutation=='escape':j['receipt']['file']='../elsewhere'
            jp.write_bytes(encode(j));p['jobs'][0]['input_sha256']=digest(jp)
        pp.write_bytes(encode(p));return result
    with pytest.raises(ValueError,match=expected):
        prepare_isolated(paths,output,invoke=corrupt,code_reader=lambda:code)
    assert not (output/'plan.json').exists() and calls==['q0','q1']


def test_code_change_during_preparation_rejected(tmp_path):
    paths,code,calls,invoke=fixture(tmp_path)
    def change(command,directory,question,spec):
        result=invoke(command,directory,question,spec);code['source']='new-code';return result
    # Return a snapshot, as the real code reader does.
    with pytest.raises(ValueError,match='preparation_changed'):
        prepare_isolated(paths,tmp_path/'result',invoke=change,code_reader=lambda:deepcopy(code))


def test_resume_changed_inputs_rejects_before_launch(tmp_path):
    paths,code,calls,invoke=fixture(tmp_path);output=tmp_path/'result'
    with pytest.raises(RuntimeError):
        prepare_isolated(paths,output,invoke=lambda *args:1,code_reader=lambda:code)
    paths['metadata'].write_text('{"changed":true}')
    with pytest.raises(ValueError,match='resume_frozen_state'):
        prepare_isolated(paths,output,resume=True,invoke=invoke,code_reader=lambda:code)
    assert calls==[]


@pytest.mark.parametrize('change',['instruction','boundary'])
def test_configuration_change_during_worker_rejects(tmp_path,monkeypatch,change):
    paths,code,calls,invoke=fixture(tmp_path)
    boundary=tmp_path/'boundary.json';boundary.write_text('{}')
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_RELEVANCE_BOUNDARY',str(boundary))
    def change_configuration(command,directory,question,spec):
        result=invoke(command,directory,question,spec)
        if change=='instruction':monkeypatch.setenv('FINSIGHT_ORGANIZATION_RERANK_INSTRUCTION','different')
        else:boundary.write_text('{"different":true}')
        return result
    with pytest.raises(ValueError,match='preparation_changed'):
        prepare_isolated(paths,tmp_path/'result',invoke=change_configuration,code_reader=lambda:code)


@pytest.mark.parametrize('ids',[[],['q','q'],['../q'],['q/child'],['q\\child'],['']])
def test_unsafe_or_incomplete_question_identity_rejected(tmp_path,ids):
    paths,code,calls,invoke=fixture(tmp_path)
    paths['queries'].write_bytes(encode({'questions':[{'id':i,'query':'x'} for i in ids]}))
    with pytest.raises(ValueError,match='query_ids_invalid'):
        prepare_isolated(paths,tmp_path/'result',invoke=invoke,code_reader=lambda:code)
    assert calls==[]
