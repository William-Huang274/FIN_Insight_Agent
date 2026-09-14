"""Zero-network qualification of a saved official SEC snapshot through BFF/MCP."""
from decimal import Decimal, localcontext
import json
import os
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest

from test_research_session_bff import _app
from local_research_resources import RUNTIME_ENVIRONMENT, _assert_assets
from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.project_sec_sources import ProjectSecSources
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from sec_agent.research_foundation.project_financial_facts import task_financial_snapshot
from sec_agent.agent_runtime.specialist_composition import open_specialist_scripted_qualification_composition
from sec_agent.agent_runtime.case_artifacts import CaseArtifacts

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'.local/fin014/20260914_e2_sec_browser_a1/project-library'
VERSION='4a35e943-f6b5-4e2f-9a19-2415e9a58e24'


@pytest.mark.local_data_integration
@pytest.mark.skipif(not os.getenv('FIN_SEC_MAPPING_ATTEMPT_DIR'),reason='explicit saved-source qualification directory')
def test_saved_sec_version_bff_sql_and_actual_expert_mcp():
    _assert_assets()
    output=Path(os.environ['FIN_SEC_MAPPING_ATTEMPT_DIR']).resolve()
    assert output.is_relative_to(ROOT/'.local/fin014')
    output.mkdir(parents=True,exist_ok=False)
    shutil.copytree(SOURCE,output/'project-library')
    library=ProjectLibrary(output/'project-library');sec=ProjectSecSources(library)
    project=next(p['id'] for p in library.index('local-pilot')['projects'] if any(v['version']==VERSION for v in sec.versions('local-pilot',p['id'])['items']))
    app,service,calls,tid=_app();service.attachment_store=TaskAttachmentStore(output/'attachments')
    async def update(thread_id,*,metadata):
        row=await service.sdk.threads.get(thread_id);row['metadata'].update(metadata);return row
    service.sdk.threads.update=update
    client=TestClient(app)
    response=client.post('/api/v1/research-sessions',headers={'X-Workbench-Request':'1'},json={
        'mode':'research','defer_start':True,'question':'Compare FY2025 Microsoft revenue and operating income from the selected SEC data.',
        'project_materials':{'project_id':project,'sec_version':VERSION}})
    assert response.status_code==200,response.text
    # Read the saved public announcement alongside the SEC numbers, retaining
    # upload authority and exact citation validation for this new user question.
    announcement=ROOT/'.local/fin014/20260914_e2_msft_material_source_a1/msft-fy25-q4.html'
    service.attachment_store.add(tid,'msft-fy25-q4.html',announcement.read_bytes())
    selected=task_financial_snapshot(service.attachment_store.root,tid)
    (output/'binding.json').write_text(json.dumps(selected[1],indent=2),encoding='utf-8')
    query={'ticker':'MSFT','metric_ids':['revenue','operating_income','operating_margin'],
           'research_as_of':'2025-08-01','selection_mode':'exact_period_end',
           'period_start':'2024-07-01','period_end':'2025-06-30','granularity':'fiscal_year'}
    result=client.post(f'/api/v1/research-sessions/{tid}/financial-facts',headers={'X-Workbench-Request':'1'},json=query)
    assert result.status_code==200,result.text
    payload=result.json();(output/'bff-query.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    expected={'revenue':'281724000000','operating_income':'128528000000'}
    with localcontext() as ctx:
        ctx.prec=34
        expected['operating_margin']=str(Decimal(expected['operating_income'])/Decimal(expected['revenue'])*100)
    facts={r['metric_id']:r['facts'][0] for r in payload['query_result']['results'] if r['status']=='resolved'}
    assert {k:v['value_decimal'] for k,v in facts.items()}==expected
    assert all(v['period_start']=='2024-07-01' and v['period_end']=='2025-06-30' for v in facts.values())
    requests=[]
    def scripted(request):
        requests.append(request)
        if len(requests)==1:
            return {'action':'request_finance','context_digest':request['context_digest'],
                'reason_summary':'Saved-source mapping qualification; use the selected task mart.',
                'intent':{k:v for k,v in query.items() if k!='research_as_of'}}
        numeric=[i for o in request['notebook']['observations'] for i in o['content'] if i.get('result_state')=='numeric_fact']
        rows=[i for o in request['notebook']['observations'] for i in o['content']]
        passages=[r for r in rows if r.get('passage')]
        catalog=[r for r in rows if r.get('document_id')]
        if not passages:
            return {'action':'request_source','context_digest':request['context_digest'],
                'reason_summary':'Read the saved issuer announcement before Q1 workpaper acceptance.',
                'selection':{'source_space':'uploads','operation':'read' if catalog else 'catalog',
                    **({'document_id':catalog[0]['document_id']} if catalog else {})}}
        passage=next(p for p in passages if 'Microsoft Corp.' in p['passage'])
        quote_start=passage['passage'].index('Microsoft Corp.')
        return {'action':'submit_workpaper','context_digest':request['context_digest'],
                'reason_summary':'Scripted qualification of archived numerical sources, not autonomous research quality.',
                'terminal_state':'supported','thesis':'Selected SEC snapshot supports these scoped numerical reads.',
                'mechanism':'Existing SQL selection and deterministic calculation; no business causality inference.',
                'narrative_markdown':'\n'.join(f"{r['metric_id']}: {r['value_decimal']} {r['unit']}; {r['period_start']} to {r['period_end']}." for r in numeric),
                'claims':[{'claim_id':r['metric_id'],'kind':'numeric_fact','materiality':'high',
                    'statement':f"{r['metric_id']}: {r['value_decimal']} {r['unit']}",
                    'evidence_ids':[],'fact_ids':[r['numeric_fact_id']],'numeric_authority':'authoritative',
                    'authority_note':'Source-bound kernel result; derived margin is a calculation, not a reported ratio.'} for r in numeric]+[
                    {'claim_id':'issuer-announcement','kind':'reported_fact','materiality':'low',
                     'statement':'The saved issuer announcement supplies source context; this uploaded copy remains unverified.',
                     'evidence_ids':[passage['passage_id']],'fact_ids':[],'numeric_authority':'not_applicable',
                     'authority_note':'Saved public HTML via the existing upload reader; no promotion of upload numeric authority.',
                     'citation_quotes':{passage['passage_id']:' '.join(passage['passage'][quote_start:].split()[:18])}}],
                'counterevidence':['Numerical consistency does not establish economic causality.'],
                'what_would_change':['An eligible conflicting or revised source observation.'],'open_gaps':[]}
    with open_specialist_scripted_qualification_composition(run_id='project-sec-'+tid,run_invocation_id='project-sec-'+tid,
        branch_id='Q1_ISSUER_TRUTH',environment={**RUNTIME_ENVIRONMENT,
            'FINSIGHT_TASK_ATTACHMENTS_ROOT':str(service.attachment_store.root),'FINSIGHT_TASK_THREAD_ID':tid,
            'FINSIGHT_RESEARCH_AS_OF':'2025-08-01T12:00:00Z'},scripted_model_turn=scripted,source_read_enabled=True,
            research_question='Compare FY2025 Microsoft revenue and operating income from the selected SEC data; retain period, units and sources.') as composition:
        graph=composition.graph.invoke(composition.graph_input.model_dump(mode='json'),{'recursion_limit':35})
    (output/'expert-graph.json').write_text(json.dumps(graph,indent=2),encoding='utf-8')
    observed=[i for o in graph['notebook']['observations'] for i in o['content'] if i.get('result_state')=='numeric_fact']
    assert {r['metric_id']:r['value_decimal'] for r in observed}==expected
    assert graph['final_submission'] is not None,graph['notebook'].get('feedback')
    assert graph['notebook']['tool_action_count']==3
    artifacts=CaseArtifacts([graph])
    claims=artifacts.read_paper('P01','claims')
    readback={sid:artifacts.read_source(sid,max_characters=50000) for c in claims for sid in c['source_ids']}
    (output/'cross_agent_sources.json').write_text(json.dumps(readback,indent=2),encoding='utf-8')
    assert {v['metric_id']:v['value_decimal'] for v in readback.values() if v.get('metric_id')}==expected
    assert any(v.get('numeric_fact_authority') is False and v.get('text') for v in readback.values())
    (output/'qualification_summary.json').write_text(json.dumps({'status':'bff_sql_actual_graph_pass',
        'provider_calls':0,'network_calls':0,'expected':expected,'task_id':tid,'project_id':project,
        'source_version':VERSION,'observations':selected[1]['counts'],'numeric_scope':'two mapped source-bound USD metrics and kernel derivation; not company-wide semantic acceptance'},indent=2),encoding='utf-8')
