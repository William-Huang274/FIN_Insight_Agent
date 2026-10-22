"""Incomplete/tampered fixtures never become resume authority."""
import json
import sqlite3
from types import SimpleNamespace
import zipfile

import pytest

from tests.integration import source_intake_checkpoint as cp
from scripts.engineering.source_intake_batches import host_memory_sample


def assets(root):
    for name in cp.FILES:
        path=root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE original (body TEXT)')
            db.execute('INSERT INTO original VALUES (?)', ('财年🧾\r\nRevenue 123.40 USD '*1000,))
    return root


def snapshot(tmp_path):
    root=tmp_path/'snapshot';root.mkdir()
    original=assets(tmp_path/'original')
    records=cp.pack_assets(original,root/'assets.zip')
    (root/'business.dump').write_bytes(b'fixture dump')
    binding={'source_ids':['a','b'],'baseline':'same-build'}
    manifest={'schema':'source-publication-checkpoint.v1','binding':binding,
        'publication':{'captures':[{'source_id':'a'}],'resources':{'a':'resource-a'},
            'grants':{'a':{}},'source_refs':[{'version_id':'v1'}]},'asset_files':records,
        'artifacts':{name:cp.digest(root/name) for name in ('assets.zip','business.dump')}}
    (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    return root,binding,manifest,original


def test_checkpoint_restores_exact_sqlite_bytes_and_unicode(tmp_path):
    root,binding,manifest,original=snapshot(tmp_path)
    assert cp.load_checkpoint(root,binding)==manifest
    destination=tmp_path/'new';destination.mkdir()
    cp.unpack_assets(root/'assets.zip',destination,manifest['asset_files'])
    for name in cp.FILES:
        assert (destination/name).read_bytes()==(original/name).read_bytes()
        with sqlite3.connect(destination/name) as db:
            assert '财年🧾' in db.execute('SELECT body FROM original').fetchone()[0]


@pytest.mark.parametrize('fault',[None,'missing','source','target','marker','scope','query','config','decision'])
def test_reviewed_replay_preserves_data_and_reports_original_baseline(tmp_path,fault):
    from copy import deepcopy
    root,_,manifest,_=snapshot(tmp_path)
    original=manifest['binding']
    original['baseline']={'git_head':'old','jar_sha256':'old-jar','configuration':{'source':'same'}}
    original['query_vectors_sha256']='fixed-query'
    (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    binding=deepcopy(original)
    binding['baseline'].update(git_head='new',jar_sha256='new-jar')
    review={'schema':'source-publication-replay-review.v1','source_manifest_sha256':cp.digest(root/'manifest.json'),
            'source_baseline':deepcopy(original['baseline']),'target_baseline':deepcopy(binding['baseline']),
            'decision':'compatible_fixture_only','reason':'No schema or custody changes; readback API added.',
            'changed_paths':['readback.py'],'git_diff_sha256':'a'*64}
    if fault=='source':review['source_baseline']['git_head']='wrong'
    if fault=='target':review['target_baseline']['git_head']='wrong'
    if fault=='marker':review['source_manifest_sha256']='wrong'
    if fault=='scope':binding['source_ids']=['other']
    if fault=='query':binding['query_vectors_sha256']='other'
    if fault=='config':
        binding['baseline']['configuration']={'source':'other'}
        review['target_baseline']=deepcopy(binding['baseline'])
    if fault=='decision':review['decision']='full_pass'
    if fault:
        with pytest.raises(ValueError):cp.load_checkpoint(root,binding,None if fault=='missing' else review)
    else:
        restored=cp.load_checkpoint(root,binding,review)
        assert restored==manifest and restored['binding']['baseline']['git_head']=='old'
        assert cp.digest(root/'manifest.json')==review['source_manifest_sha256']


@pytest.mark.parametrize('change',['baseline','scope','prefix','duplicate','dump','zip','missing_marker'])
def test_incompatible_or_incomplete_snapshot_is_rejected_before_services(tmp_path,change):
    root,binding,manifest,_=snapshot(tmp_path)
    if change=='baseline':binding['baseline']='other'
    elif change=='scope':binding['source_ids']=['a','c']
    elif change=='prefix':manifest['publication']['captures'][0]['source_id']='b'
    elif change=='duplicate':manifest['publication']['captures']*=2
    elif change in ('dump','zip'):(root/('business.dump' if change=='dump' else 'assets.zip')).write_bytes(b'changed')
    elif change=='missing_marker':(root/'manifest.json').unlink()
    if change in ('prefix','duplicate'):
        (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    with pytest.raises((ValueError,FileNotFoundError)):
        cp.load_checkpoint(root,binding)


@pytest.mark.parametrize('bad_name',['../escape','/absolute','attachments.sqlite'])
def test_zip_extra_or_duplicate_member_cannot_escape_or_overwrite(tmp_path,bad_name):
    root,_,manifest,_=snapshot(tmp_path)
    with zipfile.ZipFile(root/'assets.zip','a') as archive:
        archive.writestr(bad_name,b'injected')
    dest=tmp_path/'new';dest.mkdir()
    with pytest.raises(ValueError,match='members_mismatch'):
        cp.unpack_assets(root/'assets.zip',dest,manifest['asset_files'])
    assert not list(dest.rglob('*'))


def test_no_overwrite_and_disk_reserve(tmp_path,monkeypatch):
    root,_,manifest,original=snapshot(tmp_path)
    with pytest.raises(ValueError,match='empty_assets'):
        cp.unpack_assets(root/'assets.zip',original,manifest['asset_files'])
    dest=tmp_path/'new';dest.mkdir()
    monkeypatch.setattr(cp.shutil,'disk_usage',lambda p:SimpleNamespace(free=1))
    with pytest.raises(ValueError,match='disk_headroom'):
        cp.unpack_assets(root/'assets.zip',dest,manifest['asset_files'])


def test_wal_and_changed_archive_are_not_accepted(tmp_path):
    root=assets(tmp_path/'original')
    (root/'attachments.sqlite-wal').write_bytes(b'pending commit')
    with pytest.raises(ValueError,match='not_quiescent'):
        cp.pack_assets(root,tmp_path/'out.zip')
    assert not (tmp_path/'out.zip').exists()


def test_host_observation_includes_small_wsl_and_handles_process_exit():
    class Gone(Exception):pass
    class Process:
        def __init__(self,pid,name,rss):self.pid,self.label,self.rss=pid,name,rss
        def memory_info(self):
            if self.pid==99:raise Gone()
            return SimpleNamespace(rss=self.rss,private=self.rss*2)
        def create_time(self):return float(self.pid)
        def name(self):return self.label
        def cmdline(self):raise AssertionError('must not inspect private command lines')
    rows=[Process(i,'app',100+i) for i in range(20)]+[Process(40,'vmmemWSL',1),Process(99,'exited',0)]
    fake=SimpleNamespace(Error=Gone,process_iter=lambda:rows,
                         virtual_memory=lambda:SimpleNamespace(total=10000,available=2000))
    result=host_memory_sample(fake)
    assert len(result['processes'])==16
    assert result['processes'][-1]['name']=='vmmemWSL'
    assert result['unreadable_processes']==1


def test_failed_dump_leaves_no_completed_manifest(tmp_path,monkeypatch):
    import subprocess
    state=tmp_path/'state';assets(state/'project-library')
    stack=SimpleNamespace(output=tmp_path,state=state,processes=[],docker='docker')
    monkeypatch.setattr(cp,'own_postgres',lambda s:'own')
    def fail(*args,**kwargs):raise subprocess.CalledProcessError(1,['pg_dump'])
    monkeypatch.setattr(cp.subprocess,'run',fail)
    with pytest.raises(subprocess.CalledProcessError):cp.save_checkpoint(stack,{}, {})
    assert (tmp_path/'publication-checkpoint'/'business.dump').exists()
    assert not (tmp_path/'publication-checkpoint'/'manifest.json').exists()


def test_restore_rechecks_changed_file_before_any_docker_access(tmp_path,monkeypatch):
    root,binding,manifest,_=snapshot(tmp_path)
    approved=cp.load_checkpoint(root,binding)
    (root/'business.dump').write_bytes(b'changed after preflight')
    def forbidden(*args):raise AssertionError('must fail before Docker')
    monkeypatch.setattr(cp,'own_postgres',forbidden)
    with pytest.raises(ValueError,match='artifact_digest'):
        cp.restore_checkpoint(None,root,approved)


@pytest.mark.parametrize('ids,labels',[
    ('',{}),('a b',{}),('a',{'com.docker.compose.project':'shared','com.docker.compose.service':'postgres'}),
    ('a',{'com.docker.compose.project':'fin-intake-native-own','com.docker.compose.service':'api'})])
def test_foreign_or_ambiguous_container_is_never_dumped(tmp_path,monkeypatch,ids,labels):
    def output(args,**kwargs):
        return json.dumps([{'Id':'a','Config':{'Labels':labels}}]) if 'inspect' in args else ids
    monkeypatch.setattr(cp.subprocess,'check_output',output)
    with pytest.raises(ValueError):cp.own_postgres(SimpleNamespace(docker='docker',project='fin-intake-native-own'))


@pytest.mark.parametrize('change',[None,'project','members','revoked','grant','original','organization_original','during_read'])
def test_restored_authority_and_originals_are_checked_again(change):
    reads=[];access=[]
    bundle={'company':'A','period':'FY2025','unit':'USD','revision':2}
    grant={'id':'r','project_id':'p','organization_id':'o','revision':1,'binding':{'ref':{'version_id':'ov'}}}
    prior={'org':'o','project':'p','project_state':{'revision':1},'members':[{'active':True}],
           'captures':[{'source_id':'s'}],'source_refs':[{'version_id':'v'}],
           'resources':{'s':'r'},'grants':{'s':grant}}
    def api(method,path):
        if path.endswith('/members'):return [] if change=='members' else prior['members']
        if path=='/projects/p':return {} if change=='project' else prior['project_state']
        access.append(path)
        if change=='revoked':raise PermissionError('resource_revoked')
        if change=='grant' or (change=='during_read' and len(access)>1):return {**grant,'revision':2}
        return grant
    def original(owner,ref):
        reads.append(owner)
        corrupt=(change=='original' and owner=='oidc:alice') or (change=='organization_original' and owner=='organization:o')
        return {'source_bundle':{**bundle,'revision':3} if corrupt else bundle}
    storage=SimpleNamespace(read_source=original)
    if change:
        with pytest.raises((ValueError,PermissionError)):
            cp.verify_restored_publication(api,storage,storage,{'s':bundle},prior)
        if change in ('project','members','revoked','grant'):assert not reads
    else:
        cp.verify_restored_publication(api,storage,storage,{'s':bundle},prior)
        assert reads==['oidc:alice','organization:o'] and len(access)==2
