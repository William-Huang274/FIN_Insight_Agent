"""Read an actual browser-created report snapshot through existing expert MCP."""
import json
import os
from pathlib import Path
import shutil
import pytest
from test_specialist_composition import RUNTIME_ENVIRONMENT, _assert_assets
from sec_agent.agent_runtime.specialist_composition import open_specialist_scripted_qualification_composition
from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore

ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.local_data_integration
@pytest.mark.skipif(not os.getenv('FIN_REPORT_READBACK_ATTEMPT'),reason='Explicit browser artifact and fresh attempt required')
def test_browser_selected_report_version_is_consumed_without_fact_promotion():
    _assert_assets()
    output=Path(os.environ['FIN_REPORT_READBACK_ATTEMPT']).resolve()
    source=Path(os.environ['FIN_REPORT_BROWSER_ARTIFACT']).resolve()
    assert output.is_relative_to(ROOT/'.local/fin014') and source.is_relative_to(ROOT/'.local/fin014')
    output.mkdir(parents=True,exist_ok=False)
    shutil.copytree(source/'attachments',output/'attachments')
    store=TaskAttachmentStore(output/'attachments')
    with store.connect() as db:
        rows=db.execute('SELECT a.thread,o.origin FROM attachments a JOIN attachment_origins o ON o.object_id=a.id').fetchall()
    row=max(rows,key=lambda r:json.loads(r['origin'])['research_origin']['report_version'])
    tid=row['thread'];origin=json.loads(row['origin']);expected=origin['research_origin']
    quote='只保留观察，撤回未证实归因。'
    def model(request):
        rows=[i for o in request['notebook']['observations'] for i in o['content']]
        passages=[r for r in rows if quote in r.get('passage','')]
        catalog=[r for r in rows if r.get('document_id')]
        common={'context_digest':request['context_digest'],'reason_summary':'Deterministic report-version and authority wiring qualification, not model quality.'}
        if passages:
            passage=passages[0]
            assert passage['project_origin']['research_origin']==expected
            assert passage['source_role']=='project_research_artifact' and not passage['numeric_fact_authority']
            return {**common,'action':'submit_workpaper','terminal_state':'supported',
                'thesis':'The selected report contains a user editorial correction, not a new issuer disclosure.',
                'mechanism':'Read the selected fixed version and retain its authority boundary.',
                'narrative_markdown':'所选研究成果记录用户撤回未证实归因；不作为发行人披露或新的金融数值事实。',
                'claims':[{'claim_id':'prior-user-correction','kind':'reported_fact','materiality':'low',
                    'statement':'The selected research artifact records a prior user correction.',
                    'evidence_ids':[passage['passage_id']],'fact_ids':[],'numeric_authority':'not_applicable',
                    'authority_note':'Research artifact/user editorial context, not independent disclosure.',
                    'citation_quotes':{passage['passage_id']:quote}}],
                'counterevidence':['A prior research conclusion can be wrong.'],
                'what_would_change':['Original sources supporting a different assessment.'],'open_gaps':[]}
        return {**common,'action':'request_source','selection':{'source_space':'uploads','operation':'read' if catalog else 'catalog',
            **({'document_id':catalog[0]['document_id']} if catalog else {})}}
    with open_specialist_scripted_qualification_composition(run_id='project-report-'+tid,run_invocation_id='project-report-'+tid,
        branch_id='Q1_ISSUER_TRUTH',environment={**RUNTIME_ENVIRONMENT,'FINSIGHT_TASK_ATTACHMENTS_ROOT':str(store.root),'FINSIGHT_TASK_THREAD_ID':tid},
        research_question='Read the selected report version and distinguish user corrections from issuer facts.',
        scripted_model_turn=model,source_read_enabled=True,max_model_turns=4) as composition:
        graph=composition.graph.invoke(composition.graph_input.model_dump(mode='json'),{'recursion_limit':35})
    (output/'expert-graph.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf-8')
    assert graph['final_submission'] is not None,graph['notebook']['feedback']
    artifacts=CaseArtifacts([graph])
    claim=artifacts.read_paper('P01','claims')[0]
    read=artifacts.read_source(claim['source_ids'][0],max_characters=50000)
    assert read['project_origin']['research_origin']==expected and quote in read['text']
    assert read['source_role']=='project_research_artifact' and not read['numeric_fact_authority']
    (output/'readback.json').write_text(json.dumps({'source':read,'provider_calls':0,'network_calls':0,'status':'version_and_authority_scope_pass'},ensure_ascii=False,indent=2),encoding='utf-8')
