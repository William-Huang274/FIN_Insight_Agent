"""Explicit offline recovery of a legacy *qualification* claim; never dispatch.

All ingress and the exact native container must be stopped. Read PostgreSQL
directly after that fence, archive the original receipt, and only add evidence.
The normal authorized reconcile route decides how Java closes the command.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import socket
import subprocess
from uuid import UUID
from filelock import FileLock
from sec_agent.adapters.local_records import LocalRecords


def recover(project, directory, execution, operation, ports):
    execution, operation = str(UUID(execution)), str(UUID(operation))
    if not project.startswith('fin-intake-native-') or len(ports) != 2:
        raise ValueError('isolated_qualification_and_both_ingress_ports_required')
    def inspect(service):
        row = json.loads(subprocess.check_output(['docker','inspect',project+'-'+service+'-1'],text=True,timeout=15))[0]
        assert row['Config']['Labels']['com.docker.compose.project'] == project
        return row
    def fence():
        native = inspect('api')
        assert not native['State']['Running'], 'native_must_be_stopped'
        for port in ports:
            with socket.socket() as sock:
                sock.settimeout(1)
                assert sock.connect_ex(('127.0.0.1',int(port))) != 0, 'ingress_must_be_stopped'
        return native['Id']
    native_id = fence()
    db = inspect('postgres')
    assert db['State']['Running']
    def query(database, sql):
        return json.loads(subprocess.check_output(['docker','exec',db['Id'],'psql','-U','probe','-d',database,
            '-At','-v','ON_ERROR_STOP=1','-c',sql],text=True,timeout=20))
    command = query('business', f"SELECT row_to_json(c) FROM (SELECT principal,status,run_id,command_kind,request_body::text AS request_text,request_body::jsonb AS request FROM organization_report_command WHERE execution_id='{execution}' AND operation_id='{operation}') c")
    assert command['status'] in ('dispatching','unknown') and command['run_id'] is None
    runs = query('probe', f"SELECT coalesce(json_agg(r),'[]') FROM (SELECT run_id,status,metadata FROM run WHERE thread_id='{execution}') r")
    matching = [r for r in runs if (r['metadata'].get('organization_report_action') or {}).get('report_action_operation_id') == operation]
    active = [r for r in runs if r['status'] in ('pending','running')]
    assert not matching and not active, 'native_absence_not_proven'
    assert runs and all(r['status']=='success' for r in runs), 'retained_results_required'
    assert any(r['run_id']==command['request']['previous_run_id'] for r in runs)
    key = sha256(json.dumps([command['principal'],operation]).encode()).hexdigest()
    directory = Path(directory)
    with FileLock(str(directory/(key+'.lock')),timeout=0), LocalRecords(directory) as cache:
        prior = cache[key]
        assert prior['status']=='dispatching' and not prior.get('dispatch_phase'), 'legacy_claim_only'
        assert command['command_kind'] in ('root_task','report')
        path='/api/v1/internal-research/organization/'+('root-actions' if command['command_kind']=='root_task' else 'report-actions')
        expected=sha256(b'POST'+path.encode()+command['request_text'].encode()).hexdigest()
        assert prior['fingerprint']==expected, 'original_request_fingerprint_mismatch'
        if prior.get('quiescent_absence'):
            return prior['quiescent_absence']
        assert fence()==native_id
        evidence={'at':datetime.now(timezone.utc).isoformat(),'project':project,'execution':execution,'operation':operation,
            'receipt_key':key,'original_receipt':prior,'native_container':native_id,'native_stopped':True,
            'ingress_ports':ports,'ingress_stopped':True,'command':command,'retained_runs':runs,
            'matching_native_runs':matching,'active_native_runs':active,'automatic_resubmission':False}
        target=directory/'maintenance';target.mkdir(exist_ok=True)
        path=target/(operation+'.json');raw=json.dumps(evidence,ensure_ascii=False,indent=2).encode()
        with path.open('xb') as output: output.write(raw)
        proof={'evidence_file':path.name,'sha256':sha256(raw).hexdigest()}
        cache[key]={**prior,'quiescent_absence':proof}
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True);parser.add_argument('--directory',required=True)
    parser.add_argument('--execution',required=True);parser.add_argument('--operation',required=True)
    parser.add_argument('--ports',required=True,type=int,nargs=2)
    args=parser.parse_args()
    print(json.dumps(recover(args.project,args.directory,args.execution,args.operation,args.ports)))
