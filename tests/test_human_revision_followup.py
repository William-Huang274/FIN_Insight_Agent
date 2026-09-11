import asyncio
import json
from types import SimpleNamespace

from scripts.qualification import human_revision_followup as probe
from test_dell_case_review_agent import artifacts, call
from test_dell_report_session import setup_session
from test_dell_case_convergence_agent import NativeFixtureModel


def test_probe_uses_native_checkpoint_and_keeps_original_immutable(tmp_path, monkeypatch, artifacts):
    _, _, initial, ref = setup_session(artifacts)
    state = {**initial, 'phase':'human_completed', 'report_version':2, 'human_edits':[
        {'number':1,'reason':'Withdraw cause','papers':[{'paper_id':'P01','after':'Observation only.'}]}]}
    source = tmp_path/'source.json'; source.write_text(json.dumps(state), encoding='utf-8')
    original = source.read_bytes()
    monkeypatch.setattr(probe, 'current_task_artifacts', lambda s: artifacts.with_human_edits(s['human_edits']))
    monkeypatch.setattr(probe, 'case_chat_model', lambda *a,**kw: NativeFixtureModel(marker='fixture',replies=[
        [call('read_current_workpaper',{'paper_id':'P01'},'read')],
        [call('submit_case_answer',{'answer_markdown':f'Observation only. [{ref}]'},'submit')],
        [call('read_current_workpaper',{'paper_id':'P01'},'read-second')],
        [call('submit_case_answer',{'answer_markdown':f'Observation only. [{ref}]'},'submit-second')]]))
    from scripts.qualification.dell_q1_specialist_paid_shadow import run_once
    monkeypatch.setattr(run_once,'_dotenv',lambda:{'DEEPSEEK_API_KEY':'test-not-a-secret'})
    output=tmp_path/'out'
    asyncio.run(probe.run(SimpleNamespace(source_state=source,output=output,execute=True)))
    rows=json.loads((output/'results.private.json').read_text(encoding='utf-8'))
    assert len(rows)==2 and all(r['submitted'] for r in rows)
    assert source.read_bytes()==original
