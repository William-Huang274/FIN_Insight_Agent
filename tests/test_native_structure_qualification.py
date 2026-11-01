import importlib.util
from pathlib import Path
import subprocess

spec=importlib.util.spec_from_file_location('qualification',Path(__file__).parents[1]/'scripts/engineering/run_native_structure_qualification.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_child_timeout_records_partial_output_without_retry(tmp_path,monkeypatch):
    calls=[]
    def run(*args,**kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired(args[0],1,output=b'partial',stderr=b'failure')
    monkeypatch.setattr(module.subprocess,'run',run)
    log=tmp_path/'timeout.log'
    assert module.run_child(['python'],log,1)==124
    assert len(calls)==1
    assert 'partialfailure' in log.read_text()
    assert 'qualification_child_timeout' in log.read_text()


def test_child_failure_remains_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(module.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a,2,'out','error'))
    log=tmp_path/'failure.log'
    assert module.run_child(['python'],log,1)==2
    assert log.read_text()=='outerror'
