"""Real BFF, SQLite and local LangGraph manual editing; no model/network nodes.

The SDK adapter and in-memory checkpoint backend are qualification surfaces,
not evidence of native HTTP deployment or production restart durability.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langchain_core.runnables import RunnableLambda

from tests.integration.fixtures.project_library_web import DraftThreads, EmptyThreads, OriginalService
from apps.workbench.backend.api.v1 import report_sessions
from apps.workbench.backend.app import create_report_session_app
from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.agent_runtime.report_session import build_report_session_graph
from sec_agent.agent_runtime.report_synthesis_agent import CaseReport, report_citations

REPORT_THREAD='00000000-0000-4000-8000-000000000015'
source=Path(os.environ['FIN_PROJECT_REPORT_SOURCE']).resolve()
root=Path(__file__).resolve().parents[3]
if not source.is_relative_to(root/'.local/fin014'):
    raise RuntimeError('Explicit saved development source required')
artifacts=CaseArtifacts([json.loads(source.read_text(encoding='utf-8'))])
ref='P01:'+artifacts.read_paper('P01','claims')[0]['claim_id']
report=CaseReport(title='项目成果接续资格',narrative_markdown=(
    '这是保存原件上的工程资格报告，不代表新的自主财务研究。已查询的年度收入可按原期间与单位回读；'
    '业务原因仍需结合其他来源判断，不由单项财务数字推出。 '*4)+f' [{ref}]')
initial={'report':{**report.model_dump(),'citations':report_citations(report,artifacts)},
         'report_review':{'summary':'工程资格，不给出金融质量结论。','findings':[],'unresolved_data_requests':[]},'revisions':{}}
def forbidden(*args,**kwargs):raise RuntimeError('No model calls authorized in this fixture')
graph=build_report_session_graph(writer=RunnableLambda(forbidden),verifier=RunnableLambda(forbidden),
    artifacts=artifacts,initial=initial).compile(checkpointer=InMemorySaver())


class Threads(DraftThreads):
    def __init__(self):
        super().__init__();self.opened=False
        self.rows[REPORT_THREAD]={'thread_id':REPORT_THREAD,'status':'interrupted',
            'metadata':{'surface':'research_workbench','owner_id':'local-pilot','graph':'report_session','title':'项目成果接续资格'},
            'created_at':'2026-09-14T00:00:00Z','updated_at':'2026-09-14T00:00:00Z'}
    async def ensure(self):
        if not self.opened:
            await graph.ainvoke({'open':True},{'configurable':{'thread_id':REPORT_THREAD}});self.opened=True
    @staticmethod
    def project(state):
        return {'values':state.values,'next':list(state.next),'created_at':state.created_at,
            'checkpoint':state.config['configurable'],
            'tasks':[{'name':t.name,'interrupts':[{'value':i.value} for i in t.interrupts]} for t in state.tasks]}
    async def get_state(self,tid,checkpoint_id=None):
        if tid!=REPORT_THREAD:return await super().get_state(tid)
        await self.ensure()
        return self.project(await graph.aget_state({'configurable':{'thread_id':tid,**({'checkpoint_id':checkpoint_id} if checkpoint_id else {})}}))
    async def get_history(self,tid,limit=10):
        await self.ensure()
        return [self.project(s) async for s in graph.aget_state_history({'configurable':{'thread_id':tid}},limit=limit)]


class Runs:
    async def list(self,*args,**kwargs):return []
    async def create(self,tid,graph_id,*,command,config,**kwargs):
        if tid!=REPORT_THREAD or command['resume']['action']!='manual_complete':forbidden()
        await graph.ainvoke(Command(resume=command['resume']),{'configurable':{'thread_id':tid,**config.get('configurable',{})}})
        return {'run_id':str(uuid4()),'status':'success'}


class Service(OriginalService):
    def __init__(self,*args,**kwargs):
        args=list(args)
        if len(args)>1:args[1]=artifacts
        else:kwargs['artifacts']=artifacts
        kwargs['research_profile']={'title':'Saved report preparation','default_question':'Read the selected saved report version.','branch_topics':[]}
        super().__init__(*args,**kwargs,sdk=SimpleNamespace(threads=Threads(),assistants=EmptyThreads(),runs=Runs()))

report_sessions.ReportSessionService=Service
app=create_report_session_app()
