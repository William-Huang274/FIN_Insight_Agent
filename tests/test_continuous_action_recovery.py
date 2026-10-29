"""Offline maintenance never infers absence from a running service's empty list."""
from hashlib import sha256
import json
from uuid import uuid4
import pytest
from tests.integration.continuous_action_recovery import recover
from apps.workbench.backend.submission_receipts import SubmissionReceipts
from sec_agent.adapters.local_records import LocalRecords


@pytest.mark.parametrize('fault',[None,'native_running','ingress_running','run_exists','active_run','fingerprint'])
def test_quiescent_legacy_resolution_preserves_claim_and_requires_fence(tmp_path, monkeypatch, fault):
    project='fin-intake-native-unit';execution,operation,previous=map(str,[uuid4(),uuid4(),uuid4()])
    command={'principal':'oidc:alice','status':'unknown','run_id':None,'command_kind':'root_task',
        'request_text':'{}','request':{'previous_run_id':previous}}
    runs=[{'run_id':previous,'status':'success','metadata':{}}]
    if fault=='run_exists':runs[0]['metadata']={'organization_report_action':{'report_action_operation_id':operation}}
    if fault=='active_run':runs[0]['status']='pending'
    def output(args, **kwargs):
        if args[1]=='inspect':return json.dumps([{'Id':args[2],'State':{'Running':args[2].endswith('postgres-1') or fault=='native_running'},'Config':{'Labels':{'com.docker.compose.project':project}}}])
        return json.dumps(command if args[args.index('-d')+1]=='business' else runs)
    class Socket:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def settimeout(self,*args):pass
        def connect_ex(self,*args):return 0 if fault=='ingress_running' else 1
    monkeypatch.setattr('tests.integration.continuous_action_recovery.subprocess.check_output',output)
    monkeypatch.setattr('tests.integration.continuous_action_recovery.socket.socket',Socket)
    key=sha256(json.dumps(['oidc:alice',operation]).encode()).hexdigest()
    fingerprint=sha256(b'POST/api/v1/internal-research/organization/root-actions{}').hexdigest()
    prior={'status':'dispatching','fingerprint':'bad' if fault=='fingerprint' else fingerprint}
    with LocalRecords(tmp_path) as store:store[key]=prior
    if fault:
        with pytest.raises(AssertionError):recover(project,tmp_path,execution,operation,[21001,21002])
        with LocalRecords(tmp_path) as store:assert store[key]==prior
    else:
        proof=recover(project,tmp_path,execution,operation,[21001,21002])
        assert recover(project,tmp_path,execution,operation,[21001,21002])==proof
        with LocalRecords(tmp_path) as store:
            assert {k:v for k,v in store[key].items() if k!='quiescent_absence'}==prior
        assert SubmissionReceipts.abandoned_preflight(tmp_path,'oidc:alice',operation)
        (tmp_path/'maintenance'/proof['evidence_file']).write_text('{}')
        assert not SubmissionReceipts.abandoned_preflight(tmp_path,'oidc:alice',operation)
