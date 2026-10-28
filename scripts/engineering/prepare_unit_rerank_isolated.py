"""Prepare every frozen query in a serial child process, without provider calls.

Each child exits after one query so its Python allocator and lexical caches are
released. Resume verifies code, all input files, completed jobs and trace hashes;
it never combines different preparation versions or resumes paid execution.
"""
import argparse
from copy import deepcopy
from hashlib import file_digest
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def digest(path):
    with Path(path).open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()


def frozen_inputs(paths):
    return {str(p.resolve()):digest(p) for p in (
        paths['index'], paths['overlay']/'overlay.json',
        paths['contexts']/'context.json', paths['metadata'], paths['queries'])}


def configuration_inputs():
    boundary=os.getenv('FINSIGHT_ORGANIZATION_RELEVANCE_BOUNDARY','')
    path=Path(boundary).resolve() if boundary else None
    if path and path.stat().st_size>4*1024*1024:raise ValueError('isolated_boundary_too_large')
    return {'instruction_policy':os.getenv('FINSIGHT_ORGANIZATION_RERANK_INSTRUCTION',''),
            'boundary_path':str(path) if path else None,'boundary_sha256':digest(path) if path else None}


def trace_files(value):
    if isinstance(value, dict):
        if 'file' in value and 'sha256' in value:
            yield value['file'], value['sha256']
        for child in value.values():yield from trace_files(child)
    elif isinstance(value, list):
        for child in value:yield from trace_files(child)


def checked_child(directory, question, spec):
    plan=json.loads((directory/'plan.json').read_bytes())
    if plan['code_sha256']!=spec['code_sha256'] or plan['inputs']!=spec['inputs']:
        raise ValueError('isolated_child_frozen_state_changed')
    if len(plan['jobs'])!=1 or plan['jobs'][0]['id']!=question['id']:
        raise ValueError('isolated_child_question_mismatch')
    item=plan['jobs'][0]; name=question['id']+'.input.json'; path=directory/name
    if path.is_symlink() or digest(path)!=item['input_sha256']:
        raise ValueError('isolated_child_input_changed')
    job=json.loads(path.read_bytes())
    if job['id']!=question['id'] or job['query']!=question['query']:
        raise ValueError('isolated_child_query_changed')
    files={name:item['input_sha256']}
    for name, expected in trace_files(job):
        if not isinstance(name,str) or Path(name).name!=name or not name.startswith(question['id']+'.'):
            raise ValueError('isolated_trace_path_outside_question')
        path=directory/name
        if path.is_symlink() or digest(path)!=expected:
            raise ValueError('isolated_trace_changed')
        if name in files and files[name]!=expected:raise ValueError('isolated_trace_conflict')
        files[name]=expected
    return plan, files


def prepare_isolated(paths, output, *, resume=False, invoke=None, code_reader=None):
    if code_reader is None:
        from scripts.engineering.qualify_unit_rerank import preparation_code
        code_reader=preparation_code
    paths={k:Path(v).resolve() for k,v in paths.items()};output=Path(output).resolve()
    questions=json.loads(paths['queries'].read_bytes())['questions']
    ids=[q['id'] for q in questions]
    if not ids or len(ids)!=len(set(ids)) or any(not isinstance(i,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,179}',i) for i in ids):
        raise ValueError('isolated_query_ids_invalid')
    spec={'format':'isolated-retrieval-preparation.v1','inputs':frozen_inputs(paths),
          'code_sha256':code_reader(),'query_ids':ids,'provider_calls':0,
          'configuration':configuration_inputs(),
          'automatic_worker_retries':0,'child_memory_guard_mib':800}
    if resume:
        if json.loads((output/'preparation.json').read_bytes())!=spec:
            raise ValueError('isolated_resume_frozen_state_changed')
    else:
        output.mkdir(parents=True,exist_ok=False)
        (output/'preparation.json').write_bytes(encode(spec))
    if (output/'plan.json').exists():raise ValueError('isolated_preparation_already_complete')
    def current():
        if (code_reader()!=spec['code_sha256'] or frozen_inputs(paths)!=spec['inputs']
                or configuration_inputs()!=spec['configuration']):
            raise ValueError('isolated_preparation_changed')
    plans=[];children=[];jobs=[]
    for position,question in enumerate(questions):
        current();base=output/'parts'/f'{position:04d}'
        base.mkdir(parents=True,exist_ok=True)
        attempts=sorted(base.glob('attempt-*'))
        completed=[p for p in attempts if (p/'plan.json').is_file()]
        if len(completed)>1:raise ValueError('isolated_multiple_completed_attempts')
        if completed:directory=completed[0]
        else:
            directory=base/f'attempt-{len(attempts)+1:04d}'
            command=[sys.executable,'-u','-m','scripts.engineering.qualify_unit_rerank','prepare']
            for key,value in paths.items():command.extend(['--'+key,str(value)])
            command.extend(['--output',str(directory),'--query-id',question['id']])
            if invoke is None:
                env=dict(os.environ);env.pop('QWEN_API_KEY',None)
                with (base/f'{directory.name}.log').open('xb') as log:
                    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,
                        cwd=Path(__file__).resolve().parents[2],check=False)
                returncode=result.returncode
            else:returncode=invoke(command,directory,question,spec)
            if returncode:
                (output/'preparation-status.json').write_bytes(encode({
                    'status':'stopped','completed_queries':len(jobs),'failed_question':question['id'],
                    'exit_code':returncode,'provider_calls':0,'retry_performed':False}))
                raise RuntimeError('isolated_worker_failed_no_automatic_retry')
        current()
        plan,files=checked_child(directory,question,spec)
        if plans:
            for field in ('role','instruction','relevance_boundary','pipeline','index_digest'):
                if plan.get(field)!=plans[0].get(field):raise ValueError('isolated_pipeline_changed')
        for name,expected in files.items():
            destination=output/name
            if destination.exists():
                if destination.is_symlink() or digest(destination)!=expected:
                    raise ValueError('isolated_published_file_changed')
            else:
                # Exclusive creation: interrupted copies remain detectable and
                # are never silently overwritten during resume.
                with (directory/name).open('rb') as source, destination.open('xb') as target:
                    shutil.copyfileobj(source,target)
                if digest(destination)!=expected:raise ValueError('isolated_copy_changed')
        plans.append(plan);jobs.extend(plan['jobs'])
        children.append({'directory':str(directory.relative_to(output)),
                         'plan_sha256':digest(directory/'plan.json')})
        print(json.dumps({'prepared':len(jobs),'total':len(questions),'id':question['id'],
                          'child_exited':True,'provider_calls':0}),flush=True)
    current()
    final=deepcopy(plans[0]);final['jobs']=jobs
    basis=final['TokenBudgetBasis'];basis['input_scale']={
        field:sum(p['TokenBudgetBasis']['input_scale'][field] for p in plans)
        for field in ('queries','candidate_occurrences','utf8_bytes')}
    basis['limits']['requests']=len(jobs)
    final['isolated_preparation']={'spec_sha256':digest(output/'preparation.json'),'children':children,
        'serial_processes':True,'all_queries_same_frozen_state':True,'provider_calls':0}
    with (output/'plan.json').open('xb') as stream:stream.write(encode(final))
    (output/'preparation-status.json').write_bytes(encode({'status':'complete','completed_queries':len(jobs),'provider_calls':0}))
    return basis


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('index','overlay','contexts','metadata','queries','output'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    print(json.dumps(prepare_isolated({k:getattr(args,k) for k in ('index','overlay','contexts','metadata','queries')},args.output,resume=args.resume)))
